from typing import Dict, Optional
from loguru import logger
from sqlalchemy.orm import Session
from app.models.message_models import Message

# Constants (replace with Enums later if needed)
INCOMING = 1
OUTGOING = 2

VALID_DIRECTIONS = {
    "in": INCOMING,
    "out": OUTGOING,
}


def log_message(
    db: Session,
    *,
    content: str,
    direction: str,
    account_id: int,
    inbox_id: int,
    conversation_id: int,
    contact_id: Optional[int] = None,
    user_id: Optional[int] = None,
    source_id: Optional[str] = None,
    status: Optional[int] = None,
    content_attributes: Optional[Dict] = None,
    content_type: Optional[int] = None,
    private: Optional[bool] = False,
) -> Optional[Message]:
    """
    Saves a message record to the database.

    Args:
        db: SQLAlchemy session.
        content: Message body.
        direction: 'in' or 'out'.
        account_id, inbox_id, conversation_id: Context identifiers.
        contact_id, user_id: Optional references.
        source_id: Message ID from WhatsApp or external service.
        status: Optional message delivery status.
        content_attributes: Optional structured payload.
        content_type: Optional content type (text, media, etc.)

    Returns:
        The saved Message object, or None if failed.
    """
    logger.debug(f"[log_message] Payload received: {locals()}")
    try:
        if direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"Invalid direction '{direction}', expected 'in' or 'out'."
            )

        message_type = VALID_DIRECTIONS[direction]

        message = Message(
            account_id=account_id,
            inbox_id=inbox_id,
            conversation_id=conversation_id,
            contact_id=contact_id,
            user_id=user_id,
            content=content,
            message_type=message_type,
            content_type=content_type,
            source_id=source_id,
            content_attributes=content_attributes or {},
            status=status,
            private=private,
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        logger.debug(
            f"[log_message] Message logged: {message.id} (direction={direction})"
        )

        return message

    except Exception:
        logger.exception("[log_message] Failed to log message")
        return None
