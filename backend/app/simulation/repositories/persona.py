# backend/app/simulation/repositories/persona.py

import uuid
from typing import Optional, List, Dict, Any

from loguru import logger
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.models.simulation.persona import Persona
from app.models.contact import Contact
from app.simulation.schemas.persona import PersonaCreate


async def create_persona(
    db: AsyncSession, *, persona_in: PersonaCreate
) -> Optional[Persona]:
    """
    Creates a new Persona record linked to an existing Contact.

    Ensures the associated Contact exists and is marked for simulation.

    Args:
        db: The AsyncSession instance.
        persona_in: The PersonaCreate schema containing data for the new persona
                    and the contact_id to link to.

    Returns:
        The created Persona object, or None if the contact doesn't exist
        or if there's a database error (e.g., uniqueness violation).
    """
    try:
        # 1. Verify the associated Contact exists
        contact_result = await db.execute(
            select(Contact).where(Contact.id == persona_in.contact_id)
        )
        contact = contact_result.scalar_one_or_none()

        if not contact:
            logger.error(
                f"Contact with id {persona_in.contact_id} not found. Cannot create persona."
            )
            return None

        # 2. Optionally mark the contact as a simulation contact if not already
        if not contact.is_simulation:
            contact.is_simulation = True
            db.add(contact)  # Add to session to track the change
            logger.info(f"Marked contact {contact.id} as is_simulation=True.")

        # 3. Create the Persona instance
        db_persona = Persona(
            **persona_in.model_dump(exclude={"contact_id"}),
            contact_id=persona_in.contact_id,
            simulation_contact_identifier=contact.identifier,
        )

        db.add(db_persona)
        await db.flush()
        await db.refresh(db_persona)
        await db.refresh(contact)

        logger.success(
            f"Successfully created Persona '{db_persona.persona_id}' linked to Contact {contact.id}"
        )
        return db_persona

    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating persona: {e}")
        # Check for specific constraints if needed (e.g., unique persona_id)
        if "uq_persona_persona_id" in str(e):
            logger.error(f"Persona ID '{persona_in.persona_id}' already exists.")
        elif "uq_persona_contact_identifier" in str(e):
            logger.error(
                f"Contact Identifier '{contact.identifier}' is already used by another persona."
            )
        elif "uq_persona_contact_id" in str(e):
            logger.error(
                f"Contact ID '{persona_in.contact_id}' is already linked to another persona."
            )
        else:
            logger.error(f"Unknown integrity error: {e}")
        return None
    except Exception as e:
        await db.rollback()  # Rollback on any other exception
        logger.exception(f"Unexpected error creating persona: {e}")
        return None


async def get_persona_by_id(
    db: AsyncSession, persona_db_id: uuid.UUID
) -> Optional[Persona]:
    """
    Retrieves a Persona by its database UUID.

    Args:
        db: The AsyncSession instance.
        persona_db_id: The UUID of the persona record.

    Returns:
        The Persona object or None if not found.
    """
    result = await db.execute(
        select(Persona)
        .options(selectinload(Persona.contact))
        .where(Persona.id == persona_db_id)
    )
    return result.scalar_one_or_none()


async def get_persona_by_persona_id(
    db: AsyncSession, persona_id_str: str
) -> Optional[Persona]:
    """
    Retrieves a Persona by its human-readable persona_id.

    Args:
        db: The AsyncSession instance.
        persona_id_str: The unique string identifier (e.g., 'curious_customer').

    Returns:
        The Persona object or None if not found.
    """
    result = await db.execute(
        select(Persona)
        .options(selectinload(Persona.contact))
        .where(Persona.persona_id == persona_id_str)
    )
    return result.scalar_one_or_none()


async def get_persona_by_contact_id(
    db: AsyncSession, contact_id: uuid.UUID
) -> Optional[Persona]:
    """
    Retrieves a Persona by its associated contact_id.

    Args:
        db: The AsyncSession instance.
        contact_id: The UUID of the associated contact.

    Returns:
        The Persona object or None if not found (or if contact has no persona).
    """
    result = await db.execute(
        select(Persona)
        .options(selectinload(Persona.contact))
        .where(Persona.contact_id == contact_id)
    )
    return result.scalar_one_or_none()


async def get_persona_by_contact_identifier(
    db: AsyncSession, identifier: str
) -> Optional[Persona]:
    """
    Retrieves a Persona by the simulation_contact_identifier.

    Args:
        db: The AsyncSession instance.
        identifier: The simulation contact identifier (e.g., phone number).

    Returns:
        The Persona object or None if not found.
    """
    result = await db.execute(
        select(Persona)
        .options(selectinload(Persona.contact))
        .where(Persona.simulation_contact_identifier == identifier)
    )
    return result.scalar_one_or_none()


async def get_all_personas(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Persona]:
    """
    Retrieves a list of all Personas with pagination.

    Args:
        db: The AsyncSession instance.
        skip: Number of records to skip.
        limit: Maximum number of records to return.

    Returns:
        A list of Persona objects.
    """
    result = await db.execute(
        select(Persona)
        .options(selectinload(Persona.contact))
        .order_by(Persona.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_persona(
    db: AsyncSession, *, db_persona: Persona, update_data: Dict[str, Any]
) -> Optional[Persona]:
    """
    Updates an existing Persona record.

    Note: This provides a basic update. For complex updates involving
          relationships or specific logic, dedicated service functions are better.
          This also doesn't handle changing contact_id or persona_id easily.

    Args:
        db: The AsyncSession instance.
        db_persona: The existing Persona object to update.
        update_data: A dictionary with keys matching Persona attributes to update.

    Returns:
        The updated Persona object, or None if an error occurs.
    """
    try:
        update_values = {}
        for field, value in update_data.items():
            if hasattr(db_persona, field):
                setattr(db_persona, field, value)
                update_values[field] = value
            else:
                logger.warning(
                    f"Attempted to update non-existent field '{field}' on Persona."
                )

        if not update_values:
            logger.info("No valid fields provided for update.")
            return db_persona

        db.add(db_persona)
        await db.flush()
        await db.refresh(db_persona)
        logger.success(f"Successfully updated Persona '{db_persona.persona_id}'")
        return db_persona
    except IntegrityError as e:
        await db.rollback()
        logger.error(
            f"Database integrity error updating persona {db_persona.persona_id}: {e}"
        )

        return None
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"Unexpected error updating persona {db_persona.persona_id}: {e}"
        )
        return None


async def delete_persona(db: AsyncSession, *, persona_db_id: uuid.UUID) -> bool:
    """
    Deletes a Persona by its database UUID.

    Args:
        db: The AsyncSession instance.
        persona_db_id: The UUID of the persona record to delete.

    Returns:
        True if deletion was successful, False otherwise.
    """
    try:
        result = await db.execute(delete(Persona).where(Persona.id == persona_db_id))
        # result.rowcount tells how many rows were deleted
        if result.rowcount == 1:
            logger.success(f"Successfully deleted Persona with id {persona_db_id}")
            return True
        elif result.rowcount == 0:
            logger.warning(f"Persona with id {persona_db_id} not found for deletion.")
            return False
        else:
            # This case should ideally not happen with UUIDs
            logger.error(
                f"Unexpected row count ({result.rowcount}) during deletion of persona {persona_db_id}."
            )
            await db.rollback()  # Rollback if something unexpected happened
            return False

    except Exception as e:
        await db.rollback()
        logger.exception(f"Error deleting persona {persona_db_id}: {e}")
        return False
