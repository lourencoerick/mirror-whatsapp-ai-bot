# src/api/v1/routers/simunlation.py
from loguru import logger
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from sqlalchemy import delete, text

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.models.account import Account
from app.models.message import Message

from app.models.user import User
from app.services.repository import conversation as conversation_repo


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


from app.config import get_settings

settings = get_settings()
MESSAGE_QUEUE_NAME = settings.MESSAGE_QUEUE_NAME


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
            f"User {user_id} attempted to enqueue simulation message to non-simulation conversation {conversation_id}."
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
    checkpoint_tables = ["checkpoint_writes", "checkpoint_blobs", "checkpoints"]
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
        for table in checkpoint_tables:
            # Usar parâmetros vinculados (:thread_id) é crucial para segurança!
            logger.debug(f"{log_prefix} Deleting from {table}...")
            # Usamos checkpoint_ns = '' como padrão, ajuste se você usar namespaces AND checkpoint_ns = :checkpoint_ns , "checkpoint_ns": ""
            stmt = text(f"DELETE FROM {table} WHERE thread_id = :thread_id ")
            await db.execute(stmt, {"thread_id": thread_id_str})
            logger.debug(f"{log_prefix} Deleted rows from {table} (if any existed).")

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
