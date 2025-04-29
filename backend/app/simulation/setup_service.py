# app/simulation/setup_service.py
from loguru import logger
from typing import Tuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession

# Import models
from app.models import (
    Account,
    Contact,
    Conversation,
    Inbox,
    ContactInbox,
    User,
)

# Import repository functions/modules (adapt based on how you import/use them)
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo
from app.services.repository import inbox as inbox_repo

# Import schemas used by repository functions
from app.api.schemas.contact import ContactCreate
from app.api.schemas.inbox import InboxCreate

# Import Enum if needed
from app.models.conversation import ConversationStatusEnum

# Import constants for names (adapt path if needed)
from app.config import get_settings, Settings

settings: Settings = get_settings()

from app.simulation.config import (
    SIMULATION_INBOX_NAME,
    SIMULATION_CONTACT_NAME,
    SIMULATION_CONTACT_PHONE_NUMBER,
)


async def _fetch_existing_entities(
    session: AsyncSession, account: Account
) -> Optional[Tuple[Inbox, Contact, Conversation]]:
    """Fetches existing primary simulation entities using IDs stored on the Account.

    Args:
        session: The AsyncSession for database operations.
        account: The hydrated Account object containing the simulation IDs.

    Returns:
        A tuple (Inbox, Contact, Conversation) if all primary simulation
        entities are found, otherwise None.

    Raises:
        RuntimeError: If simulation IDs are present on the Account but the
            corresponding entities cannot be found in the database, indicating
            an inconsistency.
    """
    if not (
        account.simulation_inbox_id
        and account.simulation_contact_id
        and account.simulation_conversation_id
    ):
        return None  # Not fully set up

    sim_inbox = await session.get(Inbox, account.simulation_inbox_id)
    sim_contact = await session.get(Contact, account.simulation_contact_id)
    sim_conversation = await session.get(
        Conversation, account.simulation_conversation_id
    )

    if not (sim_inbox and sim_contact and sim_conversation):
        logger.error(
            f"Inconsistency detected for account {account.id}: "
            f"Simulation IDs present on Account, but corresponding entities not found in DB. "
            f"Inbox ID: {account.simulation_inbox_id}, "
            f"Contact ID: {account.simulation_contact_id}, "
            f"Conversation ID: {account.simulation_conversation_id}"
        )
        raise RuntimeError(f"Simulation entity inconsistency for account {account.id}")

    logger.info(
        f"Found existing simulation entities for account {account.id} via stored IDs."
    )
    return sim_inbox, sim_contact, sim_conversation


async def setup_simulation_environment(
    session: AsyncSession, account: Account, user: User  # Pass the primary user object
) -> Tuple[Inbox, Contact, Conversation]:
    """Ensures the primary simulation entities exist for an account.

    Checks if the primary simulation Inbox, Contact, and Conversation IDs are
    already stored on the Account model. If yes, fetches and returns the
    existing entities. If not, it creates the necessary entities (Inbox,
    Contact, ContactInbox link, Conversation), marks them as simulation
    entities, updates the Account model with their IDs, and returns the
    newly created entities.

    This function relies on the calling context (e.g., a Unit of Work)
    to commit the transaction changes. It performs flushes internally
    to ensure IDs are available and the Account object is updated within
    the session state.

    Args:
        session: The AsyncSession for database operations.
        account: The hydrated Account object for which to set up simulation.
        user: The primary User object associated with the account, needed for
                creating the initial InboxMember link.

    Returns:
        A tuple containing the primary simulation (Inbox, Contact, Conversation).

    Raises:
        RuntimeError: If entity creation fails or inconsistencies are detected
                        during the fetch of existing entities.
        Exception: Propagates exceptions from underlying repository calls or
                    database operations.
    """
    # --- Idempotency Check ---
    existing_entities = await _fetch_existing_entities(session=session, account=account)
    if existing_entities:
        return existing_entities

    # Handle partial setup
    if (
        account.simulation_inbox_id
        or account.simulation_contact_id
        or account.simulation_conversation_id
    ):
        logger.warning(
            f"Partial simulation setup detected for account {account.id}. Attempting to recreate."
        )
        account.simulation_inbox_id = None
        account.simulation_contact_id = None
        account.simulation_conversation_id = None
        session.add(account)
        await session.flush([account])  # Flush the reset

    logger.info(
        f"Setting up primary simulation environment for account {account.id}..."
    )
    try:
        # 1. Create Simulation Inbox using the repository function
        # Prepare data according to InboxCreate schema used by create_inbox
        inbox_data = InboxCreate(
            name=SIMULATION_INBOX_NAME,
            channel_type="simulation",  # Use 'simulation' type
            # channel_details might not be needed for simulation, or set minimally
            initial_conversation_status=ConversationStatusEnum.BOT,
            channel_details={"type": "simulation", "id": "simulation-id"},
            enable_auto_assignment=None,
            # Set initial status if applicable in your schema/logic
            # initial_conversation_status=ConversationStatusEnum.BOT, # Example
            # Other fields from InboxCreate as needed
        )
        # Call the function directly, passing the session
        sim_inbox = await inbox_repo.create_inbox(
            db=session,
            account_id=account.id,
            user_id=user.id,
            inbox_data=inbox_data,
        )
        # The create_inbox function should have flushed, making sim_inbox.id available
        if not sim_inbox or not sim_inbox.id:
            raise RuntimeError(
                f"Failed to create simulation inbox or get its ID for account {account.id}"
            )
        # Mark as simulation explicitly (if create_inbox doesn't handle it)
        if not sim_inbox.is_simulation:
            sim_inbox.is_simulation = True
            session.add(sim_inbox)
            await session.flush([sim_inbox])
        logger.info(f"Created simulation inbox {sim_inbox.id} for account {account.id}")

        # 2. Create Simulation Contact using the repository function
        contact_data = ContactCreate(
            name=SIMULATION_CONTACT_NAME,
            phone_number=SIMULATION_CONTACT_PHONE_NUMBER,  # Add phone if needed/required
            # Add other fields from ContactCreate if necessary
        )
        sim_contact = await contact_repo.create_contact(
            db=session,
            account_id=account.id,
            contact_data=contact_data,
        )
        if not sim_contact or not sim_contact.id:
            raise RuntimeError(
                f"Failed to create simulation contact or get its ID for account {account.id}"
            )
        # Mark as simulation explicitly
        if not sim_contact.is_simulation:
            sim_contact.is_simulation = True
            session.add(sim_contact)
            await session.flush([sim_contact])
        logger.info(
            f"Created simulation contact {sim_contact.id} for account {account.id}"
        )

        # 3. Get or Create ContactInbox link
        # Use a consistent source_id for simulation setup
        contact_inbox = await contact_repo.get_or_create_contact_inbox(
            db=session,
            account_id=account.id,
            contact_id=sim_contact.id,
            inbox_id=sim_inbox.id,
            source_id="simulation_setup",
        )
        if not contact_inbox or not contact_inbox.id:
            raise RuntimeError(
                f"Failed to get/create contact_inbox link for account {account.id}"
            )
        logger.info(
            f"Ensured ContactInbox link {contact_inbox.id} for account {account.id}"
        )

        # 4. Get or Create Simulation Conversation using the repository function
        sim_conversation = await conversation_repo.get_or_create_conversation(
            db=session,
            account_id=account.id,
            inbox_id=sim_inbox.id,
            contact_inbox_id=contact_inbox.id,
            status=ConversationStatusEnum.OPEN,
        )
        if not sim_conversation or not sim_conversation.id:
            raise RuntimeError(
                f"Failed to get/create simulation conversation for account {account.id}"
            )
        # Mark as simulation explicitly
        if not sim_conversation.is_simulation:
            sim_conversation.is_simulation = True
            session.add(sim_conversation)
            await session.flush([sim_conversation])
        logger.info(
            f"Ensured simulation conversation {sim_conversation.id} for account {account.id}"
        )

        # 5. Update Account with the new IDs
        account.simulation_inbox_id = sim_inbox.id
        account.simulation_contact_id = sim_contact.id
        account.simulation_conversation_id = sim_conversation.id
        session.add(account)
        await session.flush([account])
        logger.info(f"Updated account {account.id} with simulation entity IDs.")

        logger.info(
            f"Successfully set up simulation environment for account {account.id}"
        )
        # Return the main entities
        return sim_inbox, sim_contact, sim_conversation

    except Exception as e:
        logger.error(
            f"Failed to set up simulation environment for account {account.id}: {e}",
            exc_info=True,
        )
        # Let the calling context handle commit/rollback.
        raise
