import json
import os
import logging
from typing import Optional

from loguru import logger
from pydantic import ValidationError
from app.api.schemas.company_profile import CompanyProfileSchema


# Define the base directory for company profiles
# Consider making this configurable via environment variables later
# For example: PROFILE_DIR = os.getenv("COMPANY_PROFILE_DIR", "company_profiles")
PROFILE_DIR = "company_profiles"


def load_company_profile(company_id: str) -> Optional[CompanyProfileSchema]:
    """Loads and validates the company profile from a JSON file.

    Constructs the path to the company's profile JSON file based on the
    company_id and the PROFILE_DIR. It attempts to read, parse, and
    validate the JSON data against the CompanyProfileSchema.

    Args:
        company_id: The unique identifier for the company, used as the
                    filename (without extension).

    Returns:
        A validated CompanyProfileSchema object if the profile is found
        and is valid, otherwise None. Logs errors encountered during
        the process.
    """
    if not company_id:
        logger.error("Attempted to load profile with empty company_id.")
        return None

    # Sanitize company_id to prevent directory traversal issues, although
    # using it directly as a filename is generally okay if controlled.
    # Basic sanitization: ensure it's just a filename part.
    if os.path.sep in company_id or ".." in company_id:
        logger.error(f"Invalid characters found in company_id: {company_id}")
        return None

    profile_filename = f"{company_id}.json"
    profile_path = os.path.join(PROFILE_DIR, profile_filename)

    logger.info(
        f"Attempting to load profile for company_id '{company_id}' from {profile_path}"
    )

    try:
        # Ensure the base directory exists
        if not os.path.isdir(PROFILE_DIR):
            logger.error(f"Profile directory not found: {PROFILE_DIR}")
            # Optionally create it: os.makedirs(PROFILE_DIR, exist_ok=True)
            # But for loading, it should exist.
            return None

        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate data using the Pydantic schema
        profile = CompanyProfileSchema(**data)
        logger.info(
            f"Successfully loaded and validated profile for company_id: {company_id}"
        )
        return profile

    except FileNotFoundError:
        logger.warning(f"Profile file not found: {profile_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from {profile_path}: {e}")
        return None
    except ValidationError as e:
        logger.error(f"Profile validation failed for {profile_path}: {e}")
        # Consider logging e.errors() for more detailed validation info
        return None
    except IOError as e:
        logger.error(f"IOError reading profile file {profile_path}: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(
            f"An unexpected error occurred loading profile {profile_path}: {e}"
        )
        return None
