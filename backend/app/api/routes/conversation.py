from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from loguru import logger

from app.database import get_db
from app.middleware.account_context import get_account_id
from app.api.schemas.conversation import (
    ConversationResponse,
    LastMessage,
    StartConversationResponse,
    StartConversationRequest,
)
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo
from app.services.repository import inbox as inbox_repo
from app.models.conversation import Conversation

router = APIRouter()


@router.get(
    "/inboxes/{inbox_id}/conversations", response_model=List[ConversationResponse]
)
def get_conversations(
    inbox_id: UUID, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
):
    logger.info(f"Getting conversations for inbox_id {inbox_id}")
    conversations = conversation_repo.find_conversations_by_inbox(
        db=db, inbox_id=inbox_id, limit=limit, offset=offset
    )

    response = []
    for conv in conversations:
        attrs = conv.additional_attributes or {}
        last_message = attrs.get("last_message", {})
        response.append(
            ConversationResponse(
                id=conv.id,
                phone_number=attrs.get("phone_number", ""),
                contact_name=attrs.get("contact_name"),
                profile_picture_url=attrs.get("profile_picture_url"),
                last_message_at=conv.last_message_at,
                last_message=(
                    LastMessage(
                        content=last_message.get("content", ""),
                    )
                    if last_message
                    else None
                ),
            )
        )
    return response


@router.post(
    "/inboxes/{inbox_id}/conversations", response_model=StartConversationResponse
)
def start_conversation(
    inbox_id: UUID,
    payload: StartConversationRequest,
    db: Session = Depends(get_db),
):
    account_id = get_account_id()

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

    return StartConversationResponse(conversation_id=conversation.id)
