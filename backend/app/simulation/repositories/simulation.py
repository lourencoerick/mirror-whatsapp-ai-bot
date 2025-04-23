# backend/app/simulation/repositories/simulation_repo.py

from typing import Optional, Dict, Any, List
from uuid import UUID

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.simulation.schemas.persona_definition import (
    PersonaDefinition,
)


async def create_simulation(
    db: AsyncSession, *, profile_id: UUID, persona_def: PersonaDefinition
) -> Simulation:
    """
    Creates a new simulation record in the database.

    Args:
        db: The SQLAlchemy async session.
        profile_id: The UUID of the company profile being used.
        persona_def: The Pydantic schema of the persona definition.

    Returns:
        The newly created Simulation object.
    """
    logger.info(
        f"Creating new simulation record for persona '{persona_def.persona_id}'"
    )

    persona_data_to_save = persona_def.model_dump(exclude={"embeddings"})

    db_simulation = Simulation(
        company_profile_id=profile_id,
        persona_definition=persona_data_to_save,
        status=SimulationStatusEnum.RUNNING,
    )
    try:
        db.add(db_simulation)
        await db.flush()
        await db.refresh(db_simulation)
        logger.success(f"Simulation record created with ID: {db_simulation.id}")
        return db_simulation
    except Exception as e:
        logger.error(f"Error creating simulation record: {e}")
        raise


async def get_simulation_by_id(
    db: AsyncSession, simulation_id: UUID, load_relations: bool = False
) -> Optional[Simulation]:
    """
    Retrieves a simulation by its ID.

    Args:
        db: The SQLAlchemy async session.
        simulation_id: The UUID of the simulation to retrieve.
        load_relations: If True, eagerly loads messages and events.

    Returns:
        The Simulation object if found, otherwise None.
    """
    logger.debug(f"Fetching simulation with id: {simulation_id}")
    stmt = select(Simulation).where(Simulation.id == simulation_id)
    if load_relations:
        stmt = stmt.options(
            selectinload(Simulation.messages), selectinload(Simulation.events)
        )
    result = await db.execute(stmt)
    simulation = result.scalars().first()
    if not simulation:
        logger.warning(f"Simulation with id {simulation_id} not found.")
    return simulation


async def update_simulation(
    db: AsyncSession, *, db_simulation: Simulation, update_data: Dict[str, Any]
) -> Simulation:
    """
    Updates an existing simulation record.

    Args:
        db: The SQLAlchemy async session.
        db_simulation: The existing Simulation object to update.
        update_data: A dictionary containing the fields to update.

    Returns:
        The updated Simulation object.
    """
    sim_id = db_simulation.id
    logger.info(f"Updating simulation with id: {sim_id}")
    for field, value in update_data.items():
        if hasattr(db_simulation, field):
            setattr(db_simulation, field, value)
        else:
            logger.warning(
                f"Attempted to update non-existent field '{field}' on Simulation"
            )

    try:
        db.add(db_simulation)
        await db.flush()
        await db.refresh(db_simulation)
        logger.info(
            f"Successfully updated simulation {sim_id} with data: {update_data}"
        )
        return db_simulation
    except Exception as e:
        logger.error(f"Error updating simulation {sim_id}: {e}")
        raise
