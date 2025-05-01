import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Callable

from uuid import UUID

import arq
from arq.connections import RedisSettings
from loguru import logger  # Mantendo loguru se for o padrão do projeto

# --- Configuration ---
try:
    from app.config import get_settings

    settings = get_settings()
    # Define a default queue name for BATCH tasks
    DEFAULT_BATCH_QUEUE_NAME = getattr(settings, "BATCH_ARQ_QUEUE_NAME", "batch_queue")
    logger.info("Loaded settings via get_settings()")
except ImportError:
    logger.warning("app.config.get_settings not found. Relying solely on os.getenv.")
    settings = type(
        "obj",
        (object,),
        {
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
            "REDIS_PORT": int(os.getenv("REDIS_PORT", "6379")),
            "REDIS_DB": int(os.getenv("REDIS_DB", "0")),
            # Add other relevant settings if needed by batch workers
        },
    )()
    DEFAULT_BATCH_QUEUE_NAME = os.getenv(
        "BATCH_ARQ_QUEUE_NAME", "batch_queue"
    )  # Use ARQ_MAIN_QUEUE_NAME from Terraform


# --- Database Setup ---
try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine,
        async_sessionmaker,
    )

    try:
        from app.database import AsyncSessionLocal

        SHARED_SESSION_LOCAL = True
        logger.info("Using shared AsyncSessionLocal from app.database")
    except ImportError:
        SHARED_SESSION_LOCAL = False
        logger.info("Shared AsyncSessionLocal not found, will create engine locally.")
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.error("SQLAlchemy components not found. DB operations will fail.")
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore
    AsyncSessionLocal = None  # type: ignore


# --- LLM / LangChain Imports (for Researcher, Knowledge Ingester) ---
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.language_models import BaseChatModel

    LANGCHAIN_AVAILABLE = True
    logger.info("Successfully imported LangChain components.")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain components unavailable. Researcher/Ingester limited.")
    BaseChatModel = type("obj", (object,), {})  # type: ignore
    ChatOpenAI = type("obj", (object,), {})  # type: ignore


# --- Search Client Imports (for Researcher) ---
try:
    # Assuming Tavily is used via langchain or a custom client
    from langchain_community.tools.tavily_search import TavilySearchResults

    # Or use your custom client: from app.services.search.client import SearchService
    SEARCH_CLIENT_AVAILABLE = True
    logger.info("Successfully imported Search client components.")
except ImportError:
    SEARCH_CLIENT_AVAILABLE = False
    logger.warning("Search client components unavailable.")
    TavilySearchResults = None  # type: ignore
    # SearchService = None


# --- GCS Client Imports (for Contact Importer, Researcher) ---
try:
    from google.cloud import storage

    GCS_AVAILABLE = True
    logger.info("Successfully imported Google Cloud Storage client.")
except ImportError:
    GCS_AVAILABLE = False
    logger.warning("google-cloud-storage not installed. GCS features unavailable.")
    storage = None  # type: ignore


# --- Knowledge Ingestion Service Imports ---
try:
    from app.services.knowledge.ingestion_service import KnowledgeIngestionService

    INGESTION_SERVICE_AVAILABLE = True
    logger.info("Successfully imported KnowledgeIngestionService.")
except ImportError as e:
    logger.warning(f"Failed to import KnowledgeIngestionService: {e}")
    INGESTION_SERVICE_AVAILABLE = False
    KnowledgeIngestionService = None  # type: ignore


# --- Task Function Imports (Batch Tasks Only) ---
BATCH_FUNCTIONS_IMPORTED: List[Callable[..., Any]] = []

# Contact Importer / Sync
try:
    from app.workers.batch.contacts.tasks.contact_importer import (
        process_contact_csv_task,
    )
    from app.workers.batch.contacts.tasks.evolution_whatsapp_sync import (
        sync_evolution_whatsapp_contacts_task,
    )

    BATCH_FUNCTIONS_IMPORTED.extend(
        [process_contact_csv_task, sync_evolution_whatsapp_contacts_task]
    )
    logger.info("Imported contact batch tasks.")
except ImportError:
    logger.error("Failed to import contact batch tasks.")

# Researcher
try:
    from app.workers.batch.researcher import run_profile_research

    BATCH_FUNCTIONS_IMPORTED.append(run_profile_research)
    logger.info("Imported researcher task.")
except ImportError:
    logger.error("Failed to import researcher task.")

# Knowledge Ingester
try:
    from app.workers.batch.knowledge_ingester import (
        process_knowledge_source,
    )

    BATCH_FUNCTIONS_IMPORTED.append(process_knowledge_source)
    logger.info("Imported knowledge ingester task.")
except ImportError:
    logger.error("Failed to import knowledge ingester task.")

# Check if any functions were loaded
if not BATCH_FUNCTIONS_IMPORTED:
    logger.critical("CRITICAL: No Batch Arq task functions were successfully imported!")
    # Depending on desired behavior, you might raise an error here
    # raise ImportError("No Batch Arq tasks could be loaded.")


# ==============================================================================
# Batch Arq Worker Callbacks
# ==============================================================================


async def on_startup(ctx: Dict[str, Any]) -> None:
    """
    Initialize shared resources needed by the BATCH worker tasks.
    """
    worker_pid = os.getpid()
    logger.info(f"Batch Arq worker (PID: {worker_pid}) starting up...")

    # --- Database ---
    db_url = getattr(settings, "DATABASE_URL", os.getenv("DATABASE_URL"))
    if SQLALCHEMY_AVAILABLE and db_url:
        logger.info("Initializing database connection...")
        try:
            if SHARED_SESSION_LOCAL and AsyncSessionLocal:
                ctx["db_session_factory"] = AsyncSessionLocal
                logger.info("Using shared AsyncSessionLocal factory.")
            elif create_async_engine and async_sessionmaker and AsyncSession:
                engine = create_async_engine(db_url, pool_pre_ping=True)
                session_factory = async_sessionmaker(
                    engine, expire_on_commit=False, class_=AsyncSession
                )
                ctx["db_session_factory"] = session_factory
                # ctx["db_engine"] = engine # Optional: store for shutdown
                logger.info("Created local database session factory.")
            else:
                raise RuntimeError("SQLAlchemy components missing for engine creation.")
        except Exception as db_init_err:
            logger.exception(f"DB init failed: {db_init_err}")
            ctx["db_session_factory"] = None
    else:
        logger.warning("SQLAlchemy or DB URL unavailable. DB operations may fail.")
        ctx["db_session_factory"] = None

    # --- LLM Clients (General LLM & Embeddings for Researcher/Ingester) ---
    if LANGCHAIN_AVAILABLE and ChatOpenAI:
        logger.info("Initializing LLM clients for Batch tasks...")
        try:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise EnvironmentError("OPENAI_API_KEY environment variable not set.")

            # General LLM (used by Researcher, potentially Ingester)
            general_model = os.getenv("ARQ_GENERAL_LLM_MODEL", "gpt-4o-mini")
            llm_general = ChatOpenAI(
                model=general_model, temperature=0.0, api_key=openai_api_key
            )
            ctx["llm"] = llm_general
            logger.info(f"General LLM client initialized: {general_model}")

        except EnvironmentError as env_err:
            logger.error(f"LLM initialization failed: {env_err}")
        except Exception as llm_init_err:
            logger.exception(f"LLM init failed: {llm_init_err}")
        finally:
            if "llm" not in ctx:
                ctx["llm"] = None

    else:
        logger.warning(
            "LangChain unavailable. LLM functionality limited for batch tasks."
        )
        ctx["llm"] = None

    # --- Search Client (for Researcher) ---
    if SEARCH_CLIENT_AVAILABLE and TavilySearchResults:
        logger.info("Initializing Search client (Tavily)...")
        try:
            tavily_api_key = os.getenv("TAVILY_API_KEY")
            if not tavily_api_key:
                raise ValueError("TAVILY_API_KEY environment variable not set.")
            search_client = TavilySearchResults(api_key=tavily_api_key)
            ctx["search_client"] = search_client
            logger.info("Search client (Tavily) initialized.")
        except Exception as search_init_err:
            logger.exception(f"Search client init failed: {search_init_err}")
            ctx["search_client"] = None
    else:
        logger.warning("Search client unavailable.")
        ctx["search_client"] = None

    # --- GCS Client (for Contact Importer, Researcher) ---
    if GCS_AVAILABLE and storage:
        logger.info("Initializing Google Cloud Storage client...")
        try:
            gcs_client = storage.Client()
            ctx["gcs_client"] = gcs_client
            logger.info("Google Cloud Storage client initialized.")
            # Store relevant bucket names
            ctx["contact_import_bucket_name"] = os.getenv(
                "CONTACT_IMPORT_GCS_BUCKET_NAME"
            )
            ctx["knowledge_files_bucket_name"] = os.getenv("KNOWLEDGE_GCS_BUCKET_NAME")
            if not ctx["contact_import_bucket_name"]:
                logger.warning("CONTACT_IMPORT_GCS_BUCKET_NAME not set in environment.")
            if not ctx["knowledge_files_bucket_name"]:
                logger.warning("KNOWLEDGE_GCS_BUCKET_NAME not set in environment.")
        except Exception as gcs_init_err:
            logger.exception(f"GCS client init failed: {gcs_init_err}")
            ctx["gcs_client"] = None
    else:
        logger.warning("GCS client unavailable.")
        ctx["gcs_client"] = None

    # --- Knowledge Ingestion Service ---
    if (
        INGESTION_SERVICE_AVAILABLE
        and KnowledgeIngestionService
        and ctx.get("db_session_factory")
    ):
        logger.info("Initializing KnowledgeIngestionService...")
        try:
            ingestion_service = KnowledgeIngestionService(
                db_session_factory=ctx["db_session_factory"],
            )
            ctx["ingestion_service"] = ingestion_service
            logger.info("KnowledgeIngestionService initialized.")
        except Exception as service_init_err:
            logger.exception(
                f"KnowledgeIngestionService init failed: {service_init_err}"
            )
            ctx["ingestion_service"] = None
    else:
        logger.warning(
            "Cannot initialize KnowledgeIngestionService (missing service, factory, or class)."
        )
        ctx["ingestion_service"] = None

    logger.info(f"Batch Arq worker (PID: {worker_pid}) startup complete.")


async def on_shutdown(ctx: Dict[str, Any]) -> None:
    """
    Clean up resources for the BATCH worker.
    """
    worker_pid = os.getpid()
    logger.info(f"Batch Arq worker (PID: {worker_pid}) shutting down...")
    # Example: Dispose engine if created locally in startup
    # db_engine = ctx.get("db_engine")
    # if db_engine:
    #     logger.info("Disposing database engine...")
    #     await db_engine.dispose()
    #     logger.info("Database engine disposed.")
    logger.info(f"Batch Arq worker (PID: {worker_pid}) shutdown complete.")


# ==============================================================================
# Batch Arq Worker Settings Class
# ==============================================================================


class WorkerSettings:
    """
    Arq worker settings specifically for BATCH tasks
    (Contact Import, Researcher, Knowledge Ingestion, Sync).
    """

    # --- Core Arq Settings ---
    functions: List[Callable[..., Any]] = BATCH_FUNCTIONS_IMPORTED

    # Redis connection settings
    redis_settings: RedisSettings = RedisSettings(
        host=getattr(settings, "REDIS_HOST", os.getenv("REDIS_HOST", "localhost")),
        port=int(getattr(settings, "REDIS_PORT", os.getenv("REDIS_PORT", "6379"))),
        database=int(getattr(settings, "REDIS_DB", os.getenv("REDIS_DB", "0"))),
        password=os.getenv("REDIS_PASSWORD"),
    )

    # Queue Name for BATCH tasks (MUST match Terraform var.batch_arq_queue_name)
    queue_name: str = os.getenv("BATCH_ARQ_QUEUE_NAME", DEFAULT_BATCH_QUEUE_NAME)

    # --- Lifecycle Hooks ---
    on_startup: Optional[Callable[..., Any]] = on_startup
    on_shutdown: Optional[Callable[..., Any]] = on_shutdown

    # --- Job Control (tuned for Batch tasks) ---
    max_jobs: int = int(
        os.getenv("ARQ_MAX_JOBS", 5)
    )  # Lower concurrency might be better for heavy tasks

    # Long timeout for potentially slow tasks like researcher/ingestion
    job_timeout: int = int(
        os.getenv("ARQ_JOB_TIMEOUT", 3540)
    )  # ~59 mins, slightly less than 1h Cloud Run timeout

    max_tries: int = int(
        os.getenv("ARQ_MAX_TRIES", 2)
    )  # Allow one retry for transient issues

    shutdown_delay: float = float(
        os.getenv("ARQ_SHUTDOWN_DELAY", 15.0)
    )  # More time for graceful shutdown

    keep_result_seconds: int = int(
        os.getenv("ARQ_KEEP_RESULT_SECONDS", 3600 * 24 * 2)
    )  # Keep results for 2 days

    health_check_interval: int = int(
        os.getenv("ARQ_HEALTH_CHECK_INTERVAL", 120)
    )  # Less frequent health check

    logger.info(f"Batch Arq Worker configured for queue '{queue_name}'")
    logger.info(
        f"Redis: {redis_settings.host}:{redis_settings.port} DB {redis_settings.database}"
    )
    logger.info(
        f"Job Timeout: {job_timeout}s, Max Jobs: {max_jobs}, Max Tries: {max_tries}"
    )
    logger.info(f"Functions loaded: {[f.__name__ for f in functions]}")
