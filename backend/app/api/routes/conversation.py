from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
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
            async with db as session:
                conversations = await conversation_repo.find_conversations_by_user(
                    db=session,
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

    async with db as session:
        conversations = await conversation_repo.find_conversations_by_inbox(
            db=session,
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

    async with db as session:
        inbox = await inbox_repo.find_inbox_by_id_and_account(
            db=session, account_id=account_id, inbox_id=inbox_id
        )
        if not inbox or inbox.account_id != account_id:
            raise HTTPException(
                status_code=404, detail="Inbox not found or unauthorized"
            )

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
            db=session,
            account_id=account_id,
            contact_id=contact.id,
            inbox_id=inbox.id,
            source_id=internal_source_id,
        )

        conversation: Conversation = await conversation_repo.get_or_create_conversation(
            db=session,
            account_id=account_id,
            inbox_id=inbox.id,
            contact_inbox_id=contact_inbox.id,
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
    response_model=ConversationSearchResult,  # Use the same response as list/search for consistency
    summary="Update Conversation Status",
    description="Updates the status of a specific conversation.",
    status_code=status.HTTP_200_OK,  # OK for successful update
)
async def update_conversation_status_endpoint(
    conversation_id: UUID,
    payload: ConversationUpdateStatus = Body(...),  # Use Body for the request payload
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Updates the status of a conversation identified by its ID.

    - **conversation_id**: The UUID of the conversation to update.
    - **payload**: Request body containing the new status.
    """
    account_id = auth_context.account.id
    user_id = auth_context.user.id  # For potential permission checks later

    logger.info(
        f"User {user_id} attempting to update status of conversation {conversation_id} to {payload.status} for account {account_id}"
    )

    # Optional: Add fine-grained permission check here.
    # Does the user have permission to modify this specific conversation?
    # (e.g., check if they are assigned, or admin, or member of the inbox)
    # For now, we rely on the repository potentially checking account_id implicitly or explicitly.

    try:
        # Call the repository function to perform the update
        updated_conversation = await conversation_repo.update_conversation_status(
            db=db,
            conversation_id=conversation_id,
            new_status=payload.status,
            account_id=account_id,
            # Consider adding account_id to the repo function signature
            # for an extra layer of security/filtering within the query itself.
            # e.g., .where(Conversation.id == conversation_id, Conversation.account_id == account_id)
        )

        if not updated_conversation:
            # To be more specific, check if the conversation exists at all first
            # This prevents leaking information about existence vs. update failure
            conv_exists = await conversation_repo.find_conversation_by_id(
                db=db, conversation_id=conversation_id, account_id=account_id
            )
            if not conv_exists:
                logger.warning(
                    f"Conversation {conversation_id} not found for account {account_id}."
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )
            else:
                # Conversation exists, but update failed (e.g., DB error handled in repo, or status unchanged)
                logger.error(
                    f"Failed to update status for conversation {conversation_id}. Repo returned None."
                )
                # This case might indicate an issue in the repo logic or DB state
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update conversation status.",
                )

        # --- WebSocket Broadcast Placeholder ---
        # TODO: After successful update, broadcast the change via WebSockets
        # Example:
        # await broadcast_conversation_update(
        #     account_id=account_id,
        #     conversation_data={
        #         "id": updated_conversation.id,
        #         "status": updated_conversation.status,
        #         "unread_agent_count": updated_conversation.unread_agent_count,
        #         "updated_at": updated_conversation.updated_at
        #     }
        # )
        logger.info(
            f"Successfully updated status for conversation {conversation_id}. Preparing response."
        )
        # --- End WebSocket Placeholder ---

        # Commit the transaction before returning the response
        await db.commit()
        logger.debug(
            f"Committed transaction for conversation {conversation_id} status update."
        )

        # Parse the updated ORM object to the response schema
        response_data = parse_conversation_to_conversation_response(
            updated_conversation
        )
        return response_data

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly
        await db.rollback()  # Rollback on known errors
        raise http_exc
    except Exception as e:
        # Catch unexpected errors
        await db.rollback()  # Rollback on unexpected errors
        logger.exception(
            f"Unexpected error updating status for conversation {conversation_id}: {e}"
        )  # Use logger.exception to include traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the conversation status.",
        )
