# app/workers/message_processor_worker.py

import os
import asyncio
from loguru import logger
import redis.asyncio as aioredis
from typing import Optional

# --- ARQ Specific Imports ---
from arq.connections import RedisSettings

# --- Project Imports ---
# Configuration
from app.config import get_settings, Settings

settings: Settings = get_settings()

# Database
try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
    )  # Para type hints, se necessário nas tarefas
    from sqlalchemy import text
    from app.database import AsyncSessionLocal  # Sua factory de sessão SQLAlchemy

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    AsyncSessionLocal = None  # type: ignore
    SQLALCHEMY_AVAILABLE = False
    logger.error(
        "MessageProcessorWorker: SQLAlchemy components (AsyncSessionLocal) unavailable."
    )

# ARQ Manager (para obter a pool ARQ se as tarefas precisarem enfileirar outras tarefas)
# Esta pool é usada pelas tarefas para *enfileirar novas tarefas*, não a pool que o worker usa para *consumir*.
try:
    from app.core.arq_manager import init_arq_pool, get_arq_pool, close_arq_pool

    ARQ_MANAGER_AVAILABLE = True
except ImportError:
    ARQ_MANAGER_AVAILABLE = False
    logger.warning(
        "MessageProcessorWorker: arq_manager not found. Enfileiramento de tarefas aninhadas pode ser limitado."
    )

    # Define dummy functions if arq_manager is not available
    async def init_arq_pool():
        pass

    async def get_arq_pool():
        return None

    async def close_arq_pool():
        pass


# --- Import Task Functions ---
# Esta será a nossa nova tarefa principal para este worker
from app.workers.consumer.tasks.process_incoming_message import (
    process_incoming_message_task,
)

from app.services.debounce.message_debounce import MessageDebounceService

# Se houver outras tarefas relacionadas ao processamento de mensagens (ex: status), importe-as aqui.


# ==============================================================================
# Arq Worker Configuration Callbacks
# ==============================================================================


async def startup(ctx: dict):
    """
    Initializes resources shared by ARQ worker tasks for message processing.
    Called once when an ARQ worker process starts.
    Sets up database session factory and ARQ pool for enqueuing further tasks.
    """
    worker_id = os.getpid()
    logger.info(f"Message Processor ARQ Worker (PID: {worker_id}) starting up...")
    s = get_settings()  # Usar a instância global 'settings' ou obter uma nova

    # --- Initialize Database Session Factory ---
    if SQLALCHEMY_AVAILABLE and AsyncSessionLocal and s.DATABASE_URL:
        logger.info(
            "Message Processor Worker: Initializing database session factory..."
        )
        try:
            ctx["db_session_factory"] = AsyncSessionLocal
            async with AsyncSessionLocal() as session:  # Test connection
                await session.execute(
                    s.DB_HEALTH_CHECK_QUERY
                    if hasattr(s, "DB_HEALTH_CHECK_QUERY")
                    else text("SELECT 1")
                )
            logger.success(
                "Message Processor Worker: Database session factory created and tested."
            )
        except Exception as db_init_err:
            logger.exception(
                f"Message Processor Worker: Database session factory initialization failed: {db_init_err}"
            )
            ctx["db_session_factory"] = None
    else:
        logger.warning(
            "Message Processor Worker: SQLAlchemy/DB URL unavailable. Database operations will be impaired."
        )
        ctx["db_session_factory"] = None

    # --- Initialize MessageDebounceService ---
    logger.info(
        "Message Processor Worker: Initializing MessageDebounceService instance..."
    )
    # ARQ injeta sua própria conexão/pool Redis no contexto, geralmente como 'redis'
    redis_client_from_arq: Optional[aioredis.Redis] = ctx.get("redis")

    if redis_client_from_arq:
        try:
            ctx["message_debounce_service_instance"] = MessageDebounceService(
                redis_client=redis_client_from_arq
            )
            logger.success(
                "Message Processor Worker: MessageDebounceService instance created and stored in context."
            )
        except Exception as e_debounce_init:
            logger.exception(
                f"Message Processor Worker: Failed to initialize MessageDebounceService: {e_debounce_init}"
            )
            ctx["message_debounce_service_instance"] = None
    else:
        logger.error(
            "Message Processor Worker: Redis client ('redis') not found in ARQ context. Debounce service will NOT be available."
        )
        ctx["message_debounce_service_instance"] = None

    # --- Initialize ARQ Redis Pool (para tarefas que precisam enfileirar outras tarefas, ex: IA) ---
    logger.info(
        "Message Processor Worker: Acquiring ARQ Redis pool for context (for enqueuing AI tasks)..."
    )
    if ARQ_MANAGER_AVAILABLE:
        try:
            # Se init_arq_pool for idempotente ou gerenciar um singleton, chamá-lo aqui é seguro.
            # Caso contrário, certifique-se de que ele seja chamado apenas uma vez globalmente se necessário.
            await init_arq_pool()
            arq_context_pool = await get_arq_pool()
            if arq_context_pool:
                ctx["arq_pool_for_ai_tasks"] = (
                    arq_context_pool  # Nome específico para clareza
                )
                logger.success(
                    "Message Processor Worker: ARQ Redis pool for AI tasks obtained from arq_manager and set in context."
                )
            else:
                logger.error(
                    "Message Processor Worker: arq_manager.get_arq_pool() returned None. ARQ pool for AI tasks not set."
                )
                ctx["arq_pool_for_ai_tasks"] = None
        except Exception as pool_err:
            logger.exception(
                f"Message Processor Worker: Failed to init/get ARQ Redis pool for AI tasks via arq_manager: {pool_err}"
            )
            ctx["arq_pool_for_ai_tasks"] = None
    else:
        # Se não houver arq_manager, e as tarefas precisarem enfileirar, elas podem não ter uma pool ArqRedis pronta.
        # ARQ fornece ctx['redis'] que é o pool de conexão redis-py.
        # A tarefa de IA precisaria de uma instância ArqRedis.
        logger.warning(
            "Message Processor Worker: arq_manager not available. Enqueuing AI tasks from message processor might require direct Redis pool usage or separate ArqRedis client creation within tasks."
        )
        ctx["arq_pool_for_ai_tasks"] = None  # Garantir que a chave exista

    logger.info(
        f"Message Processor ARQ Worker (PID: {worker_id}) startup complete. Context keys: {list(ctx.keys())}"
    )


async def shutdown(ctx: dict):
    """
    Cleans up resources when the Message Processor ARQ worker process stops.
    """
    worker_id = os.getpid()
    logger.info(f"Message Processor ARQ Worker (PID: {worker_id}) shutting down...")

    # Se a pool ARQ para enfileirar tarefas de IA foi gerenciada pelo arq_manager e precisa de fechamento explícito
    if ARQ_MANAGER_AVAILABLE and ctx.get("arq_pool_for_ai_tasks"):
        logger.info(
            "Message Processor Worker: Closing ARQ Redis pool for AI tasks from arq_manager..."
        )
        try:
            # A função close_arq_pool deve ser idempotente ou verificar se a pool ainda é válida
            await close_arq_pool()
            logger.success(
                "Message Processor Worker: ARQ Redis pool for AI tasks from arq_manager closed."
            )
        except Exception as e:
            logger.exception(
                f"Message Processor Worker: Error closing ARQ Redis pool for AI tasks: {e}"
            )

    logger.info(f"Message Processor ARQ Worker (PID: {worker_id}) shutdown complete.")


# ==============================================================================
# Arq Worker Settings Class
# ==============================================================================


class WorkerSettings:
    """
    Configuration class for the Message Processor ARQ worker.
    """

    functions = [
        process_incoming_message_task,
        # Adicione outras tarefas de processamento de mensagens aqui se houver
    ]
    """List of all task functions this worker can execute."""

    on_startup = startup
    """Coroutine called when a worker process starts."""

    on_shutdown = shutdown
    """Coroutine called when a worker process stops."""

    job_timeout = 300  # seconds, default timeout for jobs
    """Maximum execution time for a job before it's considered timed out."""

    keep_alive = 60  # seconds
    """Time a worker process will stay alive after processing its last job before exiting."""

    queue_name = settings.MESSAGE_QUEUE_NAME

    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,  # Usar um DB Redis diferente para ARQ se possível/desejado
        # password=settings.REDIS_PASSWORD # Se tiver senha
    )
    """Redis connection settings for ARQ."""

    logger.info(
        f"Message Processor ARQ WorkerSettings configured. "
        f"Listening on Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT} DB {settings.REDIS_DB}. "
        f"Queue: '{queue_name}'. "
        f"Registered tasks: {[f.__name__ for f in functions]}"
    )
