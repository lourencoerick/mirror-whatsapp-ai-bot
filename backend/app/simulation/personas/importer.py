# backend/app/simulation/personas/importer.py

import json
import uuid
from typing import Optional, Dict, Any

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.contact import Contact
from app.simulation.schemas import persona as persona_schemas


from app.simulation.personas.generator import (
    _find_or_create_contact_for_persona,
    save_persona_from_data,
)


async def import_persona_from_json(
    db: AsyncSession,
    account: Account,
    json_file_path: str,
) -> Optional[persona_schemas.PersonaRead]:
    """
    Imports a persona definition from a JSON file into the database.

    Reads the JSON file, validates its structure against PersonaBase, finds/creates
    the associated Contact, and saves the Persona linked to the Contact.

    Args:
        db: The AsyncSession instance.
        account: The Account object the persona belongs to.
        json_file_path: The full path to the JSON file containing the persona definition.

    Returns:
        A validated PersonaRead schema object for the imported persona,
        or None if import or saving fails.
    """
    logger.info(f"Attempting to import persona from file: {json_file_path}")

    # 1. Read and Parse JSON file
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            persona_data_dict: Dict[str, Any] = json.load(f)
        logger.debug(f"Successfully read JSON data from {json_file_path}")
    except FileNotFoundError:
        logger.error(f"Import failed: File not found at {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Import failed: Invalid JSON format in {json_file_path}: {e}")
        return None
    except Exception as e:
        logger.exception(
            f"Import failed: Unexpected error reading file {json_file_path}: {e}"
        )
        return None

    # 2. Validate JSON data against PersonaBase schema
    try:
        # PersonaBase includes simulation_contact_identifier, so it's suitable here
        persona_base_data = persona_schemas.PersonaBase.model_validate(
            persona_data_dict
        )
        logger.info(
            f"JSON data validated successfully for persona_id: {persona_base_data.persona_id}"
        )
    except ValidationError as e:
        logger.error(
            f"Import failed: JSON data validation failed for {json_file_path}: {e}"
        )
        return None
    except Exception as e:
        logger.exception(
            f"Import failed: Unexpected error during validation for {json_file_path}: {e}"
        )
        return None

    contact = await _find_or_create_contact_for_persona(
        db=db,
        account_id=account.id,
        persona_id_to_link=persona_base_data.persona_id,
    )

    if not contact:
        logger.error(
            f"Import failed: Could not find or create contact for identifier '{contact.id}'. Check generator logs for details."
        )
        # Attempt rollback in case contact creation started but failed partially
        await db.rollback()
        return None

    # 3. Save Persona data linked to the Contact
    try:
        saved_persona = await save_persona_from_data(
            db=db,
            persona_base_data=persona_base_data,
            contact_id=contact.id,
        )

        if saved_persona:

            await db.commit()
            logger.success(
                f"Successfully imported and committed persona '{saved_persona.persona_id}' from {json_file_path}"
            )
            return saved_persona
        else:
            logger.error(
                f"Import failed: Could not save persona '{persona_base_data.persona_id}' to database. Check generator logs for details (e.g., duplicate persona_id)."
            )

            await db.rollback()
            return None

    except Exception as e:
        logger.exception(
            f"Import failed: Unexpected error during final persona saving or commit for {json_file_path}"
        )
        await db.rollback()
        return None
