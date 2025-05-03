import json
import os
from typing import Optional, Dict, Any
from uuid import UUID

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.simulation.schemas.persona import PersonaRead
from app.simulation.repositories import persona as persona_repo


async def load_persona_from_db(
    db: AsyncSession, persona_id_str: str
) -> Optional[PersonaRead]:
    """
    Loads a persona definition from the database using its persona_id.

    Args:
        db: The AsyncSession instance for database access.
        persona_id_str: The human-readable identifier of the persona to load
                        (e.g., 'curious_customer').

    Returns:
        A validated PersonaRead Pydantic schema object containing the persona data,
        or None if the persona is not found in the database.
    """
    if not persona_id_str:
        logger.error("Attempted to load persona with empty persona_id_str.")
        return None

    logger.info(f"Attempting to load persona '{persona_id_str}' from database.")

    try:
        # Call the repository function to get the persona ORM model
        db_persona = await persona_repo.get_persona_by_persona_id(
            db=db, persona_id_str=persona_id_str
        )

        if db_persona is None:
            logger.warning(f"Persona '{persona_id_str}' not found in database.")
            return None

        # Convert the ORM model to the Pydantic schema for consistent data structure
        # The .contact relationship should be loaded due to selectinload in the repo
        persona_read_schema = PersonaRead.model_validate(db_persona)
        # Or using Pydantic v1 style: PersonaRead.from_orm(db_persona)

        logger.success(f"Persona '{persona_id_str}' loaded successfully from database.")
        return persona_read_schema

    except Exception as e:
        # Catching potential database connection errors or other exceptions
        logger.exception(
            f"Unexpected error loading persona {persona_id_str} from database: {e}"
        )
        return None
