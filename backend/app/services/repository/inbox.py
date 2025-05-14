from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import select, update, delete
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger
from sqlalchemy.exc import IntegrityError
import enum

from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember
from app.models.bot_agent_inbox import BotAgentInbox
from app.api.schemas.inbox import InboxCreate, InboxUpdate
from app.models.conversation import ConversationStatusEnum
from app.models.channels.channel_types import ChannelTypeEnum
from app.services.repository.whatsapp_cloud_config import (
    create_whatsapp_cloud_config,
)

from app.services.repository import evolution_instance as evolution_instance_repo


async def create_inbox(
    db: AsyncSession,
    account_id: UUID,
    user_id: UUID,  # User creating the inbox, becomes a member
    inbox_data: InboxCreate,
) -> Inbox:
    """Creates a new inbox and its channel-specific configuration if applicable.

    Args:
        db (AsyncSession): The asynchronous database session.
        account_id (UUID): The ID of the account this inbox belongs to.
        user_id (UUID): The ID of the user creating the inbox.
        inbox_data (InboxCreate): Data for creating the new inbox, including
                                  channel-specific configurations.

    Returns:
        Inbox: The newly created Inbox SQLAlchemy object, with relationships loaded.

    Raises:
        ValueError: If channel configuration is invalid or instance is already linked.
        IntegrityError: If a unique constraint is violated (e.g., duplicate channel).
        Exception: For other database-related errors.
    """
    logger.info(
        f"Attempting to create inbox '{inbox_data.name}' of type '{inbox_data.channel_type.value}' "
        f"for Account ID: {account_id}"
    )

    evolution_instance_id: Optional[UUID] = None
    whatsapp_cloud_config_id: Optional[UUID] = None
    channel_id_value: Optional[str] = None
    is_simulation_channel: bool = False

    if inbox_data.channel_type == ChannelTypeEnum.WHATSAPP_EVOLUTION:
        if not inbox_data.evolution_instance_to_link:
            # This should ideally be caught by Pydantic validator in InboxCreate
            raise ValueError(
                "evolution_instance_to_link is required for WHATSAPP_EVOLUTION channel type."
            )

        platform_instance_id = (
            inbox_data.evolution_instance_to_link.platform_instance_id
        )
        logger.info(f"Linking to Evolution Instance ID: {platform_instance_id}")

        try:
            linked_evolution_instance = (
                await evolution_instance_repo.get_evolution_instance_for_linking(
                    db, instance_id=platform_instance_id, account_id=account_id
                )
            )
        except ValueError as e:  # Catch specific error from the repo function
            logger.warning(
                f"Failed to get Evolution Instance for linking. Instance ID: {platform_instance_id}, Account ID: {account_id}. Error: {e}"
            )
            raise  # Re-raise the ValueError to be handled by the endpoint

        evolution_instance_id = linked_evolution_instance.id
        channel_id_value = linked_evolution_instance.instance_name
        logger.info(
            f"Successfully validated Evolution Instance. Name: {channel_id_value}"
        )

    elif inbox_data.channel_type == ChannelTypeEnum.WHATSAPP_CLOUD:
        if not inbox_data.whatsapp_cloud_config_to_create:
            # Pydantic validator should catch this
            raise ValueError(
                "whatsapp_cloud_config_to_create is required for WHATSAPP_CLOUD channel type."
            )

        logger.info("Creating new WhatsApp Cloud Configuration.")
        new_wacc_config = await create_whatsapp_cloud_config(
            db=db,
            account_id=account_id,
            config_data=inbox_data.whatsapp_cloud_config_to_create,
        )
        # create_whatsapp_cloud_config already adds to session and flushes if successful
        whatsapp_cloud_config_id = new_wacc_config.id
        channel_id_value = new_wacc_config.phone_number_id
        logger.info(
            f"WhatsApp Cloud Configuration created with ID: {whatsapp_cloud_config_id}, Phone ID: {channel_id_value}"
        )

    elif inbox_data.channel_type == ChannelTypeEnum.SIMULATION:
        channel_id_value = f"sim_{uuid4().hex[:12]}"
        is_simulation_channel = True
        logger.info(f"Simulation channel. Generated channel_id: {channel_id_value}")

    else:
        # Should not happen if ChannelTypeEnum is exhaustive and Pydantic validates
        logger.error(f"Unsupported channel type: {inbox_data.channel_type}")
        raise ValueError(f"Unsupported channel type: {inbox_data.channel_type}")

    if not channel_id_value:
        # This is a safeguard, should be set by logic above.
        logger.error("channel_id_value was not set during inbox creation process.")
        raise ValueError("Internal error: Channel ID could not be determined.")

    try:
        new_inbox_model = Inbox(
            account_id=account_id,
            name=inbox_data.name,
            channel_type=inbox_data.channel_type.value,
            channel_id=channel_id_value,
            evolution_instance_id=evolution_instance_id,
            whatsapp_cloud_config_id=whatsapp_cloud_config_id,
            channel_details=(
                inbox_data.channel_details if inbox_data.channel_details else {}
            ),
            initial_conversation_status=inbox_data.initial_conversation_status,
            enable_auto_assignment=inbox_data.enable_auto_assignment,
            is_simulation=is_simulation_channel,
        )
        db.add(new_inbox_model)
        await db.flush()

        # Associate the creating user as a member of the inbox
        inbox_member = InboxMember(user_id=user_id, inbox_id=new_inbox_model.id)
        db.add(inbox_member)

        await db.flush()  # Flush to get IDs and check constraints before full commit

        await db.refresh(new_inbox_model)
        await db.refresh(inbox_member)

        relationships_to_load = []
        if new_inbox_model.evolution_instance_id:
            relationships_to_load.append("evolution_instance")
        if new_inbox_model.whatsapp_cloud_config_id:
            relationships_to_load.append("whatsapp_cloud_config")

        if relationships_to_load:
            logger.debug(
                f"Refreshing new_inbox_model (ID: {new_inbox_model.id}) with relationships: {relationships_to_load}"
            )
            await db.refresh(new_inbox_model, relationships_to_load)
            # Verificar se os relacionamentos foram carregados
            if "evolution_instance" in relationships_to_load:
                logger.debug(
                    f"Post-refresh, new_inbox_model.evolution_instance: {new_inbox_model.evolution_instance}"
                )
            if "whatsapp_cloud_config" in relationships_to_load:
                logger.debug(
                    f"Post-refresh, new_inbox_model.whatsapp_cloud_config: {new_inbox_model.whatsapp_cloud_config}"
                )
        return new_inbox_model

    except IntegrityError as e:
        # This can happen if the UniqueConstraint on (account_id, channel_id, channel_type) is violated,
        # or if evolution_instance_id / whatsapp_cloud_config_id unique constraints are violated.
        logger.error(f"Integrity error creating inbox '{inbox_data.name}': {e}")
        # The calling endpoint should handle db.rollback()
        raise IntegrityError(
            f"Failed to create inbox due to a conflict: {e.orig}",
            params=e.params,
            orig=e.orig,
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error creating inbox '{inbox_data.name}': {e}")
        # The calling endpoint should handle db.rollback()
        raise


async def find_inbox_by_id_and_account(
    db: AsyncSession, *, inbox_id: UUID, account_id: UUID
) -> Inbox | None:
    """
    Finds a single inbox by its ID and account ID, with related channel configs.

    Args:
        db (AsyncSession): The database session.
        inbox_id (UUID): The ID of the inbox.
        account_id (UUID): The ID of the account.

    Returns:
        Optional[Inbox]: The Inbox object if found, else None.
    """
    logger.debug(
        f"[InboxRepo] Finding inbox by ID={inbox_id} for Account={account_id} with eager loading"
    )  # Log atualizado
    stmt = (
        select(Inbox)
        .where(Inbox.id == inbox_id, Inbox.account_id == account_id)
        .options(
            selectinload(Inbox.evolution_instance),
            selectinload(Inbox.whatsapp_cloud_config),
        )
    )
    result = await db.execute(stmt)
    inbox = result.scalar_one_or_none()

    if inbox:
        logger.debug(f"Inbox found: {inbox.id}, Type: {inbox.channel_type}")
        if inbox.evolution_instance:
            logger.debug(f"Loaded evolution_instance: {inbox.evolution_instance.id}")
        if inbox.whatsapp_cloud_config:
            logger.debug(
                f"Loaded whatsapp_cloud_config: {inbox.whatsapp_cloud_config.id}"
            )
    else:
        logger.warning(
            f"[InboxRepo] Inbox ID={inbox_id} not found or not authorized for Account={account_id}"
        )
    return inbox


async def find_inboxes_with_association_by_account(
    db: AsyncSession, *, account_id: UUID, limit: int = 100, offset: int = 0
) -> List[Tuple[Inbox, Optional[UUID]]]:
    """
    Retrieve all inboxes for an account, including the associated BotAgent ID.

    Args:
        db: The SQLAlchemy async session.
        account_id: The ID of the account whose inboxes to retrieve.
        limit: Maximum number of inboxes to return.
        offset: Number of inboxes to skip.

    Returns:
        A list of tuples, each containing (Inbox object, associated BotAgent UUID or None).
    """
    logger.debug(
        f"[InboxRepo] Finding inboxes with agent association for Account={account_id} (limit={limit}, offset={offset})"
    )
    stmt = (
        select(Inbox, BotAgentInbox.bot_agent_id)
        .outerjoin(
            BotAgentInbox,
            Inbox.id == BotAgentInbox.inbox_id,
        )
        .where(
            Inbox.account_id == account_id,
            # Inbox.is_simulation.is_(False),
        )
        .options(
            selectinload(Inbox.evolution_instance),  # Eager load evolution_instance
            selectinload(
                Inbox.whatsapp_cloud_config
            ),  # Eager load whatsapp_cloud_config
        )
        .order_by(Inbox.name)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    inboxes_with_assoc: List[Tuple[Inbox, Optional[UUID]]] = result.all()
    logger.info(
        f"[InboxRepo] Found {len(inboxes_with_assoc)} inboxes with association info for Account={account_id}"
    )
    return inboxes_with_assoc


async def find_inbox_by_channel_id(
    db: AsyncSession, *, account_id: UUID, channel_id: str
) -> Optional[Inbox]:
    """Retrieve an inbox by channel ID and account ID.

    Args:
        db (AsyncSession): Asynchronous database session.
        account_id (UUID): The account ID.
        channel_id (str): The channel identifier.

    Returns:
        Optional[Inbox]: The Inbox object if found, otherwise None.
    """
    logger.debug(
        f"[InboxRepo] Finding inbox by ChannelID={channel_id} for Account={account_id}"
    )
    result = await db.execute(
        select(Inbox)
        .filter_by(account_id=account_id, channel_id=channel_id)
        .options(
            selectinload(Inbox.evolution_instance),
            selectinload(Inbox.whatsapp_cloud_config),
        )
    )
    inbox = result.scalar_one_or_none()

    if inbox:
        logger.debug(
            f"[InboxRepo] Found inbox (id={inbox.id}) for channel_id {channel_id}"
        )
    else:
        logger.info(
            f"[InboxRepo] No inbox found for channel_id {channel_id} (account_id={account_id})"
        )
    return inbox


async def find_inboxes_by_account(
    db: AsyncSession, *, account_id: UUID, limit: int = 100, offset: int = 0
) -> List[Inbox]:
    """Retrieve all inboxes belonging to a specific account with pagination.

    Args:
        db (AsyncSession): Asynchronous database session.
        account_id (UUID): The ID of the account whose inboxes to retrieve.
        limit (int): Maximum number of inboxes to return.
        offset (int): Number of inboxes to skip.

    Returns:
        List[Inbox]: A list of Inbox objects.
    """
    logger.debug(
        f"[InboxRepo] Finding all inboxes for Account={account_id} (limit={limit}, offset={offset})"
    )
    result = await db.execute(
        select(Inbox)
        .filter(Inbox.account_id == account_id, Inbox.is_simulation.is_(False))
        .order_by(Inbox.name)
        .limit(limit)
        .offset(offset)
    )
    inboxes = result.scalars().all()
    logger.info(f"[InboxRepo] Found {len(inboxes)} inboxes for Account={account_id}")
    return inboxes


async def find_inboxes_by_user_membership(
    db: AsyncSession, *, user_id: UUID, account_id: UUID
) -> List[Inbox]:
    """Fetch all inboxes within a specific account where the user is a member.

    Args:
        db (AsyncSession): Asynchronous database session.
        user_id (UUID): The user ID.
        account_id (UUID): The account ID.

    Returns:
        List[Inbox]: A list of Inbox objects.
    """
    logger.debug(
        f"[InboxRepo] Finding inboxes for User={user_id} in Account={account_id} via membership"
    )
    result = await db.execute(
        select(Inbox)
        .join(InboxMember, Inbox.id == InboxMember.inbox_id)
        .filter(
            InboxMember.user_id == user_id,
            Inbox.account_id == account_id,
            Inbox.is_simulation.is_(False),
        )
        .order_by(Inbox.name)
    )
    inboxes = result.scalars().all()
    logger.info(
        f"[InboxRepo] Found {len(inboxes)} inboxes for User={user_id} via membership in Account={account_id}"
    )
    return inboxes


async def update_inbox(
    db: AsyncSession,
    inbox_to_update: Inbox,
    update_data: InboxUpdate,  # Renomeado 'inbox' para 'inbox_to_update'
) -> Inbox:
    update_values = update_data.model_dump(exclude_unset=True)
    for key, value in update_values.items():
        if isinstance(value, enum.Enum):
            setattr(inbox_to_update, key, value.value)
        else:
            setattr(inbox_to_update, key, value)

    db.add(inbox_to_update)
    await db.flush()
    # Não precisa de db.refresh(inbox_to_update) aqui se vamos re-selecionar

    # Re-selecionar para garantir que os relacionamentos sejam carregados para a resposta
    stmt = (
        select(Inbox)
        .where(
            Inbox.id == inbox_to_update.id
        )  # Usar o ID do objeto que acabamos de dar flush
        .options(
            selectinload(Inbox.evolution_instance),
            selectinload(Inbox.whatsapp_cloud_config),
            # Adicione outros relacionamentos que InboxRead possa precisar, se houver
        )
    )
    result = await db.execute(stmt)
    updated_inbox_with_relations = result.scalar_one_or_none()

    if not updated_inbox_with_relations:
        logger.error(
            f"CRITICAL: Failed to re-fetch inbox {inbox_to_update.id} immediately after update flush."
        )
        raise Exception(
            f"Failed to retrieve updated inbox {inbox_to_update.id} with relations."
        )

    logger.info(
        f"Inbox ID {updated_inbox_with_relations.id} updated and re-fetched with relations. DB commit pending."
    )
    return updated_inbox_with_relations


async def delete_inbox(db: AsyncSession, *, inbox: Inbox) -> bool:
    """Delete an existing inbox without finalizing the transaction.

    The commit should be performed by the upper layer.

    Args:
        db (AsyncSession): Asynchronous database session.
        inbox (Inbox): The existing Inbox object to delete.

    Returns:
        bool: True if deletion was prepared successfully, otherwise raises an exception.
    """
    inbox_id = inbox.id
    logger.warning(f"[InboxRepo] Attempting to delete Inbox ID={inbox_id}")
    try:
        await db.delete(inbox)
        # Removed commit here; finalization should be handled by the caller.
        logger.info(f"[InboxRepo] Inbox ID={inbox_id} marked for deletion")
        return True
    except Exception as e:
        logger.exception(f"[InboxRepo] Failed to delete Inbox ID={inbox_id}")
        raise e


async def update_intial_conversation_status(
    db: AsyncSession,
    *,
    account_id: UUID,
    inbox_id: UUID,
    new_status: ConversationStatusEnum = ConversationStatusEnum.BOT,
) -> None:
    """
    Updates the status of active conversations in a specific inbox that currently
    have a specific status (typically BOT).

    Args:
        db: The SQLAlchemy async session.
        account_id: The account ID to scope the update.
        inbox_id: The inbox ID where conversations should be updated.
        new_status: The new status to set (e.g., PENDING).
    Returns:
        The number of conversation rows updated.
    """
    logger.info(
        f"Updating inbox {inbox_id} (Account: {account_id}) " f"to '{new_status.value}'"
    )
    try:
        stmt = (
            update(Inbox)
            .where(Inbox.account_id == account_id, Inbox.id == inbox_id)
            .values(initial_conversation_status=new_status)
            # synchronize_session=False é geralmente recomendado para updates em massa com asyncio
            .execution_options(synchronize_session=False)
        )
        await db.execute(stmt)
        logger.info(f"Updated status for inbox {inbox_id} in Account {account_id}.")
        return None
    except Exception as e:
        logger.exception(
            f"Error updating Inbox initial conversation statuses  {account_id} "
            f"to {new_status.value}: {e}"
        )
        raise  # Re-lançar para rollback na camada superior
