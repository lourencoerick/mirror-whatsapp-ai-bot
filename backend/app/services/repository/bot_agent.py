# backend/app/services/repository/bot_agent_repo.py

from typing import Optional, List, Sequence
from uuid import UUID

from loguru import logger
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

# Import Models and Schemas
from app.models.bot_agent import BotAgent
from app.models.bot_agent_inbox import BotAgentInbox
from app.models.inbox import Inbox
from app.api.schemas.bot_agent import BotAgentUpdate


async def get_agent_by_account_id(
    db: AsyncSession, account_id: UUID
) -> Optional[BotAgent]:
    """
    Retrieves the BotAgent associated with a specific account ID.
    Assumes only one agent per account for now.

    Args:
        db: The SQLAlchemy async session.
        account_id: The UUID of the account.

    Returns:
        The BotAgent object if found, otherwise None.
    """
    logger.debug(f"Fetching BotAgent for account_id: {account_id}")
    stmt = select(BotAgent).where(BotAgent.account_id == account_id)
    result = await db.execute(stmt)
    agent = result.scalars().first()
    if agent:
        logger.debug(f"Found BotAgent with id: {agent.id} for account {account_id}")
    else:
        logger.warning(f"No BotAgent found for account_id: {account_id}")
    return agent


async def get_or_create_agent_by_account_id(
    db: AsyncSession, account_id: UUID
) -> BotAgent:
    """
    Retrieves the BotAgent for an account, creating a default one if it doesn't exist.

    Args:
        db: The SQLAlchemy async session.
        account_id: The UUID of the account.

    Returns:
        The existing or newly created BotAgent object.
    """
    agent = await get_agent_by_account_id(db, account_id)
    if agent:
        return agent

    logger.info(f"No BotAgent found for account {account_id}, creating default.")
    # Create default agent (name is set by model default)
    default_agent = BotAgent(account_id=account_id)
    try:
        db.add(default_agent)
        await db.flush()
        await db.refresh(default_agent)
        logger.info(
            f"Created default BotAgent {default_agent.id} for account {account_id}"
        )
        return default_agent
    except Exception as e:
        logger.exception(
            f"Failed to create default BotAgent for account {account_id}: {e}"
        )
        # Re-raise the exception so the transaction can be rolled back by the caller
        raise


async def update_agent(
    db: AsyncSession, *, db_agent: BotAgent, agent_in: BotAgentUpdate
) -> BotAgent:
    """
    Updates an existing BotAgent record.

    Args:
        db: The SQLAlchemy async session.
        db_agent: The existing BotAgent object to update.
        agent_in: The Pydantic schema containing the fields to update.

    Returns:
        The updated BotAgent object.
    """
    logger.info(f"Updating BotAgent with id: {db_agent.id}")
    # Get data from schema, excluding unset fields to allow partial updates
    update_data = agent_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        # Check if the field exists in the model before setting
        if hasattr(db_agent, field):
            setattr(db_agent, field, value)
        else:
            logger.warning(
                f"Attempted to update non-existent field '{field}' on BotAgent"
            )

    try:
        db.add(db_agent)  # Add the modified object to the session
        await db.flush()
        await db.refresh(db_agent)
        logger.info(f"Successfully updated BotAgent {db_agent.id}")
        return db_agent
    except Exception as e:
        logger.error(f"Error updating BotAgent {db_agent.id}: {e}")
        raise


async def get_agent_for_inbox(
    db: AsyncSession, *, inbox_id: UUID, account_id: UUID
) -> Optional[BotAgent]:
    """
    Finds the BotAgent assigned to a specific Inbox within an Account.

    Args:
        db: The SQLAlchemy async session.
        inbox_id: The UUID of the Inbox.
        account_id: The UUID of the Account owning the Inbox.

    Returns:
        The assigned BotAgent object, or None if no agent is assigned.
    """
    logger.debug(
        f"Checking for assigned BotAgent for Inbox {inbox_id} in Account {account_id}"
    )
    stmt = (
        select(BotAgent)
        .join(BotAgentInbox, BotAgent.id == BotAgentInbox.bot_agent_id)
        .where(BotAgentInbox.inbox_id == inbox_id)
        .where(
            BotAgentInbox.account_id == account_id
        )  # Ensure it's the correct account
        .options(selectinload(BotAgent.account))  # Optional: Load account if needed
    )
    result = await db.execute(stmt)
    agent = result.scalars().first()
    if agent:
        logger.debug(f"Inbox {inbox_id} is assigned to BotAgent {agent.id}")
    else:
        logger.debug(f"No BotAgent assigned to Inbox {inbox_id}")
    return agent


async def get_inboxes_for_agent(db: AsyncSession, agent_id: UUID) -> List[Inbox]:
    """
    Retrieves all Inboxes associated with a specific BotAgent.

    Args:
        db: The SQLAlchemy async session.
        agent_id: The UUID of the BotAgent.

    Returns:
        A list of associated Inbox objects.
    """
    logger.debug(f"Fetching Inboxes associated with BotAgent {agent_id}")
    stmt = (
        select(Inbox)
        .join(BotAgentInbox, Inbox.id == BotAgentInbox.inbox_id)
        .where(BotAgentInbox.bot_agent_id == agent_id)
        .options(joinedload(Inbox.account))  # Eager load account for context
    )
    result = await db.execute(stmt)
    inboxes = result.scalars().all()
    logger.debug(f"Found {len(inboxes)} Inboxes for BotAgent {agent_id}")
    return list(inboxes)


async def set_agent_inboxes(
    db: AsyncSession, *, agent: BotAgent, inbox_ids: List[UUID]
) -> None:
    """
    Sets the complete list of associated Inboxes for a BotAgent.

    Removes existing associations not in the provided list and adds new ones.

    Args:
        db: The SQLAlchemy async session.
        agent: The BotAgent object whose associations are being set.
        inbox_ids: The complete list of Inbox UUIDs that should be associated.
    """
    account_id = agent.account_id
    agent_id = agent.id
    logger.info(
        f"Setting Inboxes for BotAgent {agent_id} (Account: {account_id}) to: {inbox_ids}"
    )

    # 1. Get current associations
    current_assoc_stmt = select(BotAgentInbox.inbox_id).where(
        BotAgentInbox.bot_agent_id == agent_id
    )
    result = await db.execute(current_assoc_stmt)
    current_inbox_ids = set(result.scalars().all())
    target_inbox_ids = set(inbox_ids)

    # 2. Identify associations to remove
    ids_to_remove = current_inbox_ids - target_inbox_ids
    if ids_to_remove:
        logger.debug(f"Removing associations for Inboxes: {ids_to_remove}")
        delete_stmt = delete(BotAgentInbox).where(
            BotAgentInbox.bot_agent_id == agent_id,
            BotAgentInbox.inbox_id.in_(ids_to_remove),
        )
        await db.execute(delete_stmt)

    # 3. Identify associations to add
    ids_to_add = target_inbox_ids - current_inbox_ids
    if ids_to_add:
        logger.debug(f"Adding associations for Inboxes: {ids_to_add}")
        new_associations = [
            BotAgentInbox(
                account_id=account_id, bot_agent_id=agent_id, inbox_id=inbox_id
            )
            for inbox_id in ids_to_add
        ]
        db.add_all(new_associations)

    # Flush changes within this operation
    try:
        await db.flush()
        logger.info(f"Inbox associations updated successfully for BotAgent {agent_id}")
    except Exception as e:
        logger.error(
            f"Error flushing inbox association changes for BotAgent {agent_id}: {e}"
        )
        # Re-raise to allow caller (API endpoint) to handle rollback
        raise
