from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
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
    """Find an active contact by its ID.

    Args:
        db: The asynchronous database session.
        account_id: The account UUID owning the contact.
        contact_id: The contact ID to search for.

    Returns:
        The active contact if found, otherwise None.
    """
    if not all([account_id, contact_id]):
        logger.warning("[contact] Missing required parameters for lookup")
        return None

    result = await db.execute(
        select(Contact).filter_by(
            account_id=account_id,
            id=contact_id,
            deleted_at=None,  # Only active contacts
        )
    )
    contact = result.scalar_one_or_none()

    if contact:
        logger.debug(f"[contact] Found active contact (id={contact.id})")
    else:
        logger.info(f"[contact] No active contact found: {contact_id}")

    return contact


async def find_contact_by_identifier(
    db: AsyncSession, *, identifier: str, account_id: UUID
) -> Optional[Contact]:
    """Retrieve an active contact by its normalized identifier and account ID.

    Args:
        db: The asynchronous database session.
        identifier: The normalized identifier (e.g., phone number).
        account_id: The account UUID owning the contact.

    Returns:
        The active contact if found, otherwise None.
    """
    result = await db.execute(
        select(Contact).filter(
            Contact.identifier == identifier,
            Contact.account_id == account_id,
            Contact.deleted_at.is_(None),  # Only active contacts
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
    """Fetch a paginated, filtered, and sorted list of active contacts.

    Args:
        db: The asynchronous database session.
        account_id: The account UUID owning the contacts.
        offset: The offset for pagination.
        limit: The maximum number of contacts to return.
        search: An optional search term to filter by name, email, or phone number.
        sort_by: Field to sort by; must be one of the allowed sort fields.
        sort_direction: Sorting direction, either 'asc' or 'desc'.

    Returns:
        A list of active contacts.
    """
    stmt = select(Contact).where(
        Contact.account_id == account_id, Contact.deleted_at.is_(None)
    )

    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Contact.name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.phone_number.ilike(search_term),
            )
        )

    # Apply sorting
    sort_column = DEFAULT_SORT_FIELD
    if sort_by and sort_by in ALLOWED_SORT_FIELDS:
        sort_column = ALLOWED_SORT_FIELDS[sort_by]

    stmt = stmt.order_by(
        sort_column.desc() if sort_direction == "desc" else sort_column.asc()
    )

    # Apply pagination
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


async def count_contacts(
    db: AsyncSession, account_id: UUID, search: Optional[str] = None
) -> int:
    """Count the active contacts matching an optional search filter.

    Args:
        db: The asynchronous database session.
        account_id: The account UUID owning the contacts.
        search: An optional search term to filter by name, email, or phone number.

    Returns:
        The total count of active contacts.
    """
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
    """Create a new active contact without committing the transaction.

    The commit and refresh should be performed by the upper layer (service or endpoint).

    Args:
        db: The asynchronous database session.
        contact_data: The data for the new contact.
        account_id: The account UUID owning the new contact.

    Returns:
        The newly created Contact object.

    Raises:
        HTTPException: If the phone number is invalid, or there is a conflict with an existing active contact.
    """
    # Verify if the is_simulation was passed to the contact_data
    is_simulation = getattr(contact_data, "is_simulation", False)

    normalized_phone = normalize_phone_number(contact_data.phone_number, is_simulation)
    if not normalized_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unparseable phone number: {contact_data.phone_number}",
        )

    # Check for an active contact with the same identifier
    existing_contact = await find_contact_by_identifier(
        db=db, identifier=normalized_phone, account_id=account_id
    )
    if existing_contact:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An active contact with phone number {contact_data.phone_number} "
                f"(normalized: {normalized_phone}) already exists."
            ),
        )

    # Check for email conflict among active contacts if email is provided
    if contact_data.email:
        existing_email_contact = await db.scalar(
            select(Contact).filter_by(
                account_id=account_id, email=contact_data.email, deleted_at=None
            )
        )
        if existing_email_contact:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An active contact with email {contact_data.email} already exists.",
            )

    contact_data.phone_number = normalized_phone
    db_contact = Contact(
        **contact_data.model_dump(exclude_unset=True),
        account_id=account_id,
        identifier=normalized_phone,
    )
    db.add(db_contact)
    await db.flush()  # Flush to assign primary key and update pending state.
    # Do not commit or refresh here. The upper layer should control this.
    return db_contact


async def update_contact(
    db: AsyncSession, *, contact: Contact, update_data: ContactUpdate
) -> Contact:
    """Update an active contact without committing the transaction.

    The commit and refresh should be performed by the upper layer (service or endpoint).

    Args:
        db: The asynchronous database session.
        contact: The existing contact instance to update.
        update_data: The new data for the contact.

    Returns:
        The updated Contact object.

    Raises:
        HTTPException: If trying to update a deleted contact or a conflict is detected.
    """
    if contact.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot update a deleted contact.",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return contact

    # Check if the phone number is being updated
    if "phone_number" in update_dict:
        new_phone_number = update_dict["phone_number"]
        if not new_phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number cannot be empty.",
            )
        new_normalized_phone = normalize_phone_number(new_phone_number)
        if not new_normalized_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or unparseable phone number provided: {new_phone_number}",
            )
        if new_normalized_phone != contact.identifier:
            # Check for conflict with another active contact
            existing_contact = await find_contact_by_identifier(
                db=db, identifier=new_normalized_phone, account_id=contact.account_id
            )
            if existing_contact and existing_contact.id != contact.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"An active contact with phone number {new_phone_number} "
                        f"(normalized: {new_normalized_phone}) already exists."
                    ),
                )
            update_dict["identifier"] = new_normalized_phone
            update_dict["phone_number"] = new_normalized_phone

    # Check if the email is being updated and verify conflicts among active contacts
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
                detail=f"An active contact with email {update_dict['email']} already exists.",
            )

    for key, value in update_dict.items():
        setattr(contact, key, value)

    db.add(contact)
    await db.flush()  # Flush changes before returning.
    # Do not commit or refresh here. The upper layer should control this.
    return contact


async def delete_contact(db: AsyncSession, *, contact: Contact) -> None:
    """Perform a soft delete on a contact without committing the transaction.

    The commit should be performed by the upper layer (service or endpoint).

    Args:
        db: The asynchronous database session.
        contact: The contact instance to soft delete.

    Raises:
        HTTPException: If the contact is not found or the deletion fails.
    """
    if contact.deleted_at is not None:
        logger.warning(
            f"Attempted to delete an already soft-deleted contact (id={contact.id})"
        )
        return

    stmt = (
        update(Contact)
        .where(Contact.id == contact.id, Contact.deleted_at.is_(None))
        .values(deleted_at=func.now())
        .execution_options(synchronize_session="fetch")
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        logger.warning(
            f"Contact {contact.id} was not found or was already deleted during soft delete."
        )
        await db.refresh(contact, attribute_names=["deleted_at"])
        if contact.deleted_at is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to soft delete the contact.",
            )
    # Do not commit here.


async def get_or_create_contact_inbox(
    db: AsyncSession,
    account_id: UUID,
    contact_id: UUID,
    inbox_id: UUID,
    source_id: UUID,
) -> ContactInbox:
    """Retrieve or create a ContactInbox association.

    Assumes the provided contact ID refers to an active contact.

    Args:
        db: The asynchronous database session.
        account_id: The account UUID.
        contact_id: The contact UUID.
        inbox_id: The inbox UUID.
        source_id: The source UUID.

    Returns:
        The ContactInbox association.

    Raises:
        HTTPException: If the contact does not exist or is deleted.
    """
    contact = await find_contact_by_id(
        db=db, account_id=account_id, contact_id=contact_id
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
        await db.flush()  # Flush to assign an ID to the new contact_inbox.
    else:
        logger.debug(f"[contact_inbox] Found contact_inbox (id={contact_inbox.id})")

    return contact_inbox
