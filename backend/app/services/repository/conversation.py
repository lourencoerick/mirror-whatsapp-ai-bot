from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger
from app.models.conversation_models import Conversation
from app.api.schemas.message_schema import MessageCreate


def find_conversation(
    db: Session, account_id: int, inbox_id: int, contact_inbox_id: int
) -> Optional[Conversation]:
    """
    Retrieve a conversation for a contact within an inbox and account.
    """
    if not all([account_id, inbox_id, contact_inbox_id]):
        logger.warning("[conversation] Missing required parameters for lookup")
        return None

    conversation = (
        db.query(Conversation)
        .filter_by(
            account_id=account_id,
            inbox_id=inbox_id,
            contact_inbox_id=contact_inbox_id,
        )
        .first()
    )

    if conversation:
        logger.debug(f"[conversation] Found conversation (id={conversation.id})")
    else:
        logger.info(
            f"[conversation] No conversation found for contact_inbox_id {contact_inbox_id}"
        )

    return conversation


def get_or_create_conversation(
    db: Session, account_id: int, inbox_id: int, contact_inbox_id: int
) -> Conversation:
    """
    Find or create a conversation for a given contact in an inbox.
    """
    conversation = find_conversation(db, account_id, inbox_id, contact_inbox_id)

    if conversation:
        return conversation

    logger.info(
        f"[conversation] Creating new conversation for contact_inbox_id {contact_inbox_id}"
    )
    conversation = Conversation(
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        status="open",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.debug(f"[conversation] Created conversation (id={conversation.id})")
    return conversation


def update_last_message_snapshot(
    db: Session, conversation: Conversation, message: MessageCreate
) -> None:
    """
    Store a lightweight snapshot of the last message into the conversation's additional_attributes field.
    """
    snapshot = {
        "id": message.source_id,
        "content": message.content,
        "timestamp": message.message_timestamp.isoformat(),
        "content_type": message.content_type,
        "direction": message.direction,
    }

    if conversation.additional_attributes is None:
        conversation.additional_attributes = {}

    conversation.additional_attributes["last_message"] = snapshot
    db.commit()
    db.refresh(conversation)

    logger.debug(
        f"[conversation] Updated last_message snapshot for conversation {conversation.id}"
    )
