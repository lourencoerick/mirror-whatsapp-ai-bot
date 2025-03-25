from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from loguru import logger
from app.models.message import Message
from app.api.schemas.message import MessageCreate


def find_messages_by_conversation(
    db: Session,
    conversation_id: int,
    limit: int = 20,
    offset: int = 0,
    account_id: int = None,
) -> List[Message]:
    """
    Retrieve messages belonging to a specific conversation, filtered by account.

    Args:
        db (Session): SQLAlchemy database session.
        conversation_id (int): The ID of the conversation.
        limit (int): Max number of messages to return (default: 20).
        offset (int): How many messages to skip (for pagination).
        account_id (int): The account context to enforce RLS isolation.

    Returns:
        List[Message]: A list of messages ordered by message timestamp ascending.
    """
    return (
        db.query(Message)
        .filter_by(account_id=account_id, conversation_id=conversation_id)
        .order_by(desc(Message.sent_at))
        .limit(limit)
        .offset(offset)
        .all()
    )


def get_or_create_message(db: Session, message_data: MessageCreate) -> Message:
    """
    Retrieve a message by inbox_id and source_id, or create one if it doesn't exist.
    Ensures idempotent message handling.
    """
    if not message_data.source_id:
        raise ValueError("source_id is required to identify messages")

    # Check for existing message
    message = (
        db.query(Message)
        .filter_by(inbox_id=message_data.inbox_id, source_id=message_data.source_id)
        .first()
    )

    if message:
        logger.debug(f"[message] Reusing existing message (id={message.id})")
        return message

    # Create new message
    new_message = Message(
        account_id=message_data.account_id,
        inbox_id=message_data.inbox_id,
        conversation_id=message_data.conversation_id,
        contact_id=message_data.contact_id,
        user_id=message_data.user_id,
        source_id=message_data.source_id,
        content=message_data.content,
        content_type=message_data.content_type,
        content_attributes=message_data.content_attributes,
        private=message_data.private,
        status=message_data.status,
        message_type=message_data.direction,
        timestamp=message_data.message_timestamp,
    )

    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    logger.info(f"[message] Created new message (id={new_message.id})")

    return new_message
