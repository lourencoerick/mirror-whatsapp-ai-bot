from uuid import UUID
from typing import Dict, Any  # Any para o payload_from_debounce
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.arq_manager import get_arq_pool  # Para enfileirar tarefas ARQ
from app.config import get_settings  # Para nomes de fila e outras configs
from app.database import (
    AsyncSessionLocal,
)  # Para criar uma sessão de DB para ler o status
from app.services.repository import (
    conversation as conversation_repo,
)  # Para buscar a conversa
from app.models.conversation import ConversationStatusEnum  # Para comparar o status
from app.models.message import Message as MessageModel

settings = get_settings()


async def enqueue_ai_processing_task(payload_from_debounce: Dict[str, Any]):
    """
    Checks conversation status and, if eligible (e.g., status is BOT),
    enqueues the 'handle_ai_reply_request' task to ARQ for AI processing.

    This function is intended to be called by the MessageDebounceService
    after a debounce period.

    Args:
        payload_from_debounce: A dictionary expected to contain:
            - account_id (uuid.UUID): The account ID.
            - conversation_id (uuid.UUID): The conversation ID.
            - merged_content (str): The merged text content from user messages.
    """
    account_id: UUID = payload_from_debounce["account_id"]
    conversation_id: UUID = payload_from_debounce["conversation_id"]
    merged_content: str = payload_from_debounce["merged_content"]

    logger.info(
        f"[EnqueueAIProcessing] Received request for ConvID: {conversation_id}, AccID: {account_id}. "
        f"Merged content preview: '{merged_content[:100]}...'"
    )

    # 1. Verificar o status da conversa antes de enfileirar para IA
    try:
        async with AsyncSessionLocal() as db:  # Cria uma nova sessão de DB
            conversation = await conversation_repo.find_conversation_by_id(
                db, account_id=account_id, conversation_id=conversation_id
            )
            if not conversation:
                logger.warning(
                    f"[EnqueueAIProcessing] Conversation {conversation_id} not found for account {account_id}. "
                    "Skipping AI task enqueue."
                )
                return  # Não pode prosseguir sem a conversa

            if conversation.status != ConversationStatusEnum.BOT:
                logger.info(
                    f"[EnqueueAIProcessing] Conversation {conversation_id} status is '{conversation.status.value}'. "
                    "AI reply is not applicable. Skipping AI task enqueue."
                )
                return  # Não enfileira se o status não for BOT

            logger.info(
                f"[EnqueueAIProcessing] Conversation {conversation_id} status is BOT. "
                "Proceeding to enqueue task for AI replier."
            )

    except Exception as e:
        logger.exception(
            f"[EnqueueAIProcessing] Error during DB check for conversation status (ConvID: {conversation_id}): {e}. "
            "Skipping AI task enqueue."
        )
        return  # Não enfileira em caso de erro no DB

    # 2. Se o status for BOT, enfileirar a tarefa para o AI Replier (handle_ai_reply_request)
    arq_pool = get_arq_pool()  # Obtém a instância ArqRedis
    if not arq_pool:
        logger.error(
            "[EnqueueAIProcessing] ARQ pool not available via get_arq_pool(). "
            "Cannot enqueue AI processing task for ConvID: {conversation_id}."
        )
        # Isso seria um erro de configuração/inicialização do app
        return

    # Payload para a tarefa ARQ 'handle_ai_reply_request'
    arq_task_payload = {
        "account_id": account_id,
        "conversation_id": conversation_id,
        "user_input_content": merged_content,  # O conteúdo mesclado
        "event_type": "user_message",  # Indica que é uma mensagem de usuário
        "trigger_message_id": None,  # Explicitamente None, pois não há um ID de DB único para o conteúdo mesclado
        # ou pode ser omitido se a tarefa ARQ tratar None como default.
        # "follow_up_attempt_count" não é relevante aqui
    }

    try:
        job = await arq_pool.enqueue_job(
            "handle_ai_reply_request",  # Nome da função da tarefa ARQ
            _queue_name=settings.AI_REPLY_QUEUE_NAME,  # Nome da fila de destino
            **arq_task_payload,  # Argumentos para a tarefa
        )
        if job:
            logger.info(
                f"[EnqueueAIProcessing] Successfully enqueued 'handle_ai_reply_request' for ConvID {conversation_id} "
                f"to queue '{settings.AI_REPLY_QUEUE_NAME}'. ARQ Job ID: {job.job_id}"
            )
        else:
            logger.error(
                f"[EnqueueAIProcessing] Failed to enqueue 'handle_ai_reply_request' for ConvID {conversation_id}. "
                "arq_pool.enqueue_job returned None."
            )
    except Exception as e:
        logger.exception(
            f"[EnqueueAIProcessing] Failed to enqueue 'handle_ai_reply_request' for ConvID {conversation_id}: {e}"
        )


async def enqueue_ai_processing_for_trigger(
    db: AsyncSession,
    trigger_message: MessageModel,
):
    """
    Checks conversation status and enqueues the 'handle_ai_reply_request' task
    for a conversation initiated by an integration trigger, bypassing debounce.

    Args:
        db: The active database session from the processing logic.
        trigger_message: The synthetic Message object created by the integration flow.
    """
    conversation_id = trigger_message.conversation_id
    account_id = trigger_message.account_id

    log_prefix = f"[EnqueueAIForTrigger] ConvID: {conversation_id}:"
    logger.info(
        f"{log_prefix} Received request for trigger message ID {trigger_message.id}."
    )

    # 1. Verificar o status da conversa (reutilizando a mesma lógica de negócio)
    conversation = await conversation_repo.find_conversation_by_id(
        db, account_id=account_id, conversation_id=conversation_id
    )
    if not conversation:
        logger.warning(
            f"{log_prefix} Conversation not found. Skipping AI task enqueue."
        )
        return

    if conversation.status != ConversationStatusEnum.BOT:
        logger.info(
            f"{log_prefix} Conversation status is '{conversation.status.value}'. "
            "AI reply is not applicable. Skipping AI task enqueue."
        )
        return

    logger.info(f"{log_prefix} Conversation status is BOT. Proceeding to enqueue task.")

    # 2. Se o status for BOT, enfileirar a tarefa para o AI Replier
    arq_pool = get_arq_pool()
    if not arq_pool:
        logger.error(f"{log_prefix} ARQ pool not available. Cannot enqueue AI task.")
        return

    # Payload para a tarefa ARQ 'handle_ai_reply_request'
    arq_task_payload = {
        "account_id": account_id,
        "conversation_id": conversation_id,
        "user_input_content": trigger_message.content,  # O conteúdo da nossa mensagem sintética
        "event_type": "integration_trigger",  # Novo tipo de evento para clareza
        "trigger_message_id": trigger_message.id,  # Passamos o ID da mensagem sintética
    }

    try:
        job = await arq_pool.enqueue_job(
            "handle_ai_reply_request",
            _queue_name=settings.AI_REPLY_QUEUE_NAME,
            **arq_task_payload,
        )
        if job:
            logger.info(
                f"{log_prefix} Successfully enqueued 'handle_ai_reply_request'. ARQ Job ID: {job.job_id}"
            )
        else:
            logger.error(
                f"{log_prefix} Failed to enqueue job. arq_pool.enqueue_job returned None."
            )
    except Exception as e:
        logger.exception(
            f"{log_prefix} Failed to enqueue 'handle_ai_reply_request': {e}"
        )
