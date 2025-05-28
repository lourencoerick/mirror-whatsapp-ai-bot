# backend/app/workers/ai_replier.py

import os
import asyncio
from loguru import logger

# --- ARQ Specific Imports ---
from arq.connections import RedisSettings, ArqRedis
from arq import cron

# --- Project Imports ---
# Configuration
from app.config import (
    get_settings,
    Settings,
)  # get_settings for explicit call if needed

settings: Settings = get_settings()
# Database
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from sqlalchemy import text
    from app.database import AsyncSessionLocal  # Your actual factory

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    AsyncSessionLocal = None  # type: ignore
    SQLALCHEMY_AVAILABLE = False
    logger.error(
        "ArqWorkerSettings: SQLAlchemy components (AsyncSessionLocal) unavailable."
    )

# LLM / LangChain
try:
    from langchain_openai import AzureChatOpenAI
    from langchain_core.language_models import BaseChatModel
    from app.core.embedding_utils import (
        get_embedding,
    )  # Assuming this is an async function

    LANGCHAIN_AVAILABLE = True
except ImportError:
    AzureChatOpenAI = None  # type: ignore
    BaseChatModel = None  # type: ignore
    get_embedding = None  # type: ignore
    LANGCHAIN_AVAILABLE = False
    logger.warning(
        "ArqWorkerSettings: LangChain components unavailable. LLM/Embedding features limited."
    )

# ARQ Manager (for shared pool, if you use one)
try:
    from app.core.arq_manager import init_arq_pool, get_arq_pool, close_arq_pool

    ARQ_MANAGER_AVAILABLE = True
except ImportError:
    ARQ_MANAGER_AVAILABLE = False
    logger.warning(
        "ArqWorkerSettings: arq_manager not found. ARQ pool management might be localized."
    )

    # Define dummy functions if arq_manager is not available to prevent NameError
    async def init_arq_pool():
        pass

    async def get_arq_pool():
        return None

    async def close_arq_pool():
        pass


# --- Import Task Functions ---
from app.workers.ai_replier.tasks.message_handler_task import handle_ai_reply_request
from app.workers.ai_replier.tasks.follow_up_task import schedule_conversation_follow_up
from app.workers.ai_replier.tasks.billing_task import (
    report_usage_to_stripe_task,
    REPORT_USAGE_TASK_NAME,
)

# ==============================================================================
# Arq Worker Configuration Callbacks
# ==============================================================================


async def startup(ctx: dict):
    """
    Initializes resources shared by all ARQ worker tasks.

    This function is called once when an ARQ worker process starts.
    It sets up database connections, LLM clients, and the ARQ Redis pool,
    making them available in the `ctx` dictionary for all tasks.

    Args:
        ctx: The ARQ context dictionary to be populated.
    """
    worker_id = os.getpid()
    logger.info(f"Unified ARQ Worker (PID: {worker_id}) starting up...")
    s = (
        get_settings()
    )  # Get a fresh instance of settings if needed, or use global `settings`

    # --- Initialize Database Session Factory ---
    if SQLALCHEMY_AVAILABLE and AsyncSessionLocal and s.DATABASE_URL:
        logger.info("Initializing database session factory...")
        try:
            # AsyncSessionLocal is already a factory (async_sessionmaker instance)
            ctx["db_session_factory"] = AsyncSessionLocal
            # Test connection - optional, but good for early failure detection
            async with AsyncSessionLocal() as session:
                await session.execute(
                    s.DB_HEALTH_CHECK_QUERY
                    if hasattr(s, "DB_HEALTH_CHECK_QUERY")
                    else text("SELECT 1")
                )

            logger.success("Database session factory created and tested.")
        except Exception as db_init_err:
            logger.exception(
                f"Database session factory initialization failed: {db_init_err}"
            )
            ctx["db_session_factory"] = None
    else:
        logger.warning(
            "SQLAlchemy/DB URL unavailable. Database operations will be impaired."
        )
        ctx["db_session_factory"] = None

    # --- Initialize LLM Clients ---
    if LANGCHAIN_AVAILABLE and AzureChatOpenAI:
        logger.info("Initializing LLM clients...")
        try:
            if not all(
                [
                    s.AZURE_OPENAI_API_KEY,
                    s.AZURE_OPENAI_ENDPOINT,
                    s.PRIMARY_LLM_MODEL_NAME,
                    s.FAST_LLM_MODEL_NAME,
                ]
            ):
                raise EnvironmentError(
                    "Missing one or more Azure OpenAI environment variables for LLM setup."
                )

            llm_primary_client = AzureChatOpenAI(
                azure_deployment=s.PRIMARY_LLM_MODEL_NAME,
                temperature=s.PRIMARY_LLM_TEMPERATURE,
                azure_endpoint=s.AZURE_OPENAI_ENDPOINT,
                api_key=s.AZURE_OPENAI_API_KEY,
                api_version="2025-01-01-preview",
            )
            # Test primary LLM client (optional)
            # await llm_primary_client.ainvoke("Hello")
            ctx["llm_primary"] = llm_primary_client
            logger.info(f"Primary LLM client initialized: {s.PRIMARY_LLM_MODEL_NAME}")

            llm_fast_client = AzureChatOpenAI(
                azure_deployment=s.FAST_LLM_MODEL_NAME,
                temperature=s.FAST_LLM_TEMPERATURE,
                azure_endpoint=s.AZURE_OPENAI_ENDPOINT,
                api_key=s.AZURE_OPENAI_API_KEY,
                api_version="2025-01-01-preview",
            )
            # Test fast LLM client (optional)
            # await llm_fast_client.ainvoke("Hello")
            ctx["llm_fast"] = llm_fast_client
            logger.info(f"Fast LLM client initialized: {s.FAST_LLM_MODEL_NAME}")
            logger.success("LLM clients initialized.")

            if get_embedding and s.AZURE_OPENAI_EMBEDDING_MODEL:
                logger.info("Testing embedding utility...")
                # Assuming get_embedding is an async function
                test_embedding = await get_embedding("test")
                if test_embedding is not None:
                    logger.success(
                        f"Embedding utility test successful (vector dim: {len(test_embedding)})."
                    )
                else:
                    logger.warning("Embedding utility test returned empty or None.")
            else:
                logger.warning("Embedding utility or config not available.")

        except EnvironmentError as env_err:
            logger.error(
                f"LLM/Embedding initialization failed due to missing configuration: {env_err}"
            )
            ctx["llm_primary"] = None
            ctx["llm_fast"] = None
        except Exception as llm_init_err:
            logger.exception(f"LLM/Embedding initialization failed: {llm_init_err}")
            ctx["llm_primary"] = None  # Ensure keys exist even if init failed
            ctx["llm_fast"] = None
    else:
        logger.warning(
            "LangChain components unavailable. LLM/Embedding functionality limited."
        )
        ctx["llm_primary"] = None
        ctx["llm_fast"] = None

    # --- Initialize ARQ Redis Pool (for tasks to enqueue other tasks) ---
    # The `ctx['arq_pool']` is typically the pool the worker is *using*.
    # If tasks need to enqueue to *other* queues, they use this pool.
    # `init_arq_pool` from arq_manager might be for creating a *separate client pool*
    # for general application use, which is different.
    # For tasks running within an ARQ worker, ARQ itself provides the pool in `ctx`.
    # However, if your `init_arq_pool` / `get_arq_pool` is designed to be the
    # *single source of truth* for ARQ pools, then using it here is correct.
    logger.info("Acquiring ARQ Redis pool for context...")
    if ARQ_MANAGER_AVAILABLE:
        try:
            await init_arq_pool()  # Ensure the shared pool is initialized
            arq_context_pool = await get_arq_pool()
            if arq_context_pool:
                ctx["arq_pool"] = arq_context_pool
                logger.success(
                    "ARQ Redis pool obtained from arq_manager and set in context."
                )
            else:
                logger.error(
                    "arq_manager.get_arq_pool() returned None. ARQ pool not set in context."
                )
                ctx["arq_pool"] = None
        except Exception as pool_err:
            logger.exception(
                f"Failed to init/get ARQ Redis pool via arq_manager: {pool_err}"
            )
            ctx["arq_pool"] = None
    else:
        # If no arq_manager, ARQ usually provides its own pool in ctx['redis'] or ctx['arq_pool']
        # We can try to ensure ctx['arq_pool'] is set to whatever ARQ provides.
        # This part is a bit tricky as ARQ's internal context setup can vary.
        # Often, `ctx['redis']` is the direct redis-py async connection pool.
        # `ArqRedis` is a wrapper. If `ctx['redis']` is available, tasks can use it.
        # For simplicity, we'll assume ARQ populates `ctx['arq_pool']` or `ctx['redis']`
        # if no explicit manager is used. The tasks themselves will check for `ctx['arq_pool']`.
        if "arq_pool" not in ctx and "redis" in ctx:
            # If arq_pool is not set by ARQ by default but redis (connection pool) is,
            # tasks might need to wrap ctx['redis'] with ArqRedis if they expect that interface.
            # Or, better, tasks should be flexible to use ctx['redis'] directly for enqueuing.
            # For now, we log this. The tasks will need to be robust.
            logger.info(
                "arq_manager not available. Tasks should check ctx['arq_pool'] or ctx['redis']."
            )
        elif "arq_pool" in ctx:
            logger.info(
                "ARQ Redis pool already present in context (likely set by ARQ itself)."
            )
        else:
            logger.warning(
                "ARQ Redis pool not found in context and arq_manager unavailable."
            )
        # Ensure the key exists, even if None
        if "arq_pool" not in ctx:
            ctx["arq_pool"] = None

    logger.info(
        f"Unified ARQ Worker (PID: {worker_id}) startup complete. Context keys: {list(ctx.keys())}"
    )


async def shutdown(ctx: dict):
    """
    Cleans up resources when an ARQ worker process stops.

    Args:
        ctx: The ARQ context dictionary.
    """
    worker_id = os.getpid()
    logger.info(f"Unified ARQ Worker (PID: {worker_id}) shutting down...")

    # --- Close ARQ Redis Pool (if managed by arq_manager and needs explicit close) ---
    if ARQ_MANAGER_AVAILABLE and ctx.get("arq_pool"):
        logger.info("Closing ARQ Redis pool from arq_manager...")
        try:
            await close_arq_pool()  # Close the shared pool
            logger.success("ARQ Redis pool from arq_manager closed.")
        except Exception as e:
            logger.exception(f"Error closing ARQ Redis pool from arq_manager: {e}")

    logger.info(f"Unified ARQ Worker (PID: {worker_id}) shutdown complete.")


# ==============================================================================
# Arq Worker Settings Class
# ==============================================================================


class WorkerSettings:
    """
    Configuration class for the unified ARQ worker.

    This class defines all tasks the worker can handle, common settings,
    and startup/shutdown procedures.
    """

    functions = [
        handle_ai_reply_request,
        schedule_conversation_follow_up,
        report_usage_to_stripe_task,
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

    queue_name = settings.AI_REPLY_QUEUE_NAME  # Default queue if not overridden by CLI
    """Default queue name. Override with --queue-name CLI arg for specific workers."""

    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
        # Add other Redis settings like password if needed
        # password=settings.REDIS_PASSWORD
    )
    """Redis connection settings for ARQ."""

    cron_jobs = [
        cron(
            report_usage_to_stripe_task,
            name=REPORT_USAGE_TASK_NAME,
            hour={
                1,
                6,
                7,
                13,
                19,
                23,
            },
            minute=59,
            run_at_startup=True,
        ),
    ]

    logger.info(
        f"Unified ARQ WorkerSettings configured. "
        f"Listening on Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT} DB {settings.REDIS_DB}. "
        f"Registered tasks: {[f.__name__ for f in functions]}"
    )
