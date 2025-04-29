from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger

from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember
from app.models.bot_agent_inbox import BotAgentInbox
from app.api.schemas.inbox import InboxCreate, InboxUpdate
from app.models.conversation import ConversationStatusEnum


async def find_inbox_by_id_and_account(
    db: AsyncSession, *, inbox_id: UUID, account_id: UUID
) -> Optional[Inbox]:
    """Find a specific inbox by its ID and account.

    Args:
        db (AsyncSession): Asynchronous database session.
        inbox_id (UUID): The ID of the inbox to find.
        account_id (UUID): The ID of the account that must own the inbox.

    Returns:
        Optional[Inbox]: The Inbox object if found and authorized, otherwise None.
    """
    logger.debug(f"[InboxRepo] Finding inbox by ID={inbox_id} for Account={account_id}")
    result = await db.execute(
        select(Inbox).filter(Inbox.id == inbox_id, Inbox.account_id == account_id)
    )
    inbox = result.scalar_one_or_none()

    if not inbox:
        logger.warning(
            f"[InboxRepo] Inbox ID={inbox_id} not found or not authorized for Account={account_id}"
        )
    return inbox


async def find_inboxes_with_association_by_account(
    db: AsyncSession, *, account_id: UUID, limit: int = 100, offset: int = 0
) -> List[Tuple[Inbox, Optional[UUID]]]:
    """
    Retrieve all inboxes for an account, including the associated BotAgent ID.

    Args:
        db: The SQLAlchemy async session.
        account_id: The ID of the account whose inboxes to retrieve.
        limit: Maximum number of inboxes to return.
        offset: Number of inboxes to skip.

    Returns:
        A list of tuples, each containing (Inbox object, associated BotAgent UUID or None).
    """
    logger.debug(
        f"[InboxRepo] Finding inboxes with agent association for Account={account_id} (limit={limit}, offset={offset})"
    )
    stmt = (
        select(Inbox, BotAgentInbox.bot_agent_id)
        .outerjoin(
            BotAgentInbox,
            Inbox.id == BotAgentInbox.inbox_id,
        )
        .where(
            Inbox.account_id == account_id,
            Inbox.is_simulation.is_(False),
        )
        .order_by(Inbox.name)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    inboxes_with_assoc: List[Tuple[Inbox, Optional[UUID]]] = result.all()
    logger.info(
        f"[InboxRepo] Found {len(inboxes_with_assoc)} inboxes with association info for Account={account_id}"
    )
    return inboxes_with_assoc


async def find_inbox_by_channel_id(
    db: AsyncSession, *, account_id: UUID, channel_id: str
) -> Optional[Inbox]:
    """Retrieve an inbox by channel ID and account ID.

    Args:
        db (AsyncSession): Asynchronous database session.
        account_id (UUID): The account ID.
        channel_id (str): The channel identifier.

    Returns:
        Optional[Inbox]: The Inbox object if found, otherwise None.
    """
    logger.debug(
        f"[InboxRepo] Finding inbox by ChannelID={channel_id} for Account={account_id}"
    )
    result = await db.execute(
        select(Inbox).filter_by(account_id=account_id, channel_id=channel_id)
    )
    inbox = result.scalar_one_or_none()

    if inbox:
        logger.debug(
            f"[InboxRepo] Found inbox (id={inbox.id}) for channel_id {channel_id}"
        )
    else:
        logger.info(
            f"[InboxRepo] No inbox found for channel_id {channel_id} (account_id={account_id})"
        )
    return inbox


async def find_inboxes_by_account(
    db: AsyncSession, *, account_id: UUID, limit: int = 100, offset: int = 0
) -> List[Inbox]:
    """Retrieve all inboxes belonging to a specific account with pagination.

    Args:
        db (AsyncSession): Asynchronous database session.
        account_id (UUID): The ID of the account whose inboxes to retrieve.
        limit (int): Maximum number of inboxes to return.
        offset (int): Number of inboxes to skip.

    Returns:
        List[Inbox]: A list of Inbox objects.
    """
    logger.debug(
        f"[InboxRepo] Finding all inboxes for Account={account_id} (limit={limit}, offset={offset})"
    )
    result = await db.execute(
        select(Inbox)
        .filter(Inbox.account_id == account_id, Inbox.is_simulation.is_(False))
        .order_by(Inbox.name)
        .limit(limit)
        .offset(offset)
    )
    inboxes = result.scalars().all()
    logger.info(f"[InboxRepo] Found {len(inboxes)} inboxes for Account={account_id}")
    return inboxes


async def find_inboxes_by_user_membership(
    db: AsyncSession, *, user_id: UUID, account_id: UUID
) -> List[Inbox]:
    """Fetch all inboxes within a specific account where the user is a member.

    Args:
        db (AsyncSession): Asynchronous database session.
        user_id (UUID): The user ID.
        account_id (UUID): The account ID.

    Returns:
        List[Inbox]: A list of Inbox objects.
    """
    logger.debug(
        f"[InboxRepo] Finding inboxes for User={user_id} in Account={account_id} via membership"
    )
    result = await db.execute(
        select(Inbox)
        .join(InboxMember, Inbox.id == InboxMember.inbox_id)
        .filter(
            InboxMember.user_id == user_id,
            Inbox.account_id == account_id,
            Inbox.is_simulation.is_(False),
        )
        .order_by(Inbox.name)
    )
    inboxes = result.scalars().all()
    logger.info(
        f"[InboxRepo] Found {len(inboxes)} inboxes for User={user_id} via membership in Account={account_id}"
    )
    return inboxes


async def create_inbox(
    db: AsyncSession, *, account_id: UUID, user_id: UUID, inbox_data: InboxCreate
) -> Inbox:
    """Create a new inbox for the specified account without finalizing the transaction.

    The commit and refresh should be performed by the upper layer (e.g., service or endpoint).

    Args:
        db (AsyncSession): Asynchronous database session.
        account_id (UUID): The ID of the account to associate the inbox with.
        user_id (UUID): The ID of the user creating the inbox (for InboxMember).
        inbox_data (InboxCreate): Pydantic schema containing the inbox creation data.

    Returns:
        Inbox: The newly created Inbox object.

    Raises:
        Exception: Propagates any exception encountered (upper layer should handle rollback).
    """
    logger.info(
        f"[InboxRepo] Creating new inbox '{inbox_data.name}' for Account={account_id}"
    )
    new_inbox = Inbox(
        **inbox_data.model_dump(exclude_unset=True),
        account_id=account_id,
        channel_id=inbox_data.channel_details["id"],  # type: ignore
    )
    db.add(new_inbox)
    await db.flush()
    inbox_member = InboxMember(user_id=user_id, inbox_id=new_inbox.id)
    db.add(inbox_member)
    await db.flush()
    # Removed commit and refresh here; these are to be handled by the caller.
    logger.info(f"[InboxRepo] New inbox prepared with ID={new_inbox.id}")
    return new_inbox


async def update_inbox(
    db: AsyncSession, *, inbox: Inbox, update_data: InboxUpdate
) -> Inbox:
    """Update an existing inbox with new data without finalizing the transaction.

    The commit and refresh should be performed by the upper layer.

    Args:
        db (AsyncSession): Asynchronous database session.
        inbox (Inbox): The existing Inbox object to update.
        update_data (InboxUpdate): Pydantic schema containing the fields to update.

    Returns:
        Inbox: The updated Inbox object.
    """
    logger.info(f"[InboxRepo] Updating Inbox ID={inbox.id}")
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        logger.warning(
            f"[InboxRepo] Update called for Inbox ID={inbox.id} with no data."
        )
        return inbox

    for key, value in update_dict.items():
        setattr(inbox, key, value)

    # Removed commit and refresh here; these are to be handled by the caller.
    logger.info(f"[InboxRepo] Inbox ID={inbox.id} updated locally")
    return inbox


async def delete_inbox(db: AsyncSession, *, inbox: Inbox) -> bool:
    """Delete an existing inbox without finalizing the transaction.

    The commit should be performed by the upper layer.

    Args:
        db (AsyncSession): Asynchronous database session.
        inbox (Inbox): The existing Inbox object to delete.

    Returns:
        bool: True if deletion was prepared successfully, otherwise raises an exception.
    """
    inbox_id = inbox.id
    logger.warning(f"[InboxRepo] Attempting to delete Inbox ID={inbox_id}")
    try:
        await db.delete(inbox)
        # Removed commit here; finalization should be handled by the caller.
        logger.info(f"[InboxRepo] Inbox ID={inbox_id} marked for deletion")
        return True
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to delete Inbox ID={inbox_id}")
        raise e


async def update_intial_conversation_status(
    db: AsyncSession,
    *,
    account_id: UUID,
    inbox_id: UUID,
    new_status: ConversationStatusEnum = ConversationStatusEnum.BOT,
) -> None:
    """
    Updates the status of active conversations in a specific inbox that currently
    have a specific status (typically BOT).

    Args:
        db: The SQLAlchemy async session.
        account_id: The account ID to scope the update.
        inbox_id: The inbox ID where conversations should be updated.
        new_status: The new status to set (e.g., PENDING).
    Returns:
        The number of conversation rows updated.
    """
    logger.info(
        f"Updating inbox {inbox_id} (Account: {account_id}) " f"to '{new_status.value}'"
    )
    try:
        stmt = (
            update(Inbox)
            .where(Inbox.account_id == account_id, Inbox.id == inbox_id)
            .values(initial_conversation_status=new_status)
            # synchronize_session=False é geralmente recomendado para updates em massa com asyncio
            .execution_options(synchronize_session=False)
        )
        await db.execute(stmt)
        logger.info(f"Updated status for inbox {inbox_id} in Account {account_id}.")
        return None
    except Exception as e:
        logger.exception(
            f"Error updating Inbox initial conversation statuses  {account_id} "
            f"to {new_status.value}: {e}"
        )
        raise  # Re-lançar para rollback na camada superior
