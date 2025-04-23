from typing import Optional, Dict, Any, List
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation.simulation_event import (
    SimulationEvent,
    SimulationEventTypeEnum,
)


async def create_event(
    db: AsyncSession,
    *,
    simulation_id: UUID,
    event_type: SimulationEventTypeEnum,
    turn: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> SimulationEvent:
    """
    Creates a new simulation event record.

    Args:
        db: The SQLAlchemy async session.
        simulation_id: The ID of the simulation this event belongs to.
        event_type: The type of the event.
        turn: The turn number when the event occurred (optional).
        details: Additional JSON details about the event (optional).

    Returns:
        The newly created SimulationEvent object.
    """
    logger.debug(
        f"Logging simulation event for sim_id={simulation_id}, type={event_type.value}, turn={turn}"
    )
    db_event = SimulationEvent(
        simulation_id=simulation_id,
        event_type=event_type,
        turn_number=turn,
        details=details,
    )
    try:
        db.add(db_event)
        await db.flush()
        await db.refresh(db_event)

        return db_event
    except Exception as e:
        logger.error(f"Error creating simulation event for sim_id={simulation_id}: {e}")
        raise


async def get_events_by_simulation_id(
    db: AsyncSession, simulation_id: UUID
) -> List[SimulationEvent]:
    """
    Retrieves all events for a given simulation, ordered by timestamp.

    Args:
        db: The SQLAlchemy async session.
        simulation_id: The UUID of the simulation.

    Returns:
        A list of SimulationEvent objects.
    """
    logger.debug(f"Fetching events for simulation_id: {simulation_id}")
    stmt = (
        select(SimulationEvent)
        .where(SimulationEvent.simulation_id == simulation_id)
        .order_by(SimulationEvent.timestamp)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    logger.debug(f"Found {len(events)} events for simulation {simulation_id}")
    return list(events)
