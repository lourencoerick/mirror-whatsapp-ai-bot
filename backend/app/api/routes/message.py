from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message import MessageResponse, MessageCreatePayload, MessageCreate
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
queue = RedisQueue(queue_name="response_queue")


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    summary="Get Conversation Messages (Paginated)",
    description=(
        "Retrieves a paginated list of messages for a specific conversation, "
        "supporting cursor-based pagination. The messages are ordered chronologically "
        "(oldest first)."
    ),
    response_description="A list of messages.",
)
async def get_conversation_messages_paginated(
    conversation_id: UUID = Path(..., description="The ID of the conversation"),
    limit: int = Query(
        30, ge=1, le=100, description="Maximum number of messages to return"
    ),
    before_cursor: Optional[UUID] = Query(
        None, description="Fetch messages older than this message ID"
    ),
    after_cursor: Optional[UUID] = Query(
        None, description="Fetch messages newer than this message ID"
    ),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> List[MessageResponse]:
    """Retrieve messages for a conversation using cursor-based pagination.

    Args:
        conversation_id (UUID): The ID of the conversation.
        limit (int): Maximum number of messages to return.
        before_cursor (Optional[UUID]): Fetch messages older than this message ID.
        after_cursor (Optional[UUID]): Fetch messages newer than this message ID.
        db (AsyncSession): The database session.
        auth_context (AuthContext): Authentication context containing user and account info.

    Returns:
        List[MessageResponse]: A list of messages ordered chronologically (oldest first).

    Raises:
        HTTPException: 404 if the conversation is not found.
        HTTPException: 400 if both before_cursor and after_cursor are provided.
    """
    account_id = auth_context.account.id

    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if before_cursor and after_cursor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use 'before_cursor' and 'after_cursor' simultaneously.",
        )

    messages = await message_repo.get_messages_paginated(
        db=db,
        account_id=account_id,
        conversation_id=conversation_id,
        limit=limit,
        before_cursor=before_cursor,
        after_cursor=after_cursor,
    )
    return messages


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    summary="Create Outgoing Message",
    description=(
        "Creates and sends an outgoing message linked to a conversation. The endpoint "
        "validates the conversation, persists a new outgoing message with a generated source_id, "
        "updates the last message snapshot in the conversation, and enqueues the message for delivery."
    ),
)
async def create_outgoing_message(
    conversation_id: UUID,
    payload: MessageCreatePayload,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> MessageResponse:
    """Create and send an outgoing message linked to a conversation.

    Args:
        conversation_id (UUID): The target conversation ID.
        payload (MessageCreatePayload): The message content from the frontend.
        db (AsyncSession): The database session.
        auth_context (AuthContext): Authentication context containing user and account info.

    Returns:
        MessageResponse: The persisted message.

    Raises:
        HTTPException: 404 if the conversation is not found.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Generate an internal source_id
    internal_source_id = f"internal-{uuid4().hex}"

    message_data = MessageCreate(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=conversation.contact_inbox.contact_id,
        source_id=internal_source_id,
        user_id=user_id,
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

    # Create or reuse message (the repository handles transaction management)
    message = await message_repo.get_or_create_message(db, message_data)

    # Update last message snapshot in the conversation
    if message:
        await update_last_message_snapshot(
            db=db,
            conversation=conversation,
            message=message,
        )
    else:
        logger.warning(f"[consumer] Conversation not found: {message.conversation_id}")

    try:
        await queue.enqueue({"message_id": message.id})
        logger.debug(f"[queue] Message {message.id} enqueued for delivery")
    except Exception as e:
        logger.warning(f"[queue] Failed to enqueue message {message.id}: {e}")

    try:
        logger.debug(f"[ws] Publishing message to the channel...")
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
        logger.warning(
            f"[ws] Failed to publish message {message.id} to account channel: {e}"
        )

    return message


@router.get(
    "/conversations/{conversation_id}/messages/context/{message_id}",
    response_model=List[MessageResponse],
    summary="Get Message Context",
    description=(
        "Retrieves a target message and a specified number of surrounding messages "
        "within its conversation. The context is ordered chronologically."
    ),
    response_description="A list of messages representing the context.",
)
async def get_message_context_endpoint(
    conversation_id: UUID = Path(
        ..., description="The ID of the conversation to search within"
    ),
    message_id: UUID = Path(
        ..., description="The ID of the target message for context"
    ),
    limit_before: int = Query(
        5, ge=0, le=200, description="Number of messages to retrieve before the target"
    ),
    limit_after: int = Query(
        5,
        ge=0,
        le=200,
        description="Number of messages to retrieve after (and including) the target",
    ),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> List[MessageResponse]:
    """Retrieve context messages around a specific target message.

    Args:
        conversation_id (UUID): The ID of the conversation to search within.
        message_id (UUID): The ID of the target message.
        limit_before (int): Number of messages to retrieve before the target message.
        limit_after (int): Number of messages to retrieve after (and including) the target message.
        db (AsyncSession): The database session.
        auth_context (AuthContext): Authentication context containing user and account info.

    Returns:
        List[MessageResponse]: A list of context messages, ordered chronologically.

    Raises:
        HTTPException: 404 if no context messages are found.
        HTTPException: 500 if an error occurs while fetching the message context.
    """
    account_id = auth_context.account.id

    try:
        messages = await conversation_repo.get_message_context(
            db=db,
            account_id=account_id,
            conversation_id=conversation_id,
            target_message_id=message_id,
            limit_before=limit_before,
            limit_after=limit_after,
        )

        if not messages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target message or conversation not found, or no context available.",
            )

        return messages

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in get_message_context_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching message context.",
        )
