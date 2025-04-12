from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status, Body
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message import MessageResponse, MessageCreatePayload, MessageCreate
from app.models.conversation import Conversation, ConversationStatusEnum

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
        "validates the conversation, persists a new outgoing message, resets the conversation's "
        "unread count, potentially updates its status to HUMAN_ACTIVE, updates the last message snapshot, "
        "and enqueues the message for delivery."
    ),
)
async def create_outgoing_message(
    conversation_id: UUID = Path(..., description="The target conversation ID."),
    payload: MessageCreatePayload = Body(...),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> MessageResponse:
    """Create and send an outgoing message, updating conversation state.

    Args:
        conversation_id (UUID): The target conversation ID.
        payload (MessageCreatePayload): The message content from the frontend.
        db (AsyncSession): The database session provided by FastAPI.
        auth_context (AuthContext): Authentication context.

    Returns:
        MessageResponse: The persisted message details.

    Raises:
        HTTPException: 404 if the conversation is not found.
        HTTPException: 500 if saving or updating fails unexpectedly.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    # Fetch conversation within the transaction context managed by FastAPI
    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )
    if not conversation:
        logger.warning(
            f"Conversation {conversation_id} not found for account {account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    # Store original status for later check
    original_status = conversation.status

    # Generate an internal source_id for tracking
    internal_source_id = f"internal-{uuid4().hex}"

    message_data = MessageCreate(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=(
            conversation.contact_inbox.contact_id
            if conversation.contact_inbox
            else None
        ),
        source_id=internal_source_id,
        user_id=user_id,
        direction="out",
        status="processing",
        message_timestamp=datetime.now(timezone.utc),
        content=payload.content,
        content_type="text",
        content_attributes={
            "source": "frontend",
            "channel_type": (
                conversation.inbox.channel_type if conversation.inbox else None
            ),
        },
    )

    # --- Database Operations ---
    # These operations will be committed/rolled back together by FastAPI
    try:
        # 1. Create the message
        # Assuming get_or_create_message uses the provided 'db' session and doesn't commit itself
        message = await message_repo.get_or_create_message(db, message_data)
        if not message:
            logger.error(
                f"Failed to create message for conversation {conversation_id}, get_or_create returned None."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create message.",
            )

        logger.info(
            f"Outgoing message {message.id} created for conversation {conversation_id}."
        )

        # Variable to hold the latest conversation state after updates
        final_updated_conversation: Conversation = conversation

        # 2. Reset Unread Count (since agent sent a message)
        logger.debug(f"Resetting unread count for conversation {conversation.id}")
        updated_conv_reset = await conversation_repo.reset_conversation_unread_count(
            db=db,
            account_id=account_id,
            conversation_id=conversation.id,
        )
        if updated_conv_reset:
            final_updated_conversation = updated_conv_reset
            logger.info(f"Unread count reset for conversation {conversation.id}")
        else:
            logger.warning(
                f"Failed to reset unread count for conversation {conversation.id} (maybe already 0 or conversation not found during reset?)."
            )

        # 3. Update Status to HUMAN_ACTIVE if it was PENDING
        if original_status == ConversationStatusEnum.PENDING:
            logger.debug(
                f"Updating status for conversation {conversation.id} from PENDING to HUMAN_ACTIVE"
            )
            updated_conv_status = await conversation_repo.update_conversation_status(
                db=db,
                account_id=account_id,
                conversation_id=conversation.id,
                new_status=ConversationStatusEnum.HUMAN_ACTIVE,
            )
            if updated_conv_status:
                final_updated_conversation = updated_conv_status
                logger.info(
                    f"Status updated for conversation {conversation.id} to HUMAN_ACTIVE"
                )
            else:
                logger.warning(
                    f"Failed to update status for conversation {conversation.id} to HUMAN_ACTIVE."
                )

        # 4. Update Last Message Snapshot (using the final updated conversation state)
        logger.debug(
            f"Message ID to update the conversation last message: {message.id}"
        )
        await update_last_message_snapshot(
            db=db,
            conversation=final_updated_conversation,
            message=message,
        )
        logger.debug(
            f"Last message snapshot updated for conversation {conversation.id}"
        )

        logger.debug(
            f"Explicitly flushing session after conversation updates for {conversation.id}"
        )
        await db.refresh(final_updated_conversation)
        await db.flush()
        logger.debug(f"Session flushed after conversation update.")

    except Exception as e:
        logger.exception(
            f"Database error during outgoing message creation/update for conversation {conversation_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message or update conversation state.",
        )

    # --- Post-Transaction Operations (Queueing & WebSockets) ---
    # These happen only if the database operations above were successful (no exception raised)
    # Enqueue the message ID for the sending worker
    try:
        # Ensure queue is connected (ideally handle connection more robustly)
        if not queue.is_connected:
            logger.warning(
                "[queue] Response queue not connected. Attempting to connect..."
            )
            await queue.connect()
            if not queue.is_connected:
                logger.error(
                    "[queue] Failed to connect to response queue. Cannot enqueue message."
                )
            else:

                await queue.enqueue({"message_id": str(message.id)})
                logger.info(f"[queue] Message {message.id} enqueued for delivery")
        else:
            await queue.enqueue({"message_id": str(message.id)})
            logger.info(f"[queue] Message {message.id} enqueued for delivery")

    except Exception as e:
        logger.error(
            f"[queue] Failed to enqueue message {message.id} for delivery: {e}"
        )
        # Potentially add a background task to retry enqueueing later

    # Publish WebSocket events
    try:
        # Event for the specific conversation (new message)
        logger.debug(f"Attempting to serialize message {message.id}...")
        message_payload_ws = jsonable_encoder(message)
        logger.debug(f"Message {message.id} serialized successfully.")
        await publish_to_conversation_ws(
            conversation_id=conversation.id,
            data={
                "type": "new_message",
                "payload": message_payload_ws,
            },
        )
        logger.debug(
            f"[ws] Published new_message event for conversation {conversation.id}"
        )

        # Event for the account list (updated conversation state)
        # Use the final_updated_conversation which includes reset count/new status
        parsed_conversation = parse_conversation_to_conversation_response(
            final_updated_conversation
        )
        logger.debug(
            f"Attempting to serialize conversation {parsed_conversation.id}..."
        )
        conversation_payload_ws = jsonable_encoder(parsed_conversation)
        logger.debug(f"conversation {parsed_conversation.id} serialized successfully.")
        await publish_to_account_conversations_ws(
            final_updated_conversation.account_id,
            {
                "type": "conversation_updated",
                "payload": conversation_payload_ws,
            },
        )
        logger.debug(
            f"[ws] Published conversation_updated event for conversation {conversation.id}"
        )

    except Exception as e:
        logger.warning(
            f"[ws] Failed to publish WebSocket events for message {message.id}: {e}"
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
