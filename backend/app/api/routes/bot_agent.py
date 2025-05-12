# backend/app/api/routers/bot_agent.py

from fastapi import APIRouter, Depends, HTTPException, status, Response
from loguru import logger
from uuid import UUID
from typing import List

# SQLAlchemy Session and Models/Schemas
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.bot_agent import BotAgent
from app.models.inbox import Inbox  # Needed for response model hint
from app.api.schemas.bot_agent import (
    BotAgentRead,
    BotAgentCreate,
    BotAgentUpdate,
    AgentInboxAssociationUpdate,
    # AgentInboxAssociationRead, # If needed later
)
from app.api.schemas.inbox import InboxRead  # Schema for returning associated inboxes

# Repository Functions
from app.services.repository import bot_agent as bot_agent_repo

# Auth Context
from app.core.dependencies.auth import get_auth_context, AuthContext


# Define the router
router = APIRouter(
    prefix="/bot-agents",  # Base prefix for this router
    tags=["v1 - Bot Agents"],  # Tag for API documentation
)


# --- Helper Function to Get Agent (and check ownership) ---
async def get_agent_or_404(
    bot_agent_id: UUID, account_id: UUID, db: AsyncSession
) -> BotAgent:
    """Helper to get agent by ID and verify ownership, raising 404 if not found/owned."""
    bot_agent = await bot_agent_repo.get_bot_agent_by_id(
        db, bot_agent_id=bot_agent_id, account_id=account_id
    )  # Assumes get_agent_by_id exists
    if not bot_agent or bot_agent.account_id != account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bot Agent not found."
        )
    return bot_agent


# --- Endpoints ---


@router.get(
    "/",
    response_model=List[BotAgentRead],
    summary="List Bot Agents for Account",
    description="Retrieves Bot Agents associated with the authenticated user's active account. Currently, it's expected that an account has at most one Bot Agent.",
)
async def list_bot_agents(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> List[BotAgent]:
    """Lists Bot Agents for the current account.

    In the current system design, an account typically has one primary Bot Agent.
    This endpoint retrieves that agent, returned within a list.

    Args:
        auth_context: The authentication context containing user and account info.
        db: The SQLAlchemy async session.

    Returns:
        A list containing the BotAgent if found, or an empty list if not.
    """
    account_id = auth_context.account.id
    logger.info(f"Listing Bot Agents for account {account_id}")
    bot_agent = await bot_agent_repo.get_bot_agent_by_account_id(
        db=db, account_id=account_id
    )
    return [bot_agent] if bot_agent else []


@router.post(
    "/",
    response_model=BotAgentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Bot Agent",
    description="Creates a new Bot Agent for the authenticated user's account. An account can only have one Bot Agent.",
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Bot Agent already exists for this account"
        },
    },
)
async def create_bot_agent(
    bot_agent_data: BotAgentCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> BotAgent:
    """Creates a new Bot Agent for the account.

    If a Bot Agent already exists for the account, a 409 Conflict error is returned.
    The new agent is automatically linked to the account's simulation inbox.

    Args:
        bot_agent_data: Data for creating the new Bot Agent.
        auth_context: The authentication context.
        db: The SQLAlchemy async session.

    Returns:
        The created BotAgent.

    Raises:
        HTTPException: 409 if agent already exists, 500 on other creation failures.
    """
    account_id = auth_context.account.id
    logger.info(
        f"Attempting to create Bot Agent for account {account_id} with data: {bot_agent_data.model_dump()}"
    )

    try:
        bot_agent = await bot_agent_repo.create_bot_agent(
            db=db, account_id=account_id, bot_agent_data=bot_agent_data
        )
        await db.commit()
        await db.refresh(bot_agent)
        logger.info(
            f"Bot Agent {bot_agent.id} created successfully for account {account_id}."
        )
        return bot_agent
    except ValueError as ve:
        await db.rollback()
        logger.warning(f"Conflict creating Bot Agent for account {account_id}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ve),
        ) from ve
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error creating Bot Agent for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Bot Agent due to an internal error.",
        ) from e


@router.get(
    "/{bot_agent_id}",
    response_model=BotAgentRead,
    summary="Get Bot Agent Details",
    description="Retrieves details for a specific Bot Agent by its ID, ensuring it belongs to the user's account.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Bot Agent not found"}},
)
async def get_bot_agent_details(
    bot_agent_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> BotAgent:
    """Gets details of a specific Bot Agent.

    Ensures the requested Bot Agent belongs to the authenticated user's account.

    Args:
        bot_agent_id: The UUID of the Bot Agent to retrieve.
        auth_context: The authentication context.
        db: The SQLAlchemy async session.

    Returns:
        The BotAgent if found and owned by the account.

    Raises:
        HTTPException: 404 if not found or not owned.
    """
    account_id = auth_context.account.id
    logger.info(
        f"Getting details for Bot Agent {bot_agent_id} for account {account_id}"
    )
    # Need get_agent_by_id in repo
    bot_agent = await bot_agent_repo.get_bot_agent_by_id(
        db=db, bot_agent_id=bot_agent_id, account_id=account_id
    )
    if not bot_agent or bot_agent.account_id != account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bot Agent not found"
        )
    return bot_agent


@router.put(
    "/{bot_agent_id}",
    response_model=BotAgentRead,
    summary="Update Bot Agent",
    description="Updates the configuration of a specific Bot Agent.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Bot Agent not found"}},
)
async def update_bot_agent(
    bot_agent_id: UUID,
    agent_update: BotAgentUpdate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> BotAgent:
    """Updates a specific Bot Agent's settings.

    Args:
        bot_agent_id: The UUID of the Bot Agent to update.
        agent_update: The data containing updates for the Bot Agent.
        auth_context: The authentication context.
        db: The SQLAlchemy async session.

    Returns:
        The updated BotAgent.

    Raises:
        HTTPException: 404 if not found, 500 on update failure.
    """
    account_id = auth_context.account.id
    logger.info(f"Updating Bot Agent {bot_agent_id} for account {account_id}")

    # Get the existing agent, ensuring ownership
    bot_agent = await get_agent_or_404(
        bot_agent_id=bot_agent_id, account_id=account_id, db=db
    )

    try:
        updated_agent = await bot_agent_repo.update_bot_agent(
            db=db, bot_agent=bot_agent, agent_in=agent_update
        )
        await db.commit()
        await db.refresh(updated_agent)  # Refresh to get latest state after commit
        logger.info(f"Bot Agent {bot_agent_id} updated successfully.")
        return updated_agent
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error updating Bot Agent {bot_agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Bot Agent.",
        ) from e


@router.get(
    "/{bot_agent_id}/inboxes",
    response_model=List[InboxRead],  # Use the InboxRead schema
    summary="List Associated Inboxes",
    description="Retrieves the list of Inboxes currently associated with the specified Bot Agent.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Bot Agent not found"}},
)
async def get_agent_associated_inboxes(
    bot_agent_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> List[Inbox]:  # Return list of Inbox models
    """Gets Inboxes associated with a Bot Agent.

    Args:
        bot_agent_id: The UUID of the Bot Agent.
        auth_context: The authentication context.
        db: The SQLAlchemy async session.

    Returns:
        A list of Inbox models associated with the agent.
    """
    account_id = auth_context.account.id
    logger.info(f"Getting Inboxes for Bot Agent {bot_agent_id} (Account: {account_id})")

    # Verify agent exists and belongs to the account
    await get_agent_or_404(bot_agent_id=bot_agent_id, account_id=account_id, db=db)

    inboxes = await bot_agent_repo.get_inboxes_for_bot_agent(
        db=db, bot_agent_id=bot_agent_id
    )
    return inboxes


@router.put(
    "/{bot_agent_id}/inboxes",
    status_code=status.HTTP_204_NO_CONTENT,  # No content needed on successful update
    summary="Set Associated Inboxes",
    description="Sets the complete list of Inboxes associated with the Bot Agent. Replaces any existing associations.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Bot Agent not found"},
        status.HTTP_400_BAD_REQUEST: {
            "description": "One or more Inbox IDs are invalid or do not belong to the account"
        },
    },
)
async def set_agent_associated_inboxes(
    bot_agent_id: UUID,
    association_data: AgentInboxAssociationUpdate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Sets the Inboxes associated with a Bot Agent.

    This operation replaces all current inbox associations for the agent with the
    provided list. It also handles updating conversation statuses in inboxes
    that are being disassociated from the agent.

    Args:
        bot_agent_id: The UUID of the Bot Agent.
        association_data: Data containing the list of Inbox IDs to associate.
        auth_context: The authentication context.
        db: The SQLAlchemy async session.

    Returns:
        A 204 No Content response on success.

    Raises:
        HTTPException: 404 if agent not found, 400 if inbox IDs are problematic,
                       500 on other failures.
    """
    account_id = auth_context.account.id
    inbox_ids = association_data.inbox_ids
    logger.info(
        f"Setting Inboxes for Bot Agent {bot_agent_id} (Account: {account_id}) to: {inbox_ids}"
    )

    # Get the agent, ensuring ownership
    bot_agent = await get_agent_or_404(
        bot_agent_id=bot_agent_id, account_id=account_id, db=db
    )

    # **Optional but Recommended:** Validate that all provided inbox_ids exist
    # and belong to the current account_id before proceeding.
    # This requires a new repository function like `validate_inbox_ids(db, account_id, inbox_ids)`
    # if not await validate_inbox_ids(db, account_id, inbox_ids):
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inaccessible Inbox IDs provided.")

    try:
        await bot_agent_repo.set_bot_agent_inboxes(
            db=db, bot_agent=bot_agent, inbox_ids=inbox_ids
        )
        await db.commit()
        logger.info(f"Successfully set Inboxes for Bot Agent {bot_agent_id}")
        # Return 204 No Content on success
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error setting Inboxes for Bot Agent {bot_agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Inbox associations.",
        ) from e
