# backend/app/services/ai_reply/profile_loader.py

import os
from typing import Optional
from uuid import UUID

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.company_profile import CompanyProfileSchema
from app.services.repository import company_profile as profile_repo


async def load_company_profile(
    db: AsyncSession, account_id: UUID
) -> Optional[CompanyProfileSchema]:
    """
    Loads and validates the company profile from the database.

    Retrieves the company profile associated with the given account_id
    using the profile repository and validates it against the
    CompanyProfileSchema.

    Args:
        db: The SQLAlchemy async session.
        account_id: The unique identifier (UUID) for the account whose
                    profile is needed.

    Returns:
        A validated CompanyProfileSchema object if the profile is found
        in the database, otherwise None. Logs errors if the database
        object cannot be validated against the schema.
    """
    if not account_id:
        logger.error("Attempted to load profile with empty account_id.")
        return None

    logger.info(
        f"Attempting to load profile for account_id '{account_id}' from database."
    )

    try:
        db_profile = await profile_repo.get_profile_by_account_id(
            db=db, account_id=account_id
        )

        if not db_profile:
            return None

        profile_schema = CompanyProfileSchema.model_validate(db_profile)

        logger.info(
            f"Successfully loaded and validated profile for account_id: {account_id}"
        )
        return profile_schema

    except ValidationError as e:
        logger.error(
            f"Profile data validation failed for account_id {account_id} from DB: {e}"
        )
        return None
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred loading profile for account_id {account_id} from DB: {e}"
        )
        return None
