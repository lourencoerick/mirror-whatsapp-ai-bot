from uuid import UUID
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger
from app.models.contact import Contact
from app.models.contact__inbox import ContactInbox


def find_by_phone(
    db: Session, account_id: UUID, phone_number: str
) -> Optional[Contact]:
    if not all([account_id, phone_number]):
        logger.warning("[contact] Missing required parameters for lookup")
        return None

    contact = (
        db.query(Contact)
        .filter_by(account_id=account_id, phone_number=phone_number)
        .first()
    )

    if contact:
        logger.debug(
            f"[contact] Found contact (id={contact.id}) for phone {phone_number}"
        )
    else:
        logger.info(f"[contact] No contact found for phone {phone_number}")

    return contact


def upsert_contact(
    db: Session,
    account_id: UUID,
    phone_number: str,
    name: Optional[str] = None,
) -> Contact:
    """
    Find or create a contact, and update name if provided.
    """
    contact = find_by_phone(db, account_id, phone_number)

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

    db.commit()
    db.refresh(contact)
    logger.debug(f"[contact] Contact upsert complete (id={contact.id})")
    return contact


def get_or_create_contact_inbox(
    db: Session,
    contact_id: UUID,
    inbox_id: UUID,
    source_id: UUID,
) -> ContactInbox:
    """
    Find or create a ContactInbox association between a contact and an inbox.
    """
    contact_inbox = (
        db.query(ContactInbox)
        .filter_by(contact_id=contact_id, inbox_id=inbox_id)
        .first()
    )

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
        db.commit()
        db.refresh(contact_inbox)

    else:
        logger.debug(f"[contact_inbox] Found contact_inbox (id={contact_inbox.id})")

    return contact_inbox
