# backend/app/simulation/repositories/simulation_message_repo.py

from typing import Optional, List
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import Models
from app.models.simulation.simulation_message import (
    SimulationMessage,
    SimulationMessageRoleEnum,
)


async def create_message(
    db: AsyncSession,
    *,
    simulation_id: UUID,
    turn: int,
    role: SimulationMessageRoleEnum,
    content: str,
    original_message_id: Optional[UUID] = None,  # Opcional
) -> SimulationMessage:
    """
    Creates a new simulation message record.

    Args:
        db: The SQLAlchemy async session.
        simulation_id: The ID of the simulation this message belongs to.
        turn: The turn number in the conversation.
        role: The role of the message sender (user or assistant).
        content: The text content of the message.
        original_message_id: Optional ID linking to the main 'messages' table.

    Returns:
        The newly created SimulationMessage object.
    """
    logger.debug(
        f"Creating simulation message for sim_id={simulation_id}, turn={turn}, role={role.value}"
    )
    db_message = SimulationMessage(
        simulation_id=simulation_id,
        turn_number=turn,
        role=role,
        content=content,
        original_message_id=original_message_id,
    )
    try:
        db.add(db_message)
        await db.flush()
        await db.refresh(db_message)
        # logger.debug(f"Simulation message created with ID: {db_message.id}") # Log menos verboso
        return db_message
    except Exception as e:
        logger.error(
            f"Error creating simulation message for sim_id={simulation_id}: {e}"
        )
        raise


async def get_messages_by_simulation_id(
    db: AsyncSession, simulation_id: UUID
) -> List[SimulationMessage]:
    """
    Retrieves all messages for a given simulation, ordered by turn number.

    Args:
        db: The SQLAlchemy async session.
        simulation_id: The UUID of the simulation.

    Returns:
        A list of SimulationMessage objects.
    """
    logger.debug(f"Fetching messages for simulation_id: {simulation_id}")
    stmt = (
        select(SimulationMessage)
        .where(SimulationMessage.simulation_id == simulation_id)
        .order_by(SimulationMessage.turn_number)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    logger.debug(f"Found {len(messages)} messages for simulation {simulation_id}")
    return list(messages)
