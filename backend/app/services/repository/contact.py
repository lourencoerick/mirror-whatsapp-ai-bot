from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Type, Dict, Any
from loguru import logger
from sqlalchemy import select, func

from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.contact import Contact
from app.models.contact_inbox import ContactInbox
from app.api.schemas.contact import ContactCreate, ContactUpdate
from app.services.helper.contact import normalize_phone_number


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


async def find_contact_by_identifier(
    db: AsyncSession, *, identifier: str, account_id: UUID
) -> Optional[Contact]:
    """
    Retrieves a contact by its normalized identifier and account ID.

    Args:
        db: The SQLAlchemy Session object.
        identifier: The normalized phone number (E.164 format).
        account_id: The UUID of the account the contact belongs to.

    Returns:
        The Contact instance if found, otherwise None.
    """

    result = await db.execute(
        select(Contact).filter(
            Contact.identifier == identifier, Contact.account_id == account_id
        )
    )

    return result.scalar_one_or_none()


async def get_contacts(
    db: AsyncSession, *, account_id: UUID, offset: int = 0, limit: int = 20
) -> List[Contact]:
    """
    Retrieves a paginated list of contacts for a specific account asynchronously.

    Args:
        db: The SQLAlchemy AsyncSession object.
        account_id: The UUID of the account whose contacts are to be retrieved.
        offset: The number of records to skip (for pagination).
        limit: The maximum number of records to return (for pagination).

    Returns:
        A list of ContactModel instances.
    """
    stmt = (
        select(Contact)
        .filter(Contact.account_id == account_id)
        .order_by(Contact.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def count_contacts(db: AsyncSession, *, account_id: UUID) -> int:
    """
    Counts the total number of contacts for a specific account asynchronously.

    Args:
        db: The SQLAlchemy AsyncSession object.
        account_id: The UUID of the account.

    Returns:
        The total number of contacts.
    """
    stmt = select(func.count(Contact.id)).filter(Contact.account_id == account_id)
    result = await db.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


async def create_contact(
    db: AsyncSession, *, contact_data: ContactCreate, account_id: UUID
) -> Contact:
    """
    Creates a new contact in the database asynchronously after normalizing the phone number.

    Args:
        db: The SQLAlchemy AsyncSession object.
        contact_data: The Pydantic schema containing contact creation data.
        account_id: The UUID of the account creating this contact.

    Returns:
        The newly created ContactModel instance.

    Raises:
        HTTPException: 400 if phone number is invalid/unparseable.
        HTTPException: 409 if a contact with the same normalized phone number
                       already exists for this account.
        HTTPException: 500 on database errors.
    """
    # Normalization is synchronous
    normalized_phone = normalize_phone_number(contact_data.phone_number)

    if not normalized_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unparseable phone number: {contact_data.phone_number}",
        )

    # Check if identifier already exists for this account (asynchronously)
    existing_contact = await find_contact_by_identifier(
        db=db, identifier=normalized_phone, account_id=account_id
    )

    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with phone number {contact_data.phone_number} (normalized: {normalized_phone}) already exists.",
        )

    # Create the ORM model instance (synchronous)
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
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with phone number {contact_data.phone_number} (normalized: {normalized_phone}) already exists (database constraint).",
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
    """
    Updates an existing contact in the database asynchronously.

    Requires the existing contact model instance to be passed in.

    Args:
        db: The SQLAlchemy AsyncSession object.
        contact: The existing ContactModel instance to update.
        update_data: The Pydantic schema containing contact update data.

    Returns:
        The updated ContactModel instance.

    Raises:
        HTTPException: 400 if a new phone number is provided and it's invalid.
        HTTPException: 409 if a new phone number conflicts with an existing contact.
        HTTPException: 500 on database errors.
    """
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

        # Check for conflict only if the identifier is actually changing
        if new_normalized_phone != contact.identifier:
            # Check asynchronously
            existing_contact = await find_contact_by_identifier(
                db=db, identifier=new_normalized_phone, account_id=contact.account_id
            )
            if existing_contact and existing_contact.id != contact.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Another contact with phone number {new_phone_number} (normalized: {new_normalized_phone}) already exists.",
                )
            # Update the identifier
            update_dict["identifier"] = new_normalized_phone
            update_dict["phone_number"] = new_normalized_phone

    # Update the model attributes (synchronous)
    for key, value in update_dict.items():
        setattr(contact, key, value)

    db.add(contact)
    try:
        await db.commit()
        await db.refresh(contact)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Update failed due to conflicting phone number (database constraint).",
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
    """
    Deletes a contact from the database asynchronously.

    Requires the existing contact model instance to be passed in.

    Args:
        db: The SQLAlchemy AsyncSession object.
        contact: The ContactModel instance to delete.

    Raises:
        HTTPException: 500 if deletion fails.
    """
    await db.delete(contact)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Database error deleting contact {contact.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete contact due to a database error.",
        )


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
