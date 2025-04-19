# backend/app/services/repository/profile_repo.py

from typing import Optional, Dict, Any
from uuid import UUID

from loguru import logger
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.models.company_profile import CompanyProfile
from app.api.schemas.company_profile import CompanyProfileSchema


async def get_profile_by_account_id(
    db: AsyncSession, account_id: UUID
) -> Optional[CompanyProfile]:
    """
    Retrieves a company profile by its associated account ID.

    Args:
        db: The SQLAlchemy async session.
        account_id: The UUID of the account whose profile is to be retrieved.

    Returns:
        The CompanyProfile object if found, otherwise None.
    """
    logger.debug(f"Fetching company profile for account_id: {account_id}")
    stmt = select(CompanyProfile).where(CompanyProfile.account_id == account_id)
    # Optional: Eager load relationships if needed later, e.g., account
    # stmt = stmt.options(selectinload(CompanyProfile.account))
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if profile:
        logger.debug(f"Found profile with id: {profile.id}")
    else:
        logger.warning(f"No profile found for account_id: {account_id}")
    return profile


async def create_profile(
    db: AsyncSession, *, profile_in: CompanyProfileSchema, account_id: UUID
) -> CompanyProfile:
    """
    Creates a new company profile record in the database.

    Args:
        db: The SQLAlchemy async session.
        profile_in: The Pydantic schema containing the profile data.
        account_id: The UUID of the account this profile belongs to.

    Returns:
        The newly created CompanyProfile object.

    Raises:
        IntegrityError: If a profile for this account_id already exists.
        Exception: For other database errors.
    """
    logger.info(f"Creating new company profile for account_id: {account_id}")
    # Convert Pydantic schema to dictionary, excluding unset fields if needed
    profile_data = profile_in.model_dump(exclude_unset=True, mode="json")

    # Create the SQLAlchemy model instance
    db_profile = CompanyProfile(**profile_data, account_id=account_id)

    try:
        db.add(db_profile)
        await db.flush()  # Flush to get potential errors like unique constraint violation
        await db.refresh(db_profile)  # Refresh to load defaults and generated values
        logger.info(f"Successfully created profile with id: {db_profile.id}")
        return db_profile
    except Exception as e:
        logger.error(f"Error creating profile for account {account_id}: {e}")
        # Rollback might happen automatically depending on session management,
        # but re-raising allows the caller to handle it.
        raise


async def update_profile(
    db: AsyncSession, *, db_profile: CompanyProfile, profile_in: Dict[str, Any]
) -> CompanyProfile:
    """
    Updates an existing company profile record.

    Args:
        db: The SQLAlchemy async session.
        db_profile: The existing CompanyProfile object to update.
        profile_in: A dictionary containing the fields to update.

    Returns:
        The updated CompanyProfile object.
    """
    logger.info(f"Updating company profile with id: {db_profile.id}")
    update_data = profile_in  # Can be a dict or a Pydantic model .model_dump()

    for field, value in update_data.items():
        # Ensure we only try to set valid attributes of the model
        if hasattr(db_profile, field):
            setattr(db_profile, field, value)
        else:
            logger.warning(
                f"Attempted to update non-existent field '{field}' on CompanyProfile"
            )

    try:
        db.add(db_profile)  # Add the modified object to the session
        await db.flush()
        await db.refresh(db_profile)
        logger.info(f"Successfully updated profile with id: {db_profile.id}")
        return db_profile
    except Exception as e:
        logger.error(f"Error updating profile {db_profile.id}: {e}")
        raise


async def delete_profile(db: AsyncSession, *, db_profile: CompanyProfile) -> None:
    """
    Deletes a company profile record from the database.

    Args:
        db: The SQLAlchemy async session.
        db_profile: The CompanyProfile object to delete.
    """
    profile_id = db_profile.id
    logger.warning(
        f"Deleting company profile with id: {profile_id}"
    )  # Warning level for deletion
    try:
        await db.delete(db_profile)
        await db.flush()
        logger.info(f"Successfully deleted profile with id: {profile_id}")
    except Exception as e:
        logger.error(f"Error deleting profile {profile_id}: {e}")
        raise


# Optional: get_or_create function
async def get_or_create_profile(
    db: AsyncSession,
    *,
    account_id: UUID,
    profile_defaults: Optional[Dict[str, Any]] = None,
) -> CompanyProfile:
    """
    Retrieves a profile by account_id or creates it if it doesn't exist.

    Args:
        db: The SQLAlchemy async session.
        account_id: The UUID of the account.
        profile_defaults: A dictionary of default values to use if creating.
                          Should conform to CompanyProfileSchema fields.

    Returns:
        The existing or newly created CompanyProfile object.
    """
    profile = await get_profile_by_account_id(db, account_id)
    if profile:
        return profile

    logger.info(f"Profile not found for account {account_id}, creating new one.")
    if profile_defaults is None:
        profile_defaults = {}  # Use model defaults if none provided

    # Ensure required fields are present or raise error
    if "company_name" not in profile_defaults:
        # Or fetch from Account model if possible
        raise ValueError("Cannot create profile without 'company_name' default.")

    # Use the schema to validate and structure defaults before creating model
    try:
        profile_schema = CompanyProfileSchema(**profile_defaults)
    except Exception as validation_err:
        logger.error(
            f"Invalid default data provided for profile creation: {validation_err}"
        )
        raise ValueError(
            f"Invalid profile defaults: {validation_err}"
        ) from validation_err

    return await create_profile(db=db, profile_in=profile_schema, account_id=account_id)
