from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger
from app.models.contact import Contact
from app.models.contact_inbox import ContactInbox
from sqlalchemy import select


async def find_contact_by_id(
    db: AsyncSession, account_id: UUID, contact_id: str
) -> Optional[Contact]:
    """Finds a contact by phone number.

    Args:
        db (AsyncSession): Database session.
        account_id (UUID): The ID of the account.
        contact_id (UUID): The contact ID.

    Returns:
        Optional[Contact]: The Contact object if found, otherwise None.
    """
    if not all([account_id, contact_id]):
        logger.warning("[contact] Missing required parameters for lookup")
        return None

    result = await db.execute(
        select(Contact).filter_by(account_id=account_id, id=contact_id)
    )
    contact = result.scalar_one_or_none()

    if contact:
        logger.debug(f"[contact] Found contact (id={contact.id})")
    else:
        logger.info(f"[contact] No contact found {contact_id}")

    return contact


async def find_contact_by_phone(
    db: AsyncSession, account_id: UUID, phone_number: str
) -> Optional[Contact]:
    """Finds a contact by phone number.

    Args:
        db (AsyncSession): Database session.
        account_id (UUID): The ID of the account.
        phone_number (str): The phone number to search for.

    Returns:
        Optional[Contact]: The Contact object if found, otherwise None.
    """
    if not all([account_id, phone_number]):
        logger.warning("[contact] Missing required parameters for lookup")
        return None

    result = await db.execute(
        select(Contact).filter_by(account_id=account_id, phone_number=phone_number)
    )
    contact = result.scalar_one_or_none()

    if contact:
        logger.debug(
            f"[contact] Found contact (id={contact.id}) for phone {phone_number}"
        )
    else:
        logger.info(f"[contact] No contact found for phone {phone_number}")

    return contact


async def upsert_contact(
    db: AsyncSession,
    account_id: UUID,
    phone_number: str,
    name: Optional[str] = None,
) -> Contact:
    """Finds or creates a contact, and update name if provided.

    Args:
        db (AsyncSession): Database session.
        account_id (UUID): The ID of the account.
        phone_number (str): The phone number of the contact.
        name (Optional[str], optional): The name of the contact. Defaults to None.

    Returns:
        Contact: The Contact object.
    """
    contact = await find_contact_by_phone(db, account_id, phone_number)

    if not contact:
        logger.info(f"[contact] Creating contact for phone {phone_number}")
        contact = Contact(
            account_id=account_id,
            phone_number=phone_number,
            name=name,
        )
        db.add(contact)

    elif name and not contact.name:
        logger.info(f"[contact] Updating contact name for phone {phone_number}")
        contact.name = name

    await db.flush()
    await db.commit()
    await db.refresh(contact)
    logger.debug(f"[contact] Contact upsert complete (id={contact.id})")
    return contact


async def get_or_create_contact_inbox(
    db: AsyncSession,
    contact_id: UUID,
    inbox_id: UUID,
    source_id: UUID,
) -> ContactInbox:
    """Finds or creates a ContactInbox association between a contact and an inbox.

    Args:
        db (AsyncSession): Database session.
        contact_id (UUID): The ID of the contact.
        inbox_id (UUID): The ID of the inbox.
        source_id (UUID): The source ID.

    Returns:
        ContactInbox: The ContactInbox object.
    """
    result = await db.execute(
        select(ContactInbox).filter_by(contact_id=contact_id, inbox_id=inbox_id)
    )
    contact_inbox = result.scalar_one_or_none()

    if not contact_inbox:
        logger.info(
            f"[contact_inbox] Creating contact_inbox for contact_id={contact_id} and inbox_id={inbox_id}"
        )
        contact_inbox = ContactInbox(
            contact_id=contact_id,
            inbox_id=inbox_id,
            source_id=source_id,
        )
        db.add(contact_inbox)
        await db.flush()
        await db.commit()
        await db.refresh(contact_inbox)

    else:
        logger.debug(f"[contact_inbox] Found contact_inbox (id={contact_inbox.id})")

    return contact_inbox
