import asyncio
import json
import os
import sys
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

# --- Setup sys.path to import app modules ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ---------------------------------------------


from app.database import (
    AsyncSessionLocal,
)
from app.api.schemas.company_profile import CompanyProfileSchema
from app.services.repository import company_profile as profile_repo


JSON_PROFILE_DIR = "data/company_profiles"


async def migrate_profile(db: AsyncSession, file_path: str):
    """Migrates a single JSON profile file to the database."""
    filename = os.path.basename(file_path)
    account_id_str = filename.replace(".json", "")
    logger.info(f"Processing file: {filename} for account_id: {account_id_str}")

    try:
        account_id = UUID(account_id_str)
    except ValueError:
        logger.error(f"Invalid UUID filename skipped: {filename}")
        return False

    # Optional: Verify if account exists in DB before creating profile
    # account = await account_repo.find_account_by_id(db, account_id)
    # if not account:
    #     logger.error(f"Account {account_id} not found in DB. Skipping profile {filename}.")
    #     return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate data using the Pydantic schema
        profile_schema = CompanyProfileSchema(**data)

        # Use get_or_create to avoid errors if script runs multiple times
        # Or use create_profile if you are sure it's the first run
        # We pass the validated schema directly
        await profile_repo.get_or_create_profile(
            db=db,
            account_id=account_id,
            profile_defaults=profile_schema.model_dump(),  # Pass defaults as dict
        )
        logger.success(f"Successfully migrated profile for account_id: {account_id}")
        return True  # Indicate success

    except FileNotFoundError:
        logger.error(f"File not found during migration: {file_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from {file_path}: {e}")
        return False
    except ValidationError as e:
        logger.error(f"Profile validation failed for {file_path}: {e}")
        return False
    except IntegrityError as e:
        logger.warning(
            f"Integrity error (likely profile already exists) for {account_id}: {e}"
        )
        return True
    except Exception as e:
        logger.exception(f"An unexpected error occurred migrating {file_path}: {e}")
        return False


async def main():
    """Main function to run the migration script."""
    logger.info("Starting company profile migration from JSON to Database...")

    if not os.path.isdir(JSON_PROFILE_DIR):
        logger.error(f"JSON Profile directory not found: {JSON_PROFILE_DIR}")
        return

    json_files = [f for f in os.listdir(JSON_PROFILE_DIR) if f.endswith(".json")]

    if not json_files:
        logger.warning(
            f"No JSON files found in {JSON_PROFILE_DIR}. Nothing to migrate."
        )
        return

    logger.info(f"Found {len(json_files)} JSON profile files to migrate.")

    success_count = 0
    failure_count = 0

    # Process files one by one within a single session or create session per file
    async with AsyncSessionLocal() as db:
        for filename in json_files:
            file_path = os.path.join(JSON_PROFILE_DIR, filename)
            try:
                migrated = await migrate_profile(db, file_path)
                if migrated:
                    success_count += 1
                else:
                    failure_count += 1
                # Commit after each successful migration or batch commits
                await db.commit()
            except Exception as e:
                logger.exception(
                    f"Error processing file {filename}, rolling back for this file."
                )
                await db.rollback()  # Rollback on error for the specific file
                failure_count += 1

    logger.info("--- Migration Summary ---")
    logger.info(f"Successfully migrated: {success_count}")
    logger.info(f"Failed/Skipped:      {failure_count}")
    logger.info("Migration finished.")


if __name__ == "__main__":
    logger.add(sys.stderr, level="INFO")
    asyncio.run(main())
