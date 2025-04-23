import json
import os
from typing import Optional, Dict, Any
from uuid import UUID

from loguru import logger
from pydantic import ValidationError


from app.simulation.schemas.persona_definition import PersonaDefinition

from app.simulation.config import (
    PERSONA_DIR,
)


async def load_persona(persona_id: str) -> Optional[PersonaDefinition]:
    """
    Loads a persona definition from its JSON file and validates it.
    Embeddings are no longer pre-calculated here.

    Args:
        persona_id: The identifier of the persona to load (filename without .json).

    Returns:
        A validated PersonaDefinition object, or None if loading/validation fails.
    """
    if not persona_id:
        logger.error("Attempted to load persona with empty persona_id.")
        return None

    persona_filename = f"{persona_id}.json"

    persona_path = os.path.join(PERSONA_DIR, persona_filename)
    logger.info(f"Attempting to load persona '{persona_id}' from {persona_path}")

    try:
        if not os.path.isdir(PERSONA_DIR):
            logger.error(f"Persona directory not found: {PERSONA_DIR}")
            return None

        with open(persona_path, "r", encoding="utf-8") as f:
            raw_persona_data: Dict[str, Any] = json.load(f)
        logger.debug(f"Loaded raw persona data for {persona_id}")

        persona = PersonaDefinition.model_validate(raw_persona_data)

        logger.success(f"Persona '{persona_id}' loaded and validated successfully.")
        return persona

    except FileNotFoundError:
        logger.error(f"Persona file not found: {persona_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from {persona_path}: {e}")
        return None
    except ValidationError as e:
        logger.error(f"Persona validation failed for {persona_path}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error loading persona {persona_id}: {e}")
        return None
