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

# Create the router
router = APIRouter()


@router.post(
    "/contacts",
    response_model=ContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contact",
    description="Creates a new contact for the current account after normalizing the phone number.",
)
async def create_new_contact(
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Creates a new contact associated with the authenticated user's account.

    - Normalizes the phone number to digits-only E.164 format (no '+').
    - Checks for existing contacts with the same normalized phone number within the account.
    - Stores the normalized number in both `identifier` and `phone_number` fields.

    Args:
        contact_data: The contact details from the request body.
        db: The database session dependency.
        account_id: The account ID dependency from the authenticated user.

    Returns:
        The newly created contact details.

    Raises:
        HTTPException 400: If the phone number is invalid or unparseable.
        HTTPException 409: If a contact with the same phone number already exists.
        HTTPException 500: If a database error occurs.
    """
    account_id = auth_context.account.id

    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        logger.info(f"data: {contact_data}")
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
    description="Retrieves a paginated list of contacts for the current account.",
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
):
    """
    Retrieves a list of contacts belonging to the authenticated user's account,
    with support for pagination.

    Args:
        db: The database session dependency.
        account_id: The account ID dependency from the authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        A paginated response containing the list of contacts and the total count.

    Raises:
        HTTPException 500: If a database error occurs.
    """
    account_id = auth_context.account.id
    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        contacts = await contact_repo.get_contacts(
            db=db, account_id=account_id, offset=offset, limit=limit
        )
        total_contacts = await contact_repo.count_contacts(db=db, account_id=account_id)
        return PaginatedContactRead(total=total_contacts, items=contacts)
    except Exception as e:
        logger.error(f"Unexpected error listing contacts: {e}")
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
):
    """
    Retrieves a single contact by its unique ID, ensuring it belongs to the
    authenticated user's account.

    Args:
        contact_id: The UUID of the contact to retrieve.
        db: The database session dependency.
        account_id: The account ID dependency from the authenticated user.

    Returns:
        The details of the specified contact.

    Raises:
        HTTPException 404: If the contact is not found or does not belong to the account.
        HTTPException 500: If a database error occurs.
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
        # Catch any unexpected errors during retrieval
        # Log the error e
        print(
            f"Unexpected error getting contact {contact_id}: {e}"
        )  # Replace with proper logging
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
):
    """
    Updates an existing contact identified by its ID.

    - Ensures the contact belongs to the authenticated user's account.
    - If the phone number is updated, it's normalized and uniqueness is checked.
    - Updates both `identifier` and `phone_number` fields if the phone number changes.

    Args:
        contact_id: The UUID of the contact to update.
        update_data: The contact details to update.
        db: The database session dependency.
        account_id: The account ID dependency from the authenticated user.

    Returns:
        The updated contact details.

    Raises:
        HTTPException 404: If the contact is not found or does not belong to the account.
        HTTPException 400: If the new phone number is invalid or unparseable.
        HTTPException 409: If the new phone number conflicts with another contact.
        HTTPException 500: If a database error occurs.
    """
    account_id = auth_context.account.id

    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    try:
        # First, get the existing contact to ensure it exists and belongs to the account
        existing_contact = await contact_repo.find_contact_by_id(
            db=db, contact_id=contact_id, account_id=account_id
        )
        if existing_contact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact with ID {contact_id} not found.",
            )

        # Pass the existing contact and update data to the repository function
        updated_contact = await contact_repo.update_contact(
            db=db, contact=existing_contact, update_data=update_data
        )
        return updated_contact
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error updating contact {contact_id}: {e}")
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
):
    """
    Deletes a contact identified by its ID.

    - Ensures the contact belongs to the authenticated user's account before deletion.

    Args:
        contact_id: The UUID of the contact to delete.
        db: The database session dependency.
        account_id: The account ID dependency from the authenticated user.

    Returns:
        None with a 204 No Content status code on success.

    Raises:
        HTTPException 404: If the contact is not found or does not belong to the account.
        HTTPException 500: If a database error occurs during deletion.
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

        # No content to return on successful deletion
        return None

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error deleting contact {contact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the contact.",
        )
