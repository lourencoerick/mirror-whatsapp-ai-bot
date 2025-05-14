# app/services/repository/evolution_instance.py

from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.channels.evolution_instance import (
    EvolutionInstance,
    EvolutionInstanceStatus,
)


async def get_evolution_instance_by_id(
    db: AsyncSession, instance_id: UUID, account_id: Optional[UUID] = None
) -> EvolutionInstance | None:
    """
    Retrieves an EvolutionInstance by its ID.
    Optionally filters by account_id if provided.

    Args:
        db (AsyncSession): The asynchronous database session.
        instance_id (UUID): The ID of the EvolutionInstance to retrieve.
        account_id (Optional[UUID]): If provided, ensures the instance belongs to this account.

    Returns:
        Optional[EvolutionInstance]: The EvolutionInstance object if found, else None.
    """
    stmt = select(EvolutionInstance).where(EvolutionInstance.id == instance_id)
    if account_id:
        stmt = stmt.where(EvolutionInstance.account_id == account_id)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_evolution_instance_for_linking(
    db: AsyncSession, instance_id: UUID, account_id: UUID
) -> EvolutionInstance:
    """
    Retrieves an EvolutionInstance by its ID and account ID, ensuring it's available for linking.
    An instance is available for linking if it exists, belongs to the account,
    and is not already associated with an Inbox.

    Args:
        db (AsyncSession): The asynchronous database session.
        instance_id (UUID): The ID of the EvolutionInstance to retrieve and validate.
        account_id (UUID): The ID of the account that should own the instance.

    Returns:
        EvolutionInstance: The validated EvolutionInstance object, ready for linking.

    Raises:
        ValueError: If the instance is not found, does not belong to the account,
                    or is already linked to an existing inbox.
    """
    logger.info(
        f"Attempting to retrieve Evolution Instance ID: {instance_id} for Account ID: {account_id} for linking."
    )
    stmt = (
        select(EvolutionInstance)
        .where(
            EvolutionInstance.id == instance_id,
            EvolutionInstance.account_id == account_id,
        )
        .options(
            selectinload(EvolutionInstance.inbox)
        )  # Eager load the inbox relationship
    )
    result = await db.execute(stmt)
    instance: Optional[EvolutionInstance] = result.scalar_one_or_none()

    if not instance:
        logger.warning(
            f"Evolution Instance ID {instance_id} not found or not authorized for Account {account_id}."
        )
        raise ValueError(
            f"Evolution Instance with ID {instance_id} not found or not accessible for this account."
        )

    if instance.inbox is not None:
        logger.warning(
            f"Evolution Instance ID {instance_id} is already linked to Inbox ID {instance.inbox.id}."
        )
        raise ValueError(
            f"Evolution Instance {instance_id} is already linked to another inbox (ID: {instance.inbox.id})."
        )

    logger.info(
        f"Evolution Instance ID {instance_id} (Name: {instance.instance_name}) validated and available for linking."
    )
    return instance
