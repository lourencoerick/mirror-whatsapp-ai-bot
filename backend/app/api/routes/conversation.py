from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body, Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.conversation import (
    ConversationSearchResult,
    StartConversationResponse,
    StartConversationRequest,
    ConversationUpdateStatus,
)
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo
from app.services.repository import inbox as inbox_repo
from app.models.conversation import Conversation, ConversationStatusEnum
from app.services.helper.websocket import publish_to_account_conversations_ws
from app.services.helper.conversation import (
    conversations_to_conversations_response,
    parse_conversation_to_conversation_response,
)
from app.api.schemas.contact import ContactCreate
from app.services.helper.contact import normalize_phone_number


router = APIRouter()


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationSearchResult,
    summary="Find Conversation",
)
async def get_conversation(
    conversation_id: UUID = Path(..., description="Conversation ID"),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Handles listing and searching conversations based on the presence of the 'q' query parameter.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    try:
        conversation = await conversation_repo.find_conversation_by_id(
            db=db, account_id=account_id, conversation_id=conversation_id
        )
        return parse_conversation_to_conversation_response(conversation)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving conversations. {e}",
        )


@router.get(
    "/conversations",
    response_model=List[ConversationSearchResult],
    summary="List or Search Conversations",
    description="Retrieve a list of conversations. Use the 'q' parameter to search by contact name, phone number, or message content.",
    response_description="A list of conversations matching the criteria",
)
async def search_or_list_conversations(
    q: Optional[str] = Query(
        None,
        min_length=2,
        max_length=100,
        title="Search Query",
        description="Search term for contact name, phone number, or message content. If omitted, returns a list of all conversations.",
    ),
    offset: int = Query(
        0, ge=0, title="Skip", description="Number of records to skip for pagination"
    ),
    limit: int = Query(
        20,
        ge=1,
        le=200,
        title="Limit",
        description="Maximum number of records to return",
    ),
    status: Optional[List[ConversationStatusEnum]] = Query(
        None,
        title="Status of the conversation",
        description="Status of the conversation (`PENDING`, `HUMAN_ACTIVE`, `CLOSED`... )",
    ),
    has_unread: Optional[bool] = Query(
        None,
        title="Flag indicating if there is unread messages",
        description="Flag indicating if there is unread messages",
    ),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Handles listing and searching conversations based on the presence of the 'q' query parameter.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id
    logger.debug(f"[conversation route] Status Filter active :{status}")
    try:
        if q:
            # --- Search Path ---
            conversations = await conversation_repo.search_conversations(
                db=db,
                user_id=user_id,
                account_id=account_id,
                query=q,
                offset=offset,
                limit=limit,
                status=status,
                has_unread=has_unread,
            )
            return conversations
        else:
            conversations = await conversation_repo.find_conversations_by_user(
                db=db,
                user_id=user_id,
                account_id=account_id,
                limit=limit,
                offset=offset,
                status=status,
                has_unread=has_unread,
            )
        return conversations_to_conversations_response(conversations)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving conversations. {e}",
        )


@router.get(
    "/inboxes/{inbox_id}/conversations", response_model=List[ConversationSearchResult]
)
async def get_inbox_conversations(
    inbox_id: UUID,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """Return all conversations for a specific inbox.

    Args:
        inbox_id (UUID): The ID of the inbox.
        limit (int, optional): The number of conversations to return. Defaults to 20.
        offset (int, optional): The number of conversations to skip. Defaults to 0.
        db (AsyncSession, optional): The database session. Defaults to Depends(get_db).
        auth_context (AuthContext, optional): The authentication context. Defaults to Depends(get_auth_context).

    Returns:
        List[ConversationSearchResult]: A list of conversations.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id
    logger.info(f"Getting conversations for inbox_id {inbox_id}")

    conversations = await conversation_repo.find_conversations_by_inbox(
        db=db,
        inbox_id=inbox_id,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )

    return conversations_to_conversations_response(conversations)


@router.post(
    "/inboxes/{inbox_id}/conversations", response_model=StartConversationResponse
)
async def start_conversation(
    inbox_id: UUID,
    payload: StartConversationRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """Start a new conversation in a specific inbox.

    Args:
        inbox_id (UUID): The ID of the inbox.
        payload (StartConversationRequest): The data for the new conversation.
        db (AsyncSession, optional): The database session. Defaults to Depends(get_db).
        auth_context (AuthContext, optional): The authentication context. Defaults to Depends(get_auth_context).

    Returns:
        StartConversationResponse: The ID of the new conversation.
    Raises:
        HTTPException: If the inbox is not found or the user is not authorized.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    inbox = await inbox_repo.find_inbox_by_id_and_account(
        db=db, account_id=account_id, inbox_id=inbox_id
    )
    if not inbox or inbox.account_id != account_id:
        raise HTTPException(status_code=404, detail="Inbox not found or unauthorized")

    normalized_phone_number = normalize_phone_number(payload.phone_number)

    contact = await contact_repo.find_contact_by_identifier(
        db=db,
        account_id=account_id,
        identifier=normalized_phone_number,
    )

    if not contact:
        contact = await contact_repo.create_contact(
            db=db,
            account_id=account_id,
            contact_data=ContactCreate(
                phone_number=normalized_phone_number,
            ),
        )

    internal_source_id = f"frontend-{uuid4().hex}"

    contact_inbox = await contact_repo.get_or_create_contact_inbox(
        db=db,
        account_id=account_id,
        contact_id=contact.id,
        inbox_id=inbox.id,
        source_id=internal_source_id,
    )

    conversation: Conversation = await conversation_repo.get_or_create_conversation(
        db=db,
        account_id=account_id,
        inbox_id=inbox.id,
        contact_inbox_id=contact_inbox.id,
        status=inbox.initial_conversation_status,
    )

    try:
        logger.debug("[ws] publishing message to the channel....")
        await publish_to_account_conversations_ws(
            account_id,
            {
                "type": "new_conversation",
                "payload": jsonable_encoder(
                    parse_conversation_to_conversation_response(conversation)
                ),
            },
        )
    except Exception as e:
        logger.warning(
            f"[ws] Failed to publish conversation {conversation.id} to Redis: {e}"
        )

    return StartConversationResponse(conversation_id=conversation.id)


@router.put(
    "/conversations/{conversation_id}/status",
    response_model=ConversationSearchResult,
    summary="Update Conversation Status",
    description=(
        "Updates the status of a specific conversation. "
        "If setting status to CLOSED, also resets the unread count."
    ),
    status_code=status.HTTP_200_OK,
)
async def update_conversation_status_endpoint(
    conversation_id: UUID,
    payload: ConversationUpdateStatus = Body(...),
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> ConversationSearchResult:
    """
    Updates the status of a conversation and resets unread count if closing.

    Args:
        conversation_id (UUID): The UUID of the conversation to update.
        payload (ConversationUpdateStatus): Request body containing the new status.
        db (AsyncSession): Database session dependency.
        auth_context (AuthContext): Authentication context dependency.

    Returns:
        ConversationSearchResult: The updated conversation data.

    Raises:
        HTTPException: 404 if the conversation is not found.
        HTTPException: 500 if the update fails or an unexpected error occurs.
    """
    account_id = auth_context.account.id
    user_id = auth_context.user.id

    logger.info(
        f"User {user_id} attempting to update status of conversation {conversation_id} "
        f"to {payload.status} for account {account_id}"
    )

    # Use the single session provided by Depends(get_db) for all operations
    try:
        # 1. Update the status
        updated_conversation = await conversation_repo.update_conversation_status(
            db=db,
            conversation_id=conversation_id,
            new_status=payload.status,
            account_id=account_id,
        )

        if not updated_conversation:
            # Check if conversation exists at all before raising 500
            conv_exists = await conversation_repo.find_conversation_by_id(
                db=db, conversation_id=conversation_id, account_id=account_id
            )
            if not conv_exists:
                logger.warning(
                    f"Conversation {conversation_id} not found for account {account_id} during status update."
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )
            else:
                # Conversation exists, but update failed for some other reason
                logger.error(
                    f"Failed to update status for conversation {conversation_id}. "
                    f"Repository returned None despite conversation existing."
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update conversation status.",
                )

        logger.info(
            f"Successfully updated status for conversation {conversation_id} to {payload.status}."
        )

        # 2. Reset unread count if status is set to CLOSED
        final_conversation_state = (
            updated_conversation  # Start with the result of the status update
        )
        if payload.status == ConversationStatusEnum.CLOSED:
            logger.debug(
                f"Status set to CLOSED, resetting unread count for conversation {conversation_id}."
            )
            conv_after_reset = await conversation_repo.reset_conversation_unread_count(
                db=db,
                account_id=account_id,
                conversation_id=conversation_id,
            )
            if conv_after_reset:
                final_conversation_state = conv_after_reset  # Use the state after reset
                logger.info(f"Unread count reset for conversation {conversation_id}.")
            else:
                # Log warning but proceed, maybe count was already 0 or reset failed internally
                logger.warning(
                    f"Failed to reset unread count for closing conversation {conversation_id}. Using state after status update."
                )
                # Keep final_conversation_state as it was after the status update

        # 3. Broadcast the update via WebSockets
        try:
            # Use the final state (potentially after reset) for broadcasting
            parsed_conversation = parse_conversation_to_conversation_response(
                final_conversation_state
            )
            await publish_to_account_conversations_ws(
                account_id=account_id,
                data={
                    "type": "conversation_updated",
                    "payload": jsonable_encoder(parsed_conversation),
                },
            )
            logger.debug(
                f"[ws] Published conversation_updated event for {conversation_id} after status change."
            )
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(
                f"[ws] Failed to publish status update for conversation {conversation_id} to WebSocket: {e}"
            )

        # 4. Prepare and return the response
        # Use the final state for the response as well
        response_data = parse_conversation_to_conversation_response(
            final_conversation_state
        )
        logger.info(
            f"Prepared response for conversation {conversation_id} status update."
        )
        return response_data

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions directly
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.exception(
            f"Unexpected error updating status for conversation {conversation_id}: {e}"
        )
        # FastAPI's dependency injection handles rollback on the session 'db'
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the conversation status.",
        )
