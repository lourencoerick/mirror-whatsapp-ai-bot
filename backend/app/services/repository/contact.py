from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Type, Dict, Any
from loguru import logger
from sqlalchemy import select, func, or_, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.contact import Contact
from app.models.contact_inbox import ContactInbox
from app.api.schemas.contact import ContactCreate, ContactUpdate
from app.services.helper.contact import normalize_phone_number


ALLOWED_SORT_FIELDS: Dict[str, Any] = {
    "name": Contact.name,
    "email": Contact.email,
    "phone_number": Contact.phone_number,
    "created_at": Contact.created_at,
}
DEFAULT_SORT_FIELD = Contact.name


async def find_contact_by_id(
    db: AsyncSession, account_id: UUID, contact_id: str
) -> Optional[Contact]:
    """Finds an *active* contact by ID."""  # Modified docstring
    if not all([account_id, contact_id]):
        logger.warning("[contact] Missing required parameters for lookup")
        return None

    result = await db.execute(
        select(Contact).filter_by(
            account_id=account_id,
            id=contact_id,
            deleted_at=None,  # Added filter for active contacts
        )
    )
    contact = result.scalar_one_or_none()

    if contact:
        logger.debug(f"[contact] Found active contact (id={contact.id})")
    else:
        logger.info(f"[contact] No active contact found {contact_id}")

    return contact


async def find_contact_by_identifier(
    db: AsyncSession, *, identifier: str, account_id: UUID
) -> Optional[Contact]:
    """Retrieves an *active* contact by its normalized identifier and account ID."""  # Modified docstring

    result = await db.execute(
        select(Contact).filter(
            Contact.identifier == identifier,
            Contact.account_id == account_id,
            Contact.deleted_at.is_(None),  # Added filter for active contacts
        )
    )

    return result.scalar_one_or_none()


async def get_contacts(
    db: AsyncSession,
    account_id: UUID,
    offset: int,
    limit: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_direction: str = "asc",
) -> List[Contact]:
    """Fetches a paginated, filtered, and sorted list of *active* contacts."""  # Modified docstring

    # Added filter for active contacts
    stmt = select(Contact).where(
        Contact.account_id == account_id, Contact.deleted_at.is_(None)
    )

    # --- Apply Search Filter ---
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Contact.name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.phone_number.ilike(search_term),
            )
        )

    # --- Apply Sorting ---
    sort_column = DEFAULT_SORT_FIELD
    if sort_by and sort_by in ALLOWED_SORT_FIELDS:
        sort_column = ALLOWED_SORT_FIELDS[sort_by]

    if sort_direction == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())

    # --- Apply Pagination ---
    stmt = stmt.offset(offset).limit(limit)

    # --- Execute Query ---
    result = await db.execute(stmt)
    return result.scalars().all()


async def count_contacts(
    db: AsyncSession, account_id: UUID, search: Optional[str] = None
) -> int:
    """Counts *active* contacts matching the optional search filter."""

    # Added filter for active contacts
    stmt = select(func.count(Contact.id)).where(
        Contact.account_id == account_id, Contact.deleted_at.is_(None)
    )

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Contact.name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.phone_number.ilike(search_term),
            )
        )

    total = await db.scalar(stmt)
    return total or 0


async def create_contact(
    db: AsyncSession, *, contact_data: ContactCreate, account_id: UUID
) -> Contact:
    """Creates a new contact. Checks for conflicts only among *active* contacts."""

    normalized_phone = normalize_phone_number(contact_data.phone_number)
    if not normalized_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unparseable phone number: {contact_data.phone_number}",
        )

    # Check if identifier already exists for an *active* contact
    existing_contact = await find_contact_by_identifier(
        db=db, identifier=normalized_phone, account_id=account_id
    )
    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active contact with phone number {contact_data.phone_number} (normalized: {normalized_phone}) already exists.",
        )

    # Check for email conflict among *active* contacts (if email provided)
    # Assumes partial unique index on (account_id, email) WHERE deleted_at IS NULL
    if contact_data.email:
        existing_email_contact = await db.scalar(
            select(Contact).filter_by(
                account_id=account_id, email=contact_data.email, deleted_at=None
            )
        )
        if existing_email_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Active contact with email {contact_data.email} already exists.",
            )

    contact_data.phone_number = normalized_phone
    db_contact = Contact(
        **contact_data.model_dump(exclude_unset=True),
        account_id=account_id,
        identifier=normalized_phone,
    )
    db.add(db_contact)
    try:
        await db.commit()
        await db.refresh(db_contact)
    except IntegrityError as e:
        await db.rollback()
        logger.warning(
            f"Integrity error creating contact, possibly email/identifier conflict: {e}"
        )

        if contact_data.email and await db.scalar(
            select(Contact.id).filter_by(
                account_id=account_id, email=contact_data.email, deleted_at=None
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Active contact with email {contact_data.email} already exists.",
            )

        if await db.scalar(
            select(Contact.id).filter_by(
                account_id=account_id, identifier=normalized_phone, deleted_at=None
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Active contact with phone number {contact_data.phone_number} already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact creation failed due to a conflict.",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Database error creating contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create contact due to a database error.",
        )
    return db_contact


async def update_contact(
    db: AsyncSession, *, contact: Contact, update_data: ContactUpdate
) -> Contact:
    """Updates an existing *active* contact. Checks for conflicts only among other *active* contacts."""

    if contact.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot update a deleted contact.",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return contact

    # Check if phone number is being updated
    if "phone_number" in update_dict:
        new_phone_number = update_dict["phone_number"]
        if new_phone_number is None or new_phone_number == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number cannot be set to empty.",
            )
        new_normalized_phone = normalize_phone_number(new_phone_number)
        if not new_normalized_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or unparseable phone number provided for update: {new_phone_number}",
            )
        if new_normalized_phone != contact.identifier:
            # Check for conflict with another *active* contact
            existing_contact = await find_contact_by_identifier(
                db=db, identifier=new_normalized_phone, account_id=contact.account_id
            )
            if existing_contact and existing_contact.id != contact.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Another active contact with phone number {new_phone_number} (normalized: {new_normalized_phone}) already exists.",
                )
            update_dict["identifier"] = new_normalized_phone
            update_dict["phone_number"] = new_normalized_phone

    # Check if email is being updated and check for conflicts among *active* contacts
    if (
        "email" in update_dict
        and update_dict["email"] != contact.email
        and update_dict["email"]
    ):
        existing_email_contact = await db.scalar(
            select(Contact)
            .filter_by(
                account_id=contact.account_id,
                email=update_dict["email"],
                deleted_at=None,
            )
            .filter(Contact.id != contact.id)
        )
        if existing_email_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another active contact with email {update_dict['email']} already exists.",
            )

    for key, value in update_dict.items():
        setattr(contact, key, value)

    db.add(contact)
    try:
        await db.commit()
        await db.refresh(contact)
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error updating contact {contact.id}: {e}")

        if (
            "email" in update_dict
            and update_dict["email"]
            and await db.scalar(
                select(Contact.id)
                .filter_by(
                    account_id=contact.account_id,
                    email=update_dict["email"],
                    deleted_at=None,
                )
                .filter(Contact.id != contact.id)
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another active contact with email {update_dict['email']} already exists.",
            )
        if "identifier" in update_dict and await db.scalar(
            select(Contact.id)
            .filter_by(
                account_id=contact.account_id,
                identifier=update_dict["identifier"],
                deleted_at=None,
            )
            .filter(Contact.id != contact.id)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another active contact with phone number {update_dict.get('phone_number', '')} already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact update failed due to a conflict.",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Database error updating contact {contact.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update contact due to a database error.",
        )
    return contact


async def delete_contact(db: AsyncSession, *, contact: Contact) -> None:
    """Soft deletes a contact by setting the deleted_at timestamp."""

    if contact.deleted_at is not None:
        logger.warning(f"Attempted to delete already soft-deleted contact {contact.id}")
        return

    try:

        stmt = (
            update(Contact)
            .where(Contact.id == contact.id, Contact.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .execution_options(synchronize_session="fetch")
        )
        result = await db.execute(stmt)

        if result.rowcount == 0:
            logger.warning(
                f"Contact {contact.id} was not found or already deleted during soft delete operation."
            )

            await db.refresh(contact, attribute_names=["deleted_at"])
            if contact.deleted_at is None:

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to soft delete contact.",
                )
            return

        await db.commit()

        logger.info(f"Soft deleted contact {contact.id}")

    except Exception as e:
        await db.rollback()
        logger.error(f"Database error soft deleting contact {contact.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete contact due to a database error.",
        )


async def get_or_create_contact_inbox(
    db: AsyncSession,
    account_id: UUID,
    contact_id: UUID,
    inbox_id: UUID,
    source_id: UUID,
) -> ContactInbox:
    """Finds or creates a ContactInbox association. Assumes caller provides an *active* contact ID."""

    contact = await find_contact_by_id(db, account_id, contact_id)
    if not contact:
        raise HTTPException(
            status_code=404,
            detail="Cannot associate with a non-existent or deleted contact.",
        )

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

    else:
        logger.debug(f"[contact_inbox] Found contact_inbox (id={contact_inbox.id})")

    return contact_inbox
