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


async def get_bot_agent_by_id(
    db: AsyncSession,
    account_id: UUID,
    bot_agent_id: UUID,
) -> Optional[BotAgent]:
    """
    Retrieves the BotAgent by its ID, ensuring it belongs to the specified account.

    Args:
        db: The SQLAlchemy async session.
        account_id: The UUID of the account owner.
        bot_agent_id: The UUID of the bot agent.

    Returns:
        The BotAgent object if found and owned by the account, otherwise None.
    """
    logger.debug(f"Fetching BotAgent for bot_agent_id: {bot_agent_id}")
    stmt = select(BotAgent).where(
        BotAgent.id == bot_agent_id, BotAgent.account_id == account_id
    )
    result = await db.execute(stmt)
    agent = result.scalars().first()
    if agent:
        logger.debug(f"Found BotAgent with id: {agent.id} for account {account_id}")
    else:
        logger.warning(
            f"No BotAgent found with id {bot_agent_id} for account {account_id}"
        )
    return agent


async def get_bot_agent_by_account_id(
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


async def get_or_create_bot_agent_by_account_id(
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
    agent = await get_bot_agent_by_account_id(db, account_id)
    if agent:
        return agent
    logger.info(f"No BotAgent found for account {account_id}, creating default.")
    default_bot_agent = BotAgent(account_id=account_id)
    try:
        db.add(default_bot_agent)
        await db.flush()
        await db.refresh(default_bot_agent)
        logger.info(
            f"Created default BotAgent {default_bot_agent.id} for account {account_id}"
        )
        return default_bot_agent
    except Exception as e:
        logger.exception(
            f"Failed to create default BotAgent for account {account_id}: {e}"
        )
        raise


async def update_bot_agent(
    db: AsyncSession, *, bot_agent: BotAgent, agent_in: BotAgentUpdate
) -> BotAgent:
    """
    Updates an existing BotAgent record.

    Args:
        db: The SQLAlchemy async session.
        bot_agent: The existing BotAgent object to update.
        agent_in: The Pydantic schema containing the fields to update.

    Returns:
        The updated BotAgent object.
    """
    logger.info(f"Updating BotAgent with id: {bot_agent.id}")
    update_data = agent_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(bot_agent, field):
            setattr(bot_agent, field, value)
        else:
            logger.warning(
                f"Attempted to update non-existent field '{field}' on BotAgent"
            )
    try:
        db.add(bot_agent)
        await db.flush()
        await db.refresh(bot_agent)
        logger.info(f"Successfully updated BotAgent {bot_agent.id}")
        return bot_agent
    except Exception as e:
        logger.error(f"Error updating BotAgent {bot_agent.id}: {e}")
        raise


async def get_bot_agent_for_inbox(
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
        .where(BotAgentInbox.account_id == account_id)
        .options(selectinload(BotAgent.account))
    )
    result = await db.execute(stmt)
    agent = result.scalars().first()
    if agent:
        logger.debug(f"Inbox {inbox_id} is assigned to BotAgent {agent.id}")
    else:
        logger.debug(f"No BotAgent assigned to Inbox {inbox_id}")
    return agent


async def get_inboxes_for_bot_agent(
    db: AsyncSession, bot_agent_id: UUID
) -> List[Inbox]:
    """
    Retrieves all Inboxes associated with a specific BotAgent.

    Args:
        db: The SQLAlchemy async session.
        bot_agent_id: The UUID of the BotAgent.

    Returns:
        A list of associated Inbox objects.
    """
    logger.debug(f"Fetching Inboxes associated with BotAgent {bot_agent_id}")
    stmt = (
        select(Inbox)
        .join(BotAgentInbox, Inbox.id == BotAgentInbox.inbox_id)
        .where(BotAgentInbox.bot_agent_id == bot_agent_id)
        .options(joinedload(Inbox.account))
    )
    result = await db.execute(stmt)
    inboxes = result.scalars().all()
    logger.debug(f"Found {len(inboxes)} Inboxes for BotAgent {bot_agent_id}")
    return list(inboxes)


async def set_bot_agent_inboxes(
    db: AsyncSession, *, bot_agent: BotAgent, inbox_ids: List[UUID]
) -> None:
    """
    Sets the complete list of associated Inboxes for a BotAgent.

    Removes existing associations not in the provided list and adds new ones.

    Args:
        db: The SQLAlchemy async session.
        agent: The BotAgent object whose associations are being set.
        inbox_ids: The complete list of Inbox UUIDs that should be associated.
    """
    account_id = bot_agent.account_id
    bot_agent_id = bot_agent.id  # Use agent_id consistently now
    logger.info(
        f"Setting Inboxes for BotAgent {bot_agent_id} (Account: {account_id}) to: {inbox_ids}"
    )

    # 1. Get current associations
    current_assoc_stmt = select(BotAgentInbox.inbox_id).where(
        # Corrected where condition:
        BotAgentInbox.bot_agent_id
        == bot_agent_id
    )
    result = await db.execute(current_assoc_stmt)
    current_inbox_ids = set(result.scalars().all())
    target_inbox_ids = set(inbox_ids)

    # 2. Identify associations to remove
    ids_to_remove = current_inbox_ids - target_inbox_ids
    if ids_to_remove:
        logger.debug(f"Removing associations for Inboxes: {ids_to_remove}")
        delete_stmt = delete(BotAgentInbox).where(
            # Corrected where condition:
            BotAgentInbox.bot_agent_id == bot_agent_id,
            BotAgentInbox.inbox_id.in_(ids_to_remove),
        )
        await db.execute(delete_stmt)

    # 3. Identify associations to add
    ids_to_add = target_inbox_ids - current_inbox_ids
    if ids_to_add:
        logger.debug(f"Adding associations for Inboxes: {ids_to_add}")
        new_associations = [
            BotAgentInbox(
                account_id=account_id,
                # Corrected column name:
                bot_agent_id=bot_agent_id,
                inbox_id=inbox_id,
            )
            for inbox_id in ids_to_add
        ]
        db.add_all(new_associations)

    # Flush changes within this operation
    try:
        await db.flush()
        logger.info(
            f"Inbox associations updated successfully for BotAgent {bot_agent_id}"
        )
    except Exception as e:
        logger.error(
            f"Error flushing inbox association changes for BotAgent {bot_agent_id}: {e}"
        )
        raise
