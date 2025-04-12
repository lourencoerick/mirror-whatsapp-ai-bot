from loguru import logger
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.models.message import Message
from app.api.schemas.conversation import ConversationSearchResult, MessageSnippet
from app.api.schemas.contact import ContactBase
from app.models.conversation import Conversation
from app.services.repository import contact as contact_repo


async def update_last_message_snapshot(
    db: AsyncSession, conversation: Conversation, message: Message
) -> None:
    """Update the conversation with a snapshot of the last message and its timestamp.

    Args:
        db (AsyncSession): Asynchronous database session.
        conversation (Conversation): The conversation to update.
        message (Message): The new message triggering the update.
    """
    snapshot = {
        "id": str(message.id),
        "content": message.content,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "direction": message.message_type,
        "content_type": message.content_type,
    }

    # Ensure additional_attributes exists for safe update
    if conversation.additional_attributes is None:
        conversation.additional_attributes = {}

    conversation.additional_attributes["last_message"] = snapshot

    # Retrieve the contact using the repository (transaction management handled by caller)
    contact = await contact_repo.find_contact_by_id(
        db=db, account_id=message.account_id, contact_id=message.contact_id
    )

    # Update the snapshot with contact information if available and the message is incoming
    if contact and contact.name and message.direction == "in":
        conversation.additional_attributes["contact_name"] = contact.name
        conversation.additional_attributes["phone_number"] = contact.phone_number
        conversation.additional_attributes["profile_picture_url"] = (
            contact.profile_picture_url
        )

    # Notify SQLAlchemy that additional_attributes has been modified
    flag_modified(conversation, "additional_attributes")

    # Update the conversation's last message timestamp
    conversation.last_message_at = message.sent_at

    # Note: Transaction finalization (commit/refresh) should be performed by the upper layer.
    logger.debug(
        f"[conversation] Updated snapshot and timestamp for conversation {conversation.id}"
    )


def parse_conversation_to_conversation_response(
    conversation: Conversation,
) -> ConversationSearchResult:
    """parses a conversation to a conversation response

    Args:
        conversation (Conversation): conversation

    Returns:
        ConversationSearchResult: _description_
    """
    attrs = conversation.additional_attributes or {}
    last_message = attrs.get("last_message", {})
    return ConversationSearchResult(
        id=conversation.id,
        status=conversation.status,
        unread_agent_count=conversation.unread_agent_count,
        is_bot_active=conversation.is_bot_active,
        contact=ContactBase(
            name=attrs.get("contact_name"),
            phone_number=attrs.get("phone_number"),
            profile_picture_url=attrs.get("profile_picture_url"),
        ),
        last_message_at=conversation.last_message_at,
        last_message=(
            MessageSnippet(
                id=last_message.get("id", ""),
                content=last_message.get("content", ""),
                sent_at=last_message.get("sent_at", None),
            )
            if last_message
            else None
        ),
        updated_at=conversation.updated_at,
    )


def conversations_to_conversations_response(
    conversations: List[Conversation],
) -> List[ConversationSearchResult]:
    """pares a list of conversations to a list of conversation response

    Args:
        conversations (List[Conversation]): list of conversations

    Returns:
        List[ConversationSearchResult]: list of conversations response
    """
    response = []
    for conv in conversations:
        response.append(parse_conversation_to_conversation_response(conv))
    return response
