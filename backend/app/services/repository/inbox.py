from uuid import UUID, uuid4
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any
from loguru import logger

from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember
from app.api.schemas.inbox import InboxCreate, InboxUpdate


def find_inbox_by_id_and_account(  # Renomeada e account_id obrigatório
    db: Session, *, inbox_id: UUID, account_id: UUID
) -> Optional[Inbox]:
    """
    Finds a specific inbox by its ID, ensuring it belongs to the given account.

    Args:
        db: Database session.
        inbox_id: The ID of the inbox to find.
        account_id: The ID of the account that must own the inbox.

    Returns:
        The Inbox object if found and authorized, otherwise None.
    """
    logger.debug(f"[InboxRepo] Finding inbox by ID={inbox_id} for Account={account_id}")
    inbox = (
        db.query(Inbox)
        .filter(Inbox.id == inbox_id, Inbox.account_id == account_id)
        .first()
    )

    if not inbox:
        logger.warning(
            f"[InboxRepo] Inbox ID={inbox_id} not found or not authorized for Account={account_id}"
        )
    return inbox


def find_inbox_by_channel_id(
    db: Session, *, account_id: UUID, channel_id: str
) -> Optional[Inbox]:
    """
    Retrieve an inbox by channel_id and account_id.
    """
    logger.debug(
        f"[InboxRepo] Finding inbox by ChannelID={channel_id} for Account={account_id}"
    )
    inbox = (
        db.query(Inbox).filter_by(account_id=account_id, channel_id=channel_id).first()
    )

    if inbox:
        logger.debug(
            f"[InboxRepo] Found inbox (id={inbox.id}) for channel_id {channel_id}"
        )
    else:
        logger.info(
            f"[InboxRepo] No inbox found for channel_id {channel_id} (account_id={account_id})"
        )
    return inbox


def find_inboxes_by_account(
    db: Session, *, account_id: UUID, limit: int = 100, offset: int = 0
) -> List[Inbox]:
    """
    Retrieves all inboxes belonging to a specific account with pagination.

    Args:
        db: Database session.
        account_id: The ID of the account whose inboxes to retrieve.
        limit: Maximum number of inboxes to return.
        offset: Number of inboxes to skip.

    Returns:
        A list of Inbox objects.
    """
    logger.debug(
        f"[InboxRepo] Finding all inboxes for Account={account_id} (limit={limit}, offset={offset})"
    )
    inboxes = (
        db.query(Inbox)
        .filter(Inbox.account_id == account_id)
        .order_by(Inbox.name)
        .limit(limit)
        .offset(offset)
        .all()
    )
    logger.info(f"[InboxRepo] Found {len(inboxes)} inboxes for Account={account_id}")
    return inboxes


def find_inboxes_by_user_membership(  # Renomeada de find_all_by_user para clareza
    db: Session, *, user_id: UUID, account_id: UUID
) -> List[Inbox]:
    """
    Fetch all inboxes within a specific account where the user is a member.
    """
    logger.debug(
        f"[InboxRepo] Finding inboxes for User={user_id} in Account={account_id} via membership"
    )
    inboxes = (
        db.query(Inbox)
        .join(InboxMember, Inbox.id == InboxMember.inbox_id)
        .filter(
            InboxMember.user_id == user_id,
            Inbox.account_id == account_id,
        )
        .order_by(Inbox.name)
        .all()
    )
    logger.info(
        f"[InboxRepo] Found {len(inboxes)} inboxes for User={user_id} via membership in Account={account_id}"
    )
    return inboxes


def create_inbox(
    db: Session, *, account_id: UUID, user_id: UUID, inbox_data: InboxCreate
) -> Inbox:
    """
    Creates a new inbox for the specified account.

    Args:
        db: Database session.
        account_id: The ID of the account to associate the inbox with.
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
        channel_id=f"{inbox_data.channel_type}-{uuid4().hex[:8]}",
        # TODO: Define how channel_id is truly generated or set
    )
    inbox_member = InboxMember(user_id=user_id, inbox_id=new_inbox.id)

    db.add_all([new_inbox, inbox_member])
    try:
        db.commit()
        db.refresh(new_inbox)
        db.refresh(new_inbox)
        logger.info(f"[InboxRepo] Successfully created Inbox ID={new_inbox.id}")
        return new_inbox
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to create inbox for Account={account_id}")
        db.rollback()
        raise


def update_inbox(db: Session, *, inbox: Inbox, update_data: InboxUpdate) -> Inbox:
    """
    Updates an existing inbox with new data.

    Args:
        db: Database session.
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
        db.add(inbox)
        db.commit()
        db.refresh(inbox)
        logger.info(f"[InboxRepo] Successfully updated Inbox ID={inbox.id}")
        return inbox
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to update Inbox ID={inbox.id}")
        db.rollback()
        raise


def delete_inbox(db: Session, *, inbox: Inbox) -> bool:
    """
    Deletes an existing inbox.

    Args:
        db: Database session.
        inbox: The existing Inbox object to delete (must be fetched first).

    Returns:
        True if deletion was successful, False otherwise (though errors usually raise exceptions).
    """
    inbox_id = inbox.id
    logger.warning(f"[InboxRepo] Attempting to delete Inbox ID={inbox_id}")
    try:
        db.delete(inbox)
        db.commit()
        logger.info(f"[InboxRepo] Successfully deleted Inbox ID={inbox_id}")
        return True
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to delete Inbox ID={inbox_id}")
        db.rollback()
        raise
