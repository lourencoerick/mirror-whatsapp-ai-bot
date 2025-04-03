from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, select
from typing import Optional, List
from loguru import logger
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.inbox_member import InboxMember


async def find_conversation_by_id(
    db: AsyncSession, conversation_id: UUID, account_id: UUID
) -> Optional[Conversation]:
    """Retrieves a conversation by ID.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        conversation_id (UUID): The ID of the conversation to retrieve.
        account_id (UUID): The ID of the account to which the conversation belongs.

    Returns:
        Optional[Conversation]: The conversation if found, otherwise None.
    """
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.contact_inbox))
        .options(selectinload(Conversation.inbox))
        .filter_by(id=conversation_id, account_id=account_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        logger.debug(f"[conversation] Found conversation {conversation.id}")
    else:
        logger.warning(f"[conversation] Not found: {conversation_id}")

    return conversation


async def find_conversations_by_inbox(
    db: AsyncSession,
    inbox_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Conversation]:
    """Retrieves a list of conversations for a specific inbox.

    Conversations are ordered by the timestamp of the last message
    in descending order, returning the most recent ones first.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        inbox_id (UUID): The identifier for the inbox.
        account_id (UUID): The account identifier.
        limit (int, optional): The maximum number of records to return (default is 20).
        offset (int, optional): The number of records to skip for pagination (default is 0).

    Returns:
        List[Conversation]: A list of Conversation objects.

    Raises:
        SQLAlchemyError: If an error occurs during the database query.
    """
    try:
        query = (
            select(Conversation)
            .options(
                joinedload(Conversation.contact_inbox).joinedload(ContactInbox.contact)
            )
            .filter(
                Conversation.account_id == account_id, Conversation.inbox_id == inbox_id
            )
            .order_by(desc(Conversation.last_message_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database query error: {e}")
        raise e


async def find_conversation(
    db: AsyncSession,
    inbox_id: UUID,
    contact_inbox_id: UUID,
    account_id: UUID,
) -> Optional[Conversation]:
    """Retrieves a conversation for a contact within an inbox and account.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        inbox_id (UUID): The ID of the inbox.
        contact_inbox_id (UUID): The ID of the contact inbox.
        account_id (UUID): The ID of the account.

    Returns:
        Optional[Conversation]: The conversation if found, otherwise None.
    """
    result = await db.execute(
        select(Conversation).filter_by(
            account_id=account_id,
            inbox_id=inbox_id,
            contact_inbox_id=contact_inbox_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        logger.debug(f"[conversation] Found conversation (id={conversation.id})")
    else:
        logger.info(
            f"[conversation] No conversation found for contact_inbox_id {contact_inbox_id}"
        )

    return conversation


async def get_or_create_conversation(
    db: AsyncSession,
    inbox_id: UUID,
    account_id: UUID,
    contact_inbox_id: UUID,
) -> Conversation:
    """Finds or creates a conversation for a given contact in an inbox.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        inbox_id (UUID): The ID of the inbox.
        account_id (UUID): The ID of the account.
        contact_inbox_id (UUID): The ID of the contact inbox.

    Returns:
        Conversation: The conversation object.
    """
    conversation = await find_conversation(
        db=db,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        account_id=account_id,
    )

    if conversation:
        return conversation

    logger.info(
        f"[conversation] Creating new conversation for contact_inbox_id {contact_inbox_id}"
    )

    result = await db.execute(
        select(ContactInbox)
        .options(joinedload(ContactInbox.contact))
        .filter_by(
            id=contact_inbox_id,
        )
    )
    contact_inbox: ContactInbox = result.scalar_one_or_none()

    additional_attributes: dict = {}
    additional_attributes["contact_name"] = contact_inbox.contact.name
    additional_attributes["phone_number"] = contact_inbox.contact.phone_number

    conversation = Conversation(
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        status="open",
        additional_attributes=additional_attributes,
    )
    db.add(conversation)
    await db.flush()
    await db.commit()
    await db.refresh(conversation)

    logger.debug(f"[conversation] Created conversation (id={conversation.id})")
    return conversation


async def find_conversations_by_user(
    db: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Conversation]:
    """Retrieves all conversations accessible to a given user based on inbox membership.

    Args:
        db (AsyncSession): SQLAlchemy AsyncSession.
        user_id (UUID): The user ID.
        account_id (UUID): The account ID.
        limit (int): Pagination limit.
        offset (int): Pagination offset.

    Returns:
        List[Conversation]: Conversations accessible to the user.
    """
    inbox_ids_subquery = (
        select(InboxMember.inbox_id).filter(InboxMember.user_id == user_id)
    ).scalar_subquery()

    logger.debug(f"Founded user inbox ids: {inbox_ids_subquery}")
    query = (
        select(Conversation)
        .options(
            selectinload(Conversation.contact_inbox).selectinload(ContactInbox.contact)
        )
        .filter(
            Conversation.account_id == account_id,
            Conversation.inbox_id.in_(inbox_ids_subquery),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()
    return conversations
