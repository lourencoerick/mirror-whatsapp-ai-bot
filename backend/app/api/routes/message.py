from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from loguru import logger

from app.database import get_db
from app.middleware.account_context import get_account_id
from app.services.queue.publisher import publish_message_to_queue
from app.api.schemas.message import MessageRead, MessageCreatePayload, MessageCreate
from app.services.repository import message as message_repo
from app.services.repository import conversation as conversation_repo
from app.services.helper.conversation import (
    update_last_message_snapshot,
    parse_conversation_to_conversation_response,
)
from app.services.helper.websocket import (
    publish_to_conversation_ws,
    publish_to_account_conversations_ws,
)

router = APIRouter()


@router.get(
    "/conversations/{conversation_id}/messages", response_model=List[MessageRead]
)
def get_messages(
    conversation_id: UUID,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Retrieve a paginated list of messages from a conversation.

    Args:
        conversation_id (UUID): ID of the conversation.
        limit (int): Max number of messages to return (default: 20).
        offset (int): Number of messages to skip for pagination (default: 0).
        db (Session): Injected database session.

    Returns:
        List[MessageRead]: List of messages for the given conversation.
    """
    account_id = get_account_id()
    return message_repo.find_messages_by_conversation(
        db=db,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
        account_id=account_id,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=201,
)
async def create_outgoing_message(
    conversation_id: UUID,
    payload: MessageCreatePayload,
    db: Session = Depends(get_db),
):
    """
    Creates and sends an outgoing message linked to a conversation.

    - Validates that the conversation exists and belongs to the account
    - Persists a new outgoing message using a generated source_id
    - Sends the message to the external provider (e.g., Evolution)
    - Updates the source_id if an external ID is returned

    Args:
        conversation_id (UUID): The target conversation ID.
        payload (MessageCreatePayload): The message content from the frontend.
        db (Session): Database session.

    Returns:
        MessageRead: The message after being saved and optionally sent.
    """
    conversation = conversation_repo.find_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Generate internal source_id
    internal_source_id = f"internal-{uuid4().hex}"

    message_data = MessageCreate(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=conversation.contact_inbox.contact_id,
        source_id=internal_source_id,
        user_id=UUID("22222222-2222-2222-2222-222222222222"),
        direction="out",
        status="processing",
        message_timestamp=datetime.now(timezone.utc),
        content=payload.content,
        content_type="text",
        content_attributes={
            "source": "frontend",
            "channel_type": conversation.inbox.channel_type,
        },
    )

    # Create or reuse message
    message = message_repo.get_or_create_message(db, message_data)

    # Update last message in the conversation
    if message:
        if conversation:
            update_last_message_snapshot(
                db=db, conversation=conversation, message=message
            )
        else:
            logger.warning(
                f"[consumer] Conversation not found: {message.conversation_id}"
            )

    try:
        publish_message_to_queue(message_id=message.id, queue_name="response_queue")
        logger.debug(f"[queue] Message {message.id} enqueued for delivery")
    except Exception as e:
        logger.warning(f"[queue] Failed to enqueue message {message.id}: {e}")

    try:
        logger.debug(f"[ws] publishing message to the channel....")
        await publish_to_conversation_ws(
            conversation_id=conversation.id,
            data={
                "type": "new_message",
                "payload": jsonable_encoder(message),
            },
        )
    except Exception as e:
        logger.warning(f"[ws] Failed to publish message {message.id} to Redis: {e}")

    try:
        await publish_to_account_conversations_ws(
            conversation.account_id,
            {
                "type": "conversation_updated",
                "payload": jsonable_encoder(
                    parse_conversation_to_conversation_response(conversation)
                ),
            },
        )
    except Exception as e:
        logger.warning(f"[ws] Failed to publish message {message.id} to Redis: {e}")
    return message
