# backend/app/api/routers/profile.py

from fastapi import APIRouter, Depends, HTTPException, status, Response
from loguru import logger
from uuid import UUID, uuid4
from typing import Optional

# SQLAlchemy Session and Models/Schemas
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db  # Use your actual DB dependency function
from app.models.company_profile import CompanyProfile
from app.api.schemas.company_profile import CompanyProfileSchema  # Use the main schema

# Repository Functions
from app.services.repository import (
    company_profile as profile_repo,
)  # Import the repo module

# Auth Context
from app.core.dependencies.auth import get_auth_context, AuthContext


# Define the router
router = APIRouter(
    prefix="/profile",  # Use /profile as the base
    tags=["v1 - Company Profile"],  # Tag for API documentation
)

# --- Endpoints ---


@router.get(
    "",  # Route relative to the prefix: /api/v1/profile
    response_model=CompanyProfileSchema,  # Return the full profile schema
    summary="Get Company Profile",
    description="Retrieves the company profile associated with the authenticated user's active account.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Company Profile not found for this account"
        }
    },
)
async def get_company_profile(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfile:  # Return the ORM model for automatic conversion
    """
    Retrieves the Company Profile for the currently authenticated account.
    Returns 404 if no profile exists yet.
    """
    account_id = auth_context.account.id
    logger.info(f"Getting Company Profile for account {account_id}")

    profile = await profile_repo.get_profile_by_account_id(db=db, account_id=account_id)

    if not profile:
        logger.warning(f"Company Profile not found for account {account_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company Profile not found for this account. It might need to be created or generated.",
        )

    logger.info(f"Returning Company Profile {profile.id} for account {account_id}")
    return profile


@router.put(
    "",  # Route relative to the prefix: /api/v1/profile
    response_model=CompanyProfileSchema,
    summary="Create or Update Company Profile",
    description="Creates (if doesn't exist) or fully updates the company profile associated with the authenticated user's active account.",
)
async def create_or_update_company_profile(
    profile_data: CompanyProfileSchema,  # Receive the full profile data in the request body
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfile:
    """
    Creates or updates the Company Profile for the currently authenticated account.
    This performs an 'upsert' operation based on the account ID.
    """
    account_id = auth_context.account.id
    current_user_id = auth_context.user.id

    logger.info(f"Updating/Creating Company Profile for account {account_id}")

    # Convert incoming Pydantic schema to dict suitable for DB update/create
    # Use mode='json' to handle special types like HttpUrl correctly for the repo functions
    try:
        profile_data_dict = profile_data.model_dump(
            mode="json", exclude={"id"}
        )  # Exclude ID if present
    except Exception as dump_err:
        logger.error(f"Error serializing input profile data: {dump_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid profile data format.",
        ) from dump_err

    new_offerings_list = profile_data_dict.get("offering_overview", [])
    final_offerings = []

    for offer_data in new_offerings_list:
        if "id" in offer_data and offer_data["id"]:
            # Se o ID veio do frontend, nós o mantemos.
            final_offerings.append(offer_data)
        else:
            # Se não veio ID, é uma nova oferta. Geramos um novo ID.
            offer_data["id"] = str(uuid4())
            final_offerings.append(offer_data)

    profile_data_dict["offering_overview"] = final_offerings

    if profile_data_dict.get("is_scheduling_enabled"):
        logger.info(
            f"Scheduling is enabled. Setting scheduling_user_id to {current_user_id}."
        )
        profile_data_dict["scheduling_user_id"] = str(current_user_id)
    else:
        if "scheduling_user_id" in profile_data_dict:
            logger.info("Scheduling is disabled. Clearing scheduling_user_id.")
            profile_data_dict["scheduling_user_id"] = None

        logger.info(
            "Scheduling disabled. Ensuring all offerings have requires_scheduling=false."
        )
        if (
            "offering_overview" in profile_data_dict
            and profile_data_dict["offering_overview"]
        ):
            for offer in profile_data_dict["offering_overview"]:
                offer["requires_scheduling"] = False

    saved_profile: Optional[CompanyProfile] = None
    try:
        # Check if profile exists
        existing_profile = await profile_repo.get_profile_by_account_id(
            db=db, account_id=account_id
        )

        if existing_profile:
            # Update existing profile
            logger.debug(f"Existing profile {existing_profile.id} found. Updating.")
            saved_profile = await profile_repo.update_profile(
                db=db,
                db_profile=existing_profile,
                profile_in=profile_data_dict,  # Pass the JSON-compatible dict
            )
        else:
            # Create new profile
            logger.debug(
                f"No existing profile found for account {account_id}. Creating."
            )
            # Pass the original Pydantic schema to create_profile
            # Ensure create_profile handles the internal model_dump(mode='json')
            saved_profile = await profile_repo.create_profile(
                db=db, profile_in=profile_data, account_id=account_id  # Pass the schema
            )

        if not saved_profile:
            # This case shouldn't happen if repo functions raise errors, but handle defensively
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save profile after create/update attempt.",
            )

        await db.commit()
        await db.refresh(saved_profile)  # Refresh to get final state
        logger.info(
            f"Successfully saved Company Profile {saved_profile.id} for account {account_id}"
        )
        return saved_profile

    except (
        ValueError
    ) as val_err:  # Catch potential validation errors from repo (e.g., missing defaults)
        await db.rollback()
        logger.warning(
            f"Validation error during profile save for account {account_id}: {val_err}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err)
        ) from val_err
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error saving Company Profile for account {account_id}: {e}")
        # Check for specific DB errors like unique constraint violation if needed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving the company profile.",
        ) from e
