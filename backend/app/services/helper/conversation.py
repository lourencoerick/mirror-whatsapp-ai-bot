from loguru import logger
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.models.message import Message
from app.api.schemas.conversation import ConversationResponse, LastMessage
from app.models.conversation import Conversation
from app.services.repository import contact as contact_repo


async def update_last_message_snapshot(
    db: AsyncSession, conversation: Conversation, message: Message
) -> None:
    """
    Updates the conversation with a snapshot of the last message and its timestamp.

    Args:
        db (AsyncSession): Asynchronous database session.
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

    contact = await contact_repo.find_contact_by_id(
        db=db, account_id=message.account_id, contact_id=message.contact_id
    )

    if contact and contact.name and message.direction == "in":
        conversation.additional_attributes["contact_name"] = contact.name
        conversation.additional_attributes["phone_number"] = contact.phone_number
        conversation.additional_attributes["profile_picture_url"] = (
            contact.profile_picture_url
        )
    flag_modified(conversation, "additional_attributes")

    conversation.last_message_at = message.sent_at

    await db.commit()
    await db.refresh(conversation)

    logger.debug(
        f"[conversation] Updated snapshot and timestamp for conversation {conversation.id}"
    )


def parse_conversation_to_conversation_response(
    conversation: Conversation,
) -> ConversationResponse:
    """parses a conversation to a conversation response

    Args:
        conversation (Conversation): conversation

    Returns:
        ConversationResponse: _description_
    """
    attrs = conversation.additional_attributes or {}
    last_message = attrs.get("last_message", {})
    return ConversationResponse(
        id=conversation.id,
        updated_at=conversation.updated_at,
        phone_number=attrs.get("phone_number", ""),
        contact_name=attrs.get("contact_name"),
        profile_picture_url=attrs.get("profile_picture_url"),
        last_message_at=conversation.last_message_at,
        last_message=(
            LastMessage(content=last_message.get("content", ""))
            if last_message
            else None
        ),
    )


def conversations_to_conversations_response(
    conversations: List[Conversation],
) -> List[ConversationResponse]:
    """pares a list of conversations to a list of conversation response

    Args:
        conversations (List[Conversation]): list of conversations

    Returns:
        List[ConversationResponse]: list of conversations response
    """
    response = []
    for conv in conversations:
        response.append(parse_conversation_to_conversation_response(conv))
    return response
