from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from loguru import logger

from app.database import get_db
from app.middleware.account_context import get_account_id
from app.api.schemas.conversation import ConversationResponse, LastMessage
from app.services.repository.conversation import find_conversations_by_inbox

router = APIRouter()


@router.get(
    "/inboxes/{inbox_id}/conversations", response_model=List[ConversationResponse]
)
def get_conversations(
    inbox_id: int, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
):
    logger.info(f"Getting conversations for inbox_id {inbox_id}")
    conversations = find_conversations_by_inbox(
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
                last_message_at=attrs.get("last_message_at"),
                last_message=(
                    LastMessage(
                        content=last_message.get("content", ""),
                        created_at=last_message.get("created_at"),
                    )
                    if last_message
                    else None
                ),
            )
        )
    return response
