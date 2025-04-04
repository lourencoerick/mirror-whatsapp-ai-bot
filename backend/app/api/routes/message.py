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
    description="Retrieves a paginated list of messages for a specific conversation, supporting cursor-based pagination.",
    response_description="A list of messages, ordered chronologically (oldest first).",
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
):
    """
    API endpoint to fetch messages with cursor-based pagination.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Validação básica (embora a lógica do cursor no CRUD já lide com isso)
    if before_cursor and after_cursor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use 'before_cursor' and 'after_cursor' simultaneously.",
        )

    if db is None:  # Verificação básica da dependência
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database session not available",
        )

    try:
        # Chama a função CRUD atualizada
        messages = await message_repo.get_messages_paginated(
            db=db,
            account_id=account_id,
            conversation_id=conversation_id,
            limit=limit,
            before_cursor=before_cursor,
            after_cursor=after_cursor,
        )

        # A função CRUD já retorna lista vazia se a conversa não existe ou o cursor é inválido
        # Não precisamos de um 404 explícito aqui, a menos que queiramos distinguir
        # "conversa não existe" de "sem mensagens antes/depois".

        return messages  # FastAPI converte para MessageResponse

    except Exception as e:
        print(
            f"Error in get_conversation_messages_paginated endpoint: {e}"
        )  # Logue o erro
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching messages.",
        )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
async def create_outgoing_message(
    conversation_id: UUID,
    payload: MessageCreatePayload,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
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
        db (AsyncSession): Database session.

    Returns:
        MessageResponse: The message after being saved and optionally sent.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id
    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )
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

    # Create or reuse message
    message = await message_repo.get_or_create_message(db, message_data)

    # Update last message in the conversation
    if message:
        if conversation:
            await update_last_message_snapshot(
                db=db,
                conversation=conversation,
                message=message,
            )
        else:
            logger.warning(
                f"[consumer] Conversation not found: {message.conversation_id}"
            )

    try:
        await queue.enqueue({"message_id": message.id})
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


@router.get(
    "/conversations/{conversation_id}/messages/context/{message_id}",
    response_model=List[MessageResponse],
    summary="Get Message Context",
    description="Retrieves a message and a specified number of surrounding messages within its conversation.",
    response_description="A list of messages representing the context, ordered chronologically.",
)
async def get_message_context_endpoint(
    conversation_id: UUID = Path(
        ..., description="The ID of the conversation to search within"
    ),
    message_id: UUID = Path(
        ..., description="The ID of the target message for context"
    ),
    limit_before: int = Query(
        5,
        ge=0,
        le=200,
        description="Number of messages to retrieve before the target message",
    ),
    limit_after: int = Query(
        5,
        ge=0,
        le=200,
        description="Number of messages to retrieve after (and including) the target message",
    ),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    API endpoint to fetch the context around a specific message.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database session not available",
        )

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
