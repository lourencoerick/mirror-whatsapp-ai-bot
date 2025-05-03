# src/api/v1/routers/simunlation.py
from loguru import logger
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from sqlalchemy import delete, text

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.models.account import Account
from app.models.message import Message

from app.models.user import User
from app.services.repository import conversation as conversation_repo
from app.services.helper.checkpoint import reset_checkpoint

from app.services.queue.iqueue import IQueue
from app.services.queue.redis_queue import RedisQueue

from app.api.schemas.simulation import (
    SimulationDetailsResponse,
    SimulationMessageCreate,
    SimulationMessageEnqueueResponse,
)

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    CHECKPOINTER_AVAILABLE = True
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    logger.error("AsyncPostgresSaver not available for checkpoint deletion.")

    # Dummy class para evitar erros de importação, mas a funcionalidade falhará
    class AsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, *args, **kwargs):
            class DummyCheckpointer:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    pass

                async def delete(self, config):
                    logger.error("Dummy checkpointer cannot delete.")
                    raise NotImplementedError

            return DummyCheckpointer()


from app.simulation.schemas.persona import PersonaBase, PersonaRead, PersonaCreate

from app.models.simulation.persona import Persona
from app.models.contact import Contact
from app.simulation.repositories import persona as persona_repo  # Import repo namespace


from app.config import get_settings

settings = get_settings()
MESSAGE_QUEUE_NAME = settings.MESSAGE_QUEUE_NAME


async def _enqueue_simulation_message(
    account_id: UUID,
    conversation_id: UUID,
    message_payload: SimulationMessageCreate,
    db: AsyncSession,
) -> SimulationMessageEnqueueResponse:

    # --- Fetch Conversation (ensure related data is loaded if needed by validation/payload) ---
    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )

    # --- Validation ---
    if not conversation:
        logger.warning(
            f"Simulation message enqueue failed: Conversation {conversation_id} not found for account {account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa de simulação não encontrada.",
        )

    if not conversation.is_simulation:
        logger.warning(
            f"Account {account_id} attempted to enqueue simulation message to non-simulation conversation {conversation_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta operação só é permitida em conversas de simulação.",
        )

    # Ensure related objects needed for the payload are loaded
    if not conversation.contact_inbox or not conversation.contact_inbox.contact_id:
        logger.error(
            f"Failed to load contact details (contact_inbox or contact_id) for simulation conversation {conversation_id}."
        )
        # Refresh might help if lazy loading failed, but indicates an issue
        await db.refresh(conversation, attribute_names=["contact_inbox"])
        if not conversation.contact_inbox or not conversation.contact_inbox.contact_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao carregar detalhes do contato/inbox da simulação.",
            )

    # --- Prepare Message Data for Queue  ---
    source_id = f"sim_ui_{uuid4()}"
    message_create_data = {
        "account_id": conversation.account_id,
        "inbox_id": conversation.inbox_id,
        "conversation_id": conversation.id,
        "contact_id": conversation.contact_inbox.contact_id,
        "source_id": source_id,
        "direction": "in",
        "status": "pending",
        "message_timestamp": datetime.now(timezone.utc).isoformat(),
        "content": message_payload.content,
        "content_type": "text",
        "is_simulation": True,
        "content_attributes": {
            "source": "frontend_simulation",
            "channel_type": (
                conversation.inbox.channel_type if conversation.inbox else "simulation"
            ),
        },
    }

    # --- Enqueue the Data ---
    try:
        queue: IQueue = RedisQueue(queue_name=MESSAGE_QUEUE_NAME)
        await queue.enqueue(message_create_data)
        logger.info(
            f"Enqueued simulation message data with source_id {source_id} for conversation {conversation_id}."
        )

        # --- Return Confirmation ---
        # Return the confirmation dictionary matching the response_model
        return SimulationMessageEnqueueResponse(
            status="message enqueued",
            source_id=source_id,
            conversation_id=str(conversation_id),
        )

    except Exception as e:
        logger.exception(
            f"Error enqueuing simulation message for conversation {conversation_id}: {e}"
        )
        # No rollback needed as no DB changes were made here
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao enfileirar a mensagem de simulação para processamento.",
        ) from e


router = APIRouter()


@router.get(
    "/simulation/details",
    response_model=SimulationDetailsResponse,
    summary="Get Primary Simulation Environment Details",
    description="Retrieves the IDs for the user's primary simulation inbox, contact, and conversation, stored on their account.",
)
async def get_simulation_details(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> SimulationDetailsResponse:
    """
    Fetches the primary simulation entity IDs associated with the currently
    authenticated user's account directly from the Account record.
    """

    if not auth_context.account.id:
        logger.error(f"User {auth_context.user.id} has no associated account_id.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não associado a uma conta.",
        )

    account: Account = auth_context.account
    user: User = auth_context.user

    if not account:
        logger.error(f"Account {account.id} not found for user {user.id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta associada ao usuário não encontrada.",
        )

    if not (
        account.simulation_inbox_id
        and account.simulation_contact_id
        and account.simulation_conversation_id
    ):
        logger.warning(
            f"Primary simulation environment IDs are not fully set up on account {account.id} (User: {user.id})."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ambiente de simulação principal não configurado ou incompleto. Tente novamente mais tarde ou contate o suporte.",
        )

    return SimulationDetailsResponse(
        inbox_id=account.simulation_inbox_id,
        contact_id=account.simulation_contact_id,
        conversation_id=account.simulation_conversation_id,
    )


@router.post(
    "/simulation/conversations/{conversation_id}/messages",
    response_model=SimulationMessageEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a Simulated Incoming Message",
    description="Accepts a message as if sent by the simulated contact, validates it, "
    "and enqueues it for processing by the message consumer (which will save it and trigger AI).",
)
async def enqueue_simulation_message(
    conversation_id: UUID,
    message_payload: SimulationMessageCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> SimulationMessageEnqueueResponse:
    """
    Handles receiving a message from the 'simulated contact' perspective.
    Validates input and enqueues the message data for the consumer.
    Does NOT save the message to the database directly in this endpoint.
    """
    account_id = auth_context.account.id
    user_id = auth_context.user.id
    logger.info(
        f"Received simulation message to enqueue for conversation {conversation_id} from user {user_id}"
    )

    await _enqueue_simulation_message(
        db=db,
        account_id=account_id,
        conversation_id=conversation_id,
        message_payload=message_payload,
    )


@router.delete(
    "/simulation/conversations/{conversation_id}/checkpoint",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset Simulation State (Delete Checkpoint & Messages)",  # Nome mais claro
    description="Deletes the persisted LangGraph state (checkpoint) AND associated messages "
    "for the specified simulation conversation.",
)
async def reset_simulation_state(  # Nome mais claro
    conversation_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes checkpoint data and messages for the given simulation conversation ID.
    Uses direct SQL DELETE commands as checkpointer.adelete might not be available.
    """
    account_id = auth_context.account.id
    user_id = auth_context.user.id
    thread_id_str = str(conversation_id)  # Checkpoint usa string
    log_prefix = (
        f"[ResetSimState|Conv:{conversation_id}|Acc:{account_id}|User:{user_id}]"
    )
    logger.info(f"{log_prefix} Received request to reset simulation state.")

    # --- 1. Verificar se a conversa existe, pertence à conta e é de simulação ---
    conversation = await conversation_repo.find_conversation_by_id(
        db, conversation_id=conversation_id, account_id=account_id
    )
    if not conversation:
        logger.warning(f"{log_prefix} Conversation not found or not authorized.")
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    if not conversation.is_simulation:
        logger.warning(f"{log_prefix} Attempted reset on non-simulation conversation.")
        raise HTTPException(
            status_code=400, detail="Operação permitida apenas em simulações."
        )

    # --- 2. Executar Comandos DELETE SQL ---
    # Nomes das tabelas e colunas baseados no código fonte do AsyncPostgresSaver
    # ATENÇÃO: Se o LangGraph mudar esses nomes, este código quebrará.
    # A tabela checkpoint_migrations geralmente não deve ser limpa por thread.
    try:
        logger.info(f"{log_prefix} Deleting messages...")
        # Usando SQLAlchemy Core API (mais seguro contra SQL Injection que f-string)
        delete_msgs_stmt = delete(Message).where(
            Message.conversation_id == conversation_id
        )
        await db.execute(delete_msgs_stmt)
        logger.info(f"{log_prefix} Messages deleted (if any existed).")

        logger.info(
            f"{log_prefix} Deleting checkpoint data for thread_id: {thread_id_str}..."
        )
        await reset_checkpoint(db=db, thread_id=thread_id_str)

        # --- 3. Commit da Transação ---
        await db.commit()
        logger.success(
            f"{log_prefix} Simulation state (messages and checkpoint) reset successfully."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.exception(f"{log_prefix} Error during simulation state reset: {e}")
        await db.rollback()  # Garante rollback em caso de erro
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao reiniciar o estado da simulação.",
        ) from e


# --- Endpoint to Create a Persona ---
@router.post(
    "/simulation/personas",
    response_model=PersonaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Persona",
    description="Create a new Persona linked to an existing Contact.",
)
async def create_new_persona(
    persona_in: PersonaCreate,
    db: AsyncSession = Depends(get_db),
) -> Persona:
    """
    Creates a new Persona in the database.

    Requires the UUID of an existing Contact to establish the 1:1 link.
    The Contact will be marked as `is_simulation=True` if not already set.
    The `simulation_contact_identifier` is automatically derived from the Contact.

    Args:
        persona_in: Input data adhering to the PersonaCreate schema.
        db: Database session dependency.

    Returns:
        The newly created Persona object (validated by PersonaRead).

    Raises:
        HTTPException(404): If the specified Contact ID does not exist.
        HTTPException(409): If a Persona with the same `persona_id` or linked
                           to the same `contact_id` already exists, or if the
                           contact's identifier is already used by another persona.
        HTTPException(500): For other database errors during creation.
    """
    # The repository function handles checking if contact exists and potential IntegrityErrors
    db_persona = await persona_repo.create_persona(db=db, persona_in=persona_in)

    if db_persona is None:
        # Attempt to determine the cause more specifically if possible, based on logs
        # For now, assume conflict as it covers uniqueness constraints & potentially missing contact implicitly
        # The repo logs the specific reason (contact not found vs unique constraint)
        # Check if contact exists first for a clearer 404
        contact_exists = await db.get(Contact, persona_in.contact_id)
        if not contact_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact with ID '{persona_in.contact_id}' not found.",
            )
        # If contact exists, the error is likely a conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Failed to create persona. Possible reasons: "
                "duplicate persona_id, contact already linked to a persona, "
                "or contact identifier already used by another persona."
            ),
        )

    # Return the ORM model instance, FastAPI handles serialization via response_model
    return db_persona


# --- Endpoint to Read Multiple Personas ---
@router.get(
    "/simulation/personas",
    response_model=List[PersonaRead],
    summary="Read Personas",
    description="Retrieve a list of personas with pagination.",
)
async def read_personas(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> List[Persona]:
    """
    Retrieves a list of Persona records from the database.

    Args:
        skip: Number of records to skip for pagination.
        limit: Maximum number of records to return.
        db: Database session dependency.

    Returns:
        A list of Persona objects.
    """
    personas = await persona_repo.get_all_personas(db=db, skip=skip, limit=limit)
    return personas


# --- Endpoint to Read Persona by Database ID ---
@router.get(
    "/simlation/personas/{persona_db_id}",
    response_model=PersonaRead,
    summary="Read Persona by DB ID",
    description="Get a specific persona by its database UUID.",
)
async def read_persona_by_id(
    persona_db_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Persona:
    """
    Retrieves a single Persona by its primary key (UUID).

    Args:
        persona_db_id: The UUID of the Persona record.
        db: Database session dependency.

    Returns:
        The requested Persona object.

    Raises:
        HTTPException(404): If no Persona with the given ID is found.
    """
    db_persona = await persona_repo.get_persona_by_id(
        db=db, persona_db_id=persona_db_id
    )
    if db_persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona with ID '{persona_db_id}' not found",
        )
    return db_persona


# --- Endpoint to Read Persona by Human-Readable persona_id ---
@router.get(
    "/by_persona_id/{persona_id_str}",
    response_model=PersonaRead,
    summary="Read Persona by Persona ID",
    description="Get a specific persona by its unique string identifier (persona_id).",
)
async def read_persona_by_persona_id_str(
    persona_id_str: str,
    db: AsyncSession = Depends(get_db),
) -> Persona:
    """
    Retrieves a single Persona by its unique human-readable identifier.

    Args:
        persona_id_str: The `persona_id` string (e.g., 'curious_customer').
        db: Database session dependency.

    Returns:
        The requested Persona object.

    Raises:
        HTTPException(404): If no Persona with the given persona_id is found.
    """
    db_persona = await persona_repo.get_persona_by_persona_id(
        db=db, persona_id_str=persona_id_str
    )
    if db_persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona with persona_id '{persona_id_str}' not found",
        )
    return db_persona


# --- Endpoint to Read Persona by Contact ID ---
@router.get(
    "/simulation/personas/by_contact_id/{contact_id}",
    response_model=PersonaRead,
    summary="Read Persona by Contact ID",
    description="Get the persona associated with a specific Contact UUID.",
)
async def read_persona_by_contact_id_uuid(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Persona:
    """
    Retrieves a Persona by the UUID of its linked Contact.

    Args:
        contact_id: The UUID of the Contact record.
        db: Database session dependency.

    Returns:
        The associated Persona object.

    Raises:
        HTTPException(404): If no Persona is linked to the given Contact ID.
    """
    db_persona = await persona_repo.get_persona_by_contact_id(
        db=db, contact_id=contact_id
    )
    if db_persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Persona found linked to Contact ID '{contact_id}'",
        )
    return db_persona


# --- Endpoint to Read Persona by Simulation Contact Identifier ---
@router.get(
    "/simulation/personas/by_identifier/{identifier}",
    response_model=PersonaRead,
    summary="Read Persona by Simulation Identifier",
    description="Get a persona by its simulation contact identifier (e.g., phone number).",
)
async def read_persona_by_identifier_str(
    identifier: str,
    db: AsyncSession = Depends(get_db),
) -> Persona:
    """
    Retrieves a Persona by its simulation contact identifier.

    Args:
        identifier: The simulation contact identifier string.
        db: Database session dependency.

    Returns:
        The associated Persona object.

    Raises:
        HTTPException(404): If no Persona uses the given identifier.
    """
    db_persona = await persona_repo.get_persona_by_contact_identifier(
        db=db, identifier=identifier
    )
    if db_persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Persona found with identifier '{identifier}'",
        )
    return db_persona


# --- Endpoint to Update a Persona ---
# NOTE: Using PUT here. Consider PATCH for partial updates if needed later.
# We use PersonaBase as input to avoid requiring contact_id in the update payload.
# We explicitly prevent changing persona_id and contact_id via this endpoint.
@router.put(
    "/simulation/personas/{persona_db_id}",
    response_model=PersonaRead,
    summary="Update Persona",
    description="Update an existing persona's details. Cannot change persona_id or linked contact.",
)
async def update_existing_persona(
    persona_db_id: UUID,
    persona_update: PersonaBase,  # Use Base schema for update payload
    db: AsyncSession = Depends(get_db),
) -> Persona:
    """
    Updates fields of an existing Persona.

    This endpoint uses PUT semantics but takes the PersonaBase schema.
    It intentionally prevents modification of `persona_id` and the linked `contact_id`.
    Use dedicated functions or direct repository access for such changes if necessary.

    Args:
        persona_db_id: The UUID of the Persona to update.
        persona_update: The updated data adhering to PersonaBase schema.
        db: Database session dependency.

    Returns:
        The updated Persona object.

    Raises:
        HTTPException(404): If the Persona with the given ID is not found.
        HTTPException(400): If the update fails due to invalid data (although most
                           validation happens via Pydantic schema).
        HTTPException(500): For other database errors during update.
    """
    # 1. Get the existing persona
    db_persona = await persona_repo.get_persona_by_id(db, persona_db_id=persona_db_id)
    if not db_persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona with ID '{persona_db_id}' not found",
        )

    # 2. Prepare update data, excluding forbidden fields
    update_data = persona_update.model_dump(
        exclude_unset=False
    )  # Get all fields from input

    # Explicitly remove fields we don't want to update via this generic endpoint
    if (
        "persona_id" in update_data
        and update_data["persona_id"] != db_persona.persona_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Updating 'persona_id' is not allowed via this endpoint.",
        )
    update_data.pop(
        "persona_id", None
    )  # Remove even if not changed, repo handles actual update
    update_data.pop(
        "simulation_contact_identifier", None
    )  # Derived field, cannot be set directly

    # 3. Call the repository update function
    updated_persona = await persona_repo.update_persona(
        db=db, db_persona=db_persona, update_data=update_data
    )

    if updated_persona is None:
        # This might happen if repo update encounters an unexpected issue
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update persona due to a database error.",
        )

    return updated_persona


# --- Endpoint to Delete a Persona ---
@router.delete(
    "/simulation/personas/{persona_db_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Persona",
    description="Delete a persona by its database UUID.",
)
async def delete_existing_persona(
    persona_db_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Deletes a Persona record from the database.

    Args:
        persona_db_id: The UUID of the Persona to delete.
        db: Database session dependency.

    Returns:
        None on successful deletion (Status 204).

    Raises:
        HTTPException(404): If the Persona with the given ID is not found.
        HTTPException(500): For database errors during deletion.
    """
    deleted = await persona_repo.delete_persona(db=db, persona_db_id=persona_db_id)

    if not deleted:
        # Assume not found if repo returns False (it logs specific errors)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona with ID '{persona_db_id}' not found or could not be deleted.",
        )
    # No return value needed for 204 No Content response
    return None
