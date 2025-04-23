from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

# Repository imports
from app.services.repository import inbox as inbox_repo
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo
from app.services.repository import message as message_repo


async def reset_simulation_conversation(
    db: AsyncSession, account_id: UUID, inbox_id: UUID, contact_identifier: str
):
    """
    Resets a conversation for a given contact identifier and inbox by deleting
    all its messages and optionally resetting conversation status.

    Args:
        db: The SQLAlchemy async session.
        account_id: The account ID.
        inbox_id: The inbox ID.
        contact_identifier: The unique identifier of the contact.
    """
    inbox = await inbox_repo.find_inbox_by_id_and_account(
        db, inbox_id=inbox_id, account_id=account_id
    )
    logger.info(
        f"Attempting to reset conversation for contact '{contact_identifier}' in inbox '{inbox.id}'"
    )

    if not inbox:
        raise ValueError(f"Inbox {inbox_id} not found. Cannot reset conversation.")

    # Find contact
    contact = await contact_repo.find_contact_by_identifier(
        db, account_id=account_id, identifier=contact_identifier
    )
    if not contact:
        logger.warning(f"No contact found for identifier '{contact_identifier}'.")
        return

    # Find conversation
    conversation = await conversation_repo.find_conversation_by_contact_inbox(
        db, contact_id=contact.id, inbox_id=inbox.id
    )
    if not conversation:
        logger.warning(
            f"No conversation found for contact '{contact.id}' in inbox '{inbox.id}'."
        )
        return

    # Delete messages
    try:
        deleted_count = await message_repo.delete_messages_by_conversation(
            db, conversation_id=conversation.id
        )
        if deleted_count:
            logger.info(
                f"Deleted {deleted_count} messages for conversation '{conversation.id}'."
            )
        else:
            logger.info(f"No messages to delete for conversation '{conversation.id}'.")

        # Reset status and snapshot if they've changed
        if (
            conversation.status != inbox.initial_conversation_status
            or conversation.additional_attributes is not None
        ):
            logger.info(
                f"Resetting conversation '{conversation.id}' status to "
                f"'{inbox.initial_conversation_status}' and clearing snapshot."
            )
            conversation.status = inbox.initial_conversation_status
            conversation.additional_attributes = {}
            conversation.unread_agent_count = 0
            conversation.unread_user_count = 0
            db.add(conversation)
            await db.flush()
            logger.info(f"Conversation '{conversation.id}' status and snapshot reset.")

    except Exception as e:
        logger.error(
            f"Failed to reset conversation for contact '{contact.id}' in inbox '{inbox.id}': {e}"
        )
        raise
