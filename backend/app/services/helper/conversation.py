from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.models.message import Message
from app.models.conversation import Conversation


def update_last_message_snapshot(
    db: Session, conversation: Conversation, message: Message
) -> None:
    """
    Updates the conversation with a snapshot of the last message and its timestamp.

    Args:
        conversation (Conversation): The conversation to update.
        message (Message): The new message triggering the update.
    """

    snapshot = {
        "id": str(message.id),
        "content": message.content,
        "timestamp": (message.sent_at.isoformat() if message.sent_at else None),
        "direction": message.message_type,
        "content_type": message.content_type,
    }

    # Update additional_attributes safely
    if conversation.additional_attributes is None:
        conversation.additional_attributes = {}

    conversation.additional_attributes["last_message"] = snapshot

    if message.contact and message.contact.name:
        conversation.additional_attributes["contact_name"] = message.contact.name
        conversation.additional_attributes["phone_number"] = (
            message.contact.phone_number
        )
        conversation.additional_attributes["profile_picture_url"] = (
            message.contact.profile_picture_url
        )
    flag_modified(conversation, "additional_attributes")

    conversation.last_message_at = message.sent_at

    db.commit()
    db.refresh(conversation)

    logger.debug(
        f"[conversation] Updated snapshot and timestamp for conversation {conversation.id}"
    )
