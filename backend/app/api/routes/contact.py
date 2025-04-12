from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.services.repository import contact as contact_repo
from app.api.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactRead,
    PaginatedContactRead,
)

router = APIRouter()


@router.post(
    "/contacts",
    response_model=ContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contact",
    description=(
        "Creates a new contact for the current account after normalizing the phone number. "
        "Checks for existing contacts with the same normalized phone number and stores the normalized "
        "number in both the `identifier` and `phone_number` fields."
    ),
)
async def create_new_contact(
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> ContactRead:
    """Create a new contact associated with the authenticated user's account.

    Args:
        contact_data (ContactCreate): The contact details from the request body.
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): Authentication context containing account information.

    Returns:
        ContactRead: The newly created contact details.

    Raises:
        HTTPException: 400 if the phone number is invalid or unparseable.
        HTTPException: 409 if a contact with the same phone number already exists.
        HTTPException: 500 if a database error occurs.
    """
    account_id = auth_context.account.id
    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        logger.info(f"Creating contact with data: {contact_data}")
        new_contact = await contact_repo.create_contact(
            db=db, contact_data=contact_data, account_id=account_id
        )
        return new_contact
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error creating contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the contact.",
        )


@router.get(
    "/contacts",
    response_model=PaginatedContactRead,
    summary="List contacts",
    description=(
        "Retrieves a paginated, searchable, and sortable list of contacts for the current account. "
        "Filtering is possible by name, email, or phone number."
    ),
)
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
    offset: int = Query(
        0, ge=0, description="Number of records to skip for pagination"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None,
        description="Search term to filter contacts by name, email, or phone number.",
        min_length=1,
        max_length=100,
    ),
    sort_by: Optional[str] = Query(
        None,
        description="Field to sort contacts by (e.g., 'name', 'email', 'created_at').",
    ),
    sort_direction: str = Query(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort direction: 'asc' (ascending) or 'desc' (descending).",
    ),
) -> PaginatedContactRead:
    """Retrieve contacts belonging to the authenticated user's account with pagination, search, and sorting.

    Args:
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): Authentication context containing the account ID.
        offset (int): Pagination offset.
        limit (int): Pagination limit.
        search (Optional[str]): Optional search term.
        sort_by (Optional[str]): Optional field to sort by.
        sort_direction (str): Sort direction, either "asc" or "desc".

    Returns:
        PaginatedContactRead: A paginated response containing the list of contacts and the total count.

    Raises:
        HTTPException: 500 if a database error occurs.
    """
    account_id = auth_context.account.id
    if db is None:
        logger.error("Database session not available in list_contacts")
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        contacts = await contact_repo.get_contacts(
            db=db,
            account_id=account_id,
            offset=offset,
            limit=limit,
            search=search,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        total_contacts = await contact_repo.count_contacts(
            db=db, account_id=account_id, search=search
        )
        return PaginatedContactRead(total=total_contacts, items=contacts)
    except Exception as e:
        logger.exception(
            f"Unexpected error listing contacts for account {account_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing contacts.",
        )


@router.get(
    "/contacts/{contact_id}",
    response_model=ContactRead,
    summary="Get a specific contact",
    description="Retrieves the details of a specific contact by its ID.",
)
async def get_contact_details(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> ContactRead:
    """Retrieve a single contact by its unique ID, ensuring it belongs to the authenticated user's account.

    Args:
        contact_id (UUID): The UUID of the contact to retrieve.
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): Authentication context with account details.

    Returns:
        ContactRead: The details of the specified contact.

    Raises:
        HTTPException: 404 if the contact is not found or does not belong to the account.
        HTTPException: 500 if a database error occurs.
    """
    account_id = auth_context.account.id

    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        contact = await contact_repo.find_contact_by_id(
            db=db, contact_id=contact_id, account_id=account_id
        )
        if contact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact with ID {contact_id} not found.",
            )
        return contact
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error getting contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the contact.",
        )


@router.put(
    "/contacts/{contact_id}",
    response_model=ContactRead,
    summary="Update a contact",
    description="Updates the details of an existing contact.",
)
async def update_existing_contact(
    contact_id: UUID,
    update_data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> ContactRead:
    """Update an existing contact identified by its ID.

    - Normalizes the phone number if updated.
    - Checks that the contact belongs to the authenticated user's account.
    - Updates both the `identifier` and `phone_number` fields if the phone number changes.

    Args:
        contact_id (UUID): The UUID of the contact to update.
        update_data (ContactUpdate): The contact details to update.
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): Authentication context containing account information.

    Returns:
        ContactRead: The updated contact details.

    Raises:
        HTTPException: 404 if the contact is not found or does not belong to the account.
        HTTPException: 400 if the new phone number is invalid or unparseable.
        HTTPException: 409 if the new phone number conflicts with another contact.
        HTTPException: 500 if a database error occurs.
    """
    account_id = auth_context.account.id

    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        existing_contact = await contact_repo.find_contact_by_id(
            db=db, contact_id=contact_id, account_id=account_id
        )
        if existing_contact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact with ID {contact_id} not found.",
            )
        updated_contact = await contact_repo.update_contact(
            db=db, contact=existing_contact, update_data=update_data
        )
        return updated_contact
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error updating contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the contact.",
        )


@router.delete(
    "/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a contact",
    description="Deletes a specific contact by its ID.",
)
async def delete_existing_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a contact identified by its ID, ensuring it belongs to the authenticated user's account.

    Args:
        contact_id (UUID): The UUID of the contact to delete.
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): Authentication context with account information.

    Returns:
        None: A 204 No Content response on success.

    Raises:
        HTTPException: 404 if the contact is not found or does not belong to the account.
        HTTPException: 500 if a database error occurs during deletion.
    """
    account_id = auth_context.account.id

    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        existing_contact = await contact_repo.find_contact_by_id(
            db=db, contact_id=contact_id, account_id=account_id
        )
        if existing_contact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact with ID {contact_id} not found.",
            )
        await contact_repo.delete_contact(db=db, contact=existing_contact)
        return None
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Unexpected error deleting contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the contact.",
        )
