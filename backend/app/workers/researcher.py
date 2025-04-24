# backend/app/workers/researcher.py

from uuid import UUID
from loguru import logger
from typing import Optional
from arq.connections import RedisSettings
from loguru import logger

from app.config import get_settings, Settings


# --- Arq and Asyncio ---
# Ensure arq is installed: pip install arq
# from arq import Retry # Import if using Arq's retry mechanism

# --- Project Imports ---
# Orchestrator
try:
    from app.services.researcher.orchestrator import research_and_create_profile

    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    logger.error("Orchestrator function 'research_and_create_profile' not found.")
    ORCHESTRATOR_AVAILABLE = False

# LLM Client Base (for type hint) & Concrete Client (for startup)
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_openai import ChatOpenAI  # Example, adjust as needed

    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.error("LangChain core components not found.")
    LANGCHAIN_AVAILABLE = False

    class BaseChatModel:
        pass

    class ChatOpenAI(BaseChatModel):
        pass  # Dummy


# Database Session (for type hint and startup)
try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine,
        async_sessionmaker,
    )
    from app.config import get_settings  # Assuming settings has DATABASE_URL

    settings = get_settings()
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    logger.error("SQLAlchemy components not found.")
    SQLALCHEMY_AVAILABLE = False
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore
    settings = type("obj", (object,), {"DATABASE_URL": None})()  # Dummy settings


# --- Arq Task Definition ---


async def run_profile_research(ctx: dict, url: str, account_id: UUID):
    """
    Arq task to perform website research, extract profile, and save to DB.

    Args:
        ctx: The Arq context dictionary, containing 'db_session_factory' and 'llm'.
        url: The URL of the website to research.
        account_id: The UUID of the account associated with the profile.
    """
    task_id = ctx.get("job_id", "unknown_job")  # Get Arq job ID if available
    logger.info(
        f"[ResearcherTask:{task_id}] Starting for URL: {url}, Account: {account_id}"
    )

    # --- Get Dependencies from Context ---
    session_factory = ctx.get("db_session_factory")
    llm_client: Optional[BaseChatModel] = ctx.get("llm")

    if not session_factory or not llm_client:
        logger.error(
            f"[ResearcherTask:{task_id}] Missing dependencies in Arq context (db_session_factory or llm). Aborting."
        )
        # Optionally raise Retry or another exception if needed
        return  # Or raise an exception

    if not ORCHESTRATOR_AVAILABLE:
        logger.error(
            f"[ResearcherTask:{task_id}] Orchestrator function not available. Aborting."
        )
        return  # Or raise

    # --- Execute Orchestrator within a DB Session ---
    try:
        # Create a new session for this task
        async with session_factory() as db:
            try:
                logger.debug(f"[ResearcherTask:{task_id}] Calling orchestrator...")
                saved_profile = await research_and_create_profile(
                    url=url,
                    account_id=account_id,
                    llm=llm_client,
                    db=db,
                )

                if saved_profile:
                    profile_id = getattr(saved_profile, "id", "N/A")
                    logger.success(
                        f"[ResearcherTask:{task_id}] Research and save completed successfully. Profile ID: {profile_id}"
                    )
                    # Commit the transaction if orchestrator succeeded
                    await db.commit()
                    logger.debug(
                        f"[ResearcherTask:{task_id}] Database transaction committed."
                    )
                else:
                    logger.warning(
                        f"[ResearcherTask:{task_id}] Orchestrator finished but returned no profile. Rolling back."
                    )
                    # Rollback if orchestrator failed gracefully without raising DB error
                    await db.rollback()

            except Exception as orchestrator_exc:
                # Catch errors specifically from the orchestrator or commit
                logger.exception(
                    f"[ResearcherTask:{task_id}] Error during orchestration or commit: {orchestrator_exc}. Rolling back."
                )
                await db.rollback()
                # Optionally re-raise or raise Retry for Arq's retry mechanism
                # raise Retry(defer=10) from orchestrator_exc
                raise  # Re-raise to let Arq handle the failure

    except Exception as e:
        # Catch errors related to session creation or general task execution
        logger.exception(
            f"[ResearcherTask:{task_id}] Unexpected error processing task: {e}"
        )
        # Depending on Arq setup, this might trigger retries
        raise  # Re-raise to let Arq handle the failure


# --- Arq Worker Configuration (WorkerSettings) ---
# This part defines how the Arq worker starts up, connects to Redis,
# finds tasks, and manages context like DB sessions and LLM clients.


async def startup(ctx: dict):
    """
    Initialize resources needed by the worker tasks on startup.
    Creates DB session factory and LLM client, stores them in context.
    """
    logger.info("Researcher worker starting up...")
    # Initialize Database Session Factory
    if SQLALCHEMY_AVAILABLE and settings.DATABASE_URL:
        logger.info("Initializing database connection...")
        try:
            engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
            # expire_on_commit=False is recommended for background tasks
            session_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            ctx["db_session_factory"] = session_factory
            # Optional: Test connection
            # async with session_factory() as session:
            #     await session.execute(text("SELECT 1"))
            logger.info("Database session factory created successfully.")
        except Exception as db_init_err:
            logger.exception(f"Failed to initialize database connection: {db_init_err}")
            ctx["db_session_factory"] = None  # Ensure it's None if failed
    else:
        logger.warning(
            "SQLAlchemy or DATABASE_URL not available/configured. DB operations will fail."
        )
        ctx["db_session_factory"] = None

    # Initialize LLM Client
    if LANGCHAIN_AVAILABLE:
        logger.info("Initializing LLM client...")
        try:
            # Configure your LLM client here (e.g., ChatOpenAI)
            # Ensure API keys are available (e.g., via environment variables)
            # You might load model name, temperature etc., from settings
            llm = ChatOpenAI(model="gpt-4o", temperature=0.0)  # Example
            ctx["llm"] = llm
            # Optional: Add a test call if feasible/needed
            # await llm.ainvoke("test")
            logger.info(
                f"LLM client ({llm.__class__.__name__}) initialized successfully."
            )
        except Exception as llm_init_err:
            logger.exception(f"Failed to initialize LLM client: {llm_init_err}")
            ctx["llm"] = None
    else:
        logger.warning("LangChain not available. LLM operations will fail.")
        ctx["llm"] = None

    logger.info("Researcher worker startup complete.")


async def shutdown(ctx: dict):
    """
    Clean up resources on worker shutdown.
    """
    logger.info("Researcher worker shutting down...")
    # Clean up DB engine if needed (though often managed globally)
    # engine = ctx.get('db_engine') # If engine was stored directly
    # if engine:
    #     await engine.dispose()
    #     logger.info("Database engine disposed.")
    # Clean up LLM client if needed (e.g., close sessions)
    # llm = ctx.get('llm')
    # if hasattr(llm, 'close'): await llm.close()
    logger.info("Researcher worker shutdown complete.")


# Define the WorkerSettings class for Arq
# This tells Arq how to run the worker
class WorkerSettings:
    """
    Arq worker settings for the researcher tasks.
    """

    # List of functions Arq should expose as tasks
    functions = [run_profile_research]
    # Queue name this worker will listen to
    queue_name = "researcher_queue"  # Choose a descriptive name
    # Redis settings (load from environment or config)
    # redis_settings = RedisSettings(...) # Use arq.connections.RedisSettings
    settings: Settings = get_settings()

    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown
    # Other settings like max_jobs, job_timeout, keep_result_forever, etc.
    job_timeout = 300  # Example: 5 minutes timeout per job
    # max_tries = 3 # Example: Allow retries


# Note: To run this worker, you would typically use the Arq CLI:
# arq app.workers.researcher.WorkerSettings
# Ensure Redis is running and accessible.
