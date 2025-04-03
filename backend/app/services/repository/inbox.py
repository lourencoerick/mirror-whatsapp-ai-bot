from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any
from loguru import logger

from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember
from app.api.schemas.inbox import InboxCreate, InboxUpdate


async def find_inbox_by_id_and_account(
    db: AsyncSession, *, inbox_id: UUID, account_id: UUID
) -> Optional[Inbox]:
    """
    Finds a specific inbox by its ID, ensuring it belongs to the given account.

    Args:
        db: Asynchronous database session.
        inbox_id: The ID of the inbox to find.
        account_id: The ID of the account that must own the inbox.

    Returns:
        The Inbox object if found and authorized, otherwise None.
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


async def find_inbox_by_channel_id(
    db: AsyncSession, *, account_id: UUID, channel_id: str
) -> Optional[Inbox]:
    """
    Retrieve an inbox by channel_id and account_id.
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
    """
    Retrieves all inboxes belonging to a specific account with pagination.

    Args:
        db: Asynchronous database session.
        account_id: The ID of the account whose inboxes to retrieve.
        limit: Maximum number of inboxes to return.
        offset: Number of inboxes to skip.

    Returns:
        A list of Inbox objects.
    """
    logger.debug(
        f"[InboxRepo] Finding all inboxes for Account={account_id} (limit={limit}, offset={offset})"
    )
    result = await db.execute(
        select(Inbox)
        .filter(Inbox.account_id == account_id)
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
    """
    Fetch all inboxes within a specific account where the user is a member.
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
    """
    Creates a new inbox for the specified account.

    Args:
        db: Asynchronous database session.
        account_id: The ID of the account to associate the inbox with.
        user_id: The ID of the user creating the inbox (for InboxMember).
        inbox_data: Pydantic schema containing the inbox creation data.

    Returns:
        The newly created Inbox object.
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
    try:
        await db.commit()
        await db.refresh(new_inbox)
        await db.refresh(inbox_member)
        logger.info(f"[InboxRepo] Successfully created Inbox ID={new_inbox.id}")
        return new_inbox
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to create inbox for Account={account_id}")
        await db.rollback()
        raise


async def update_inbox(
    db: AsyncSession, *, inbox: Inbox, update_data: InboxUpdate
) -> Inbox:
    """
    Updates an existing inbox with new data.

    Args:
        db: Asynchronous database session.
        inbox: The existing Inbox object to update (must be fetched first).
        update_data: Pydantic schema containing the fields to update.

    Returns:
        The updated Inbox object.
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

    try:
        await db.commit()
        await db.refresh(inbox)
        logger.info(f"[InboxRepo] Successfully updated Inbox ID={inbox.id}")
        return inbox
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to update Inbox ID={inbox.id}")
        await db.rollback()
        raise


async def delete_inbox(db: AsyncSession, *, inbox: Inbox) -> bool:
    """
    Deletes an existing inbox.

    Args:
        db: Asynchronous database session.
        inbox: The existing Inbox object to delete (must be fetched first).

    Returns:
        True if deletion was successful, False otherwise (though errors usually raise exceptions).
    """
    inbox_id = inbox.id
    logger.warning(f"[InboxRepo] Attempting to delete Inbox ID={inbox_id}")
    try:
        await db.delete(inbox)
        await db.commit()
        logger.info(f"[InboxRepo] Successfully deleted Inbox ID={inbox_id}")
        return True
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to delete Inbox ID={inbox_id}")
        await db.rollback()
        raise
