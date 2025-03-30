from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import List
from loguru import logger

from app.database import get_db
from app.core.dependencies import get_auth_context, AuthContext
from app.api.schemas.conversation import (
    ConversationResponse,
    StartConversationResponse,
    StartConversationRequest,
)
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo
from app.services.repository import inbox as inbox_repo
from app.models.conversation import Conversation
from app.services.helper.websocket import publish_to_account_conversations_ws
from app.services.helper.conversation import (
    conversations_to_conversations_response,
    parse_conversation_to_conversation_response,
)


router = APIRouter()


@router.get("/conversations", response_model=List[ConversationResponse])
def get_user_conversations(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Return all conversations visible to the current user,
    based on inbox membership.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id
    conversations = conversation_repo.find_all_by_user(
        db=db,
        user_id=user_id,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )

    return conversations_to_conversations_response(conversations)


@router.get(
    "/inboxes/{inbox_id}/conversations", response_model=List[ConversationResponse]
)
def get_inbox_conversations(
    inbox_id: UUID, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
):
    logger.info(f"Getting conversations for inbox_id {inbox_id}")
    conversations = conversation_repo.find_conversations_by_inbox(
        db=db, inbox_id=inbox_id, limit=limit, offset=offset
    )

    return conversations_to_conversations_response(conversations)


@router.post(
    "/inboxes/{inbox_id}/conversations", response_model=StartConversationResponse
)
async def start_conversation(
    inbox_id: UUID,
    payload: StartConversationRequest,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    inbox = inbox_repo.find_by_id(db=db, account_id=account_id, inbox_id=inbox_id)
    if not inbox or inbox.account_id != account_id:
        raise HTTPException(status_code=404, detail="Inbox not found or unauthorized")

    contact = contact_repo.upsert_contact(
        db=db,
        account_id=account_id,
        phone_number=payload.phone_number,
    )

    internal_source_id = f"frontend-{uuid4().hex}"

    contact_inbox = contact_repo.get_or_create_contact_inbox(
        db=db,
        contact_id=contact.id,
        inbox_id=inbox.id,
        source_id=internal_source_id,
    )

    conversation: Conversation = conversation_repo.get_or_create_conversation(
        db=db,
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
