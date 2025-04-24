# backend/app/workers/researcher.py

import os
import asyncio
from uuid import UUID
from typing import Optional
from arq.connections import RedisSettings
from loguru import logger

# --- Arq Imports ---
# from arq import Retry # Uncomment if using Arq's retry mechanism

# --- Project Imports ---
# Graph related imports
try:
    from app.services.researcher.graph import create_research_graph
    from app.services.researcher.graph_state import ResearchState

    GRAPH_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import research graph components: {e}")
    GRAPH_AVAILABLE = False

# LLM Client
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.language_models import BaseChatModel

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain components not found. LLM functionality limited.")

    class BaseChatModel:
        pass

    class ChatOpenAI(BaseChatModel):
        pass  # Dummy


# Search Client
try:
    from app.services.search.client import SearchService

    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.warning("SearchService not found. Search functionality disabled.")

    class SearchService:  # Dummy
        def __init__(self, api_key):
            pass


# Database Session & Config
try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine,
        async_sessionmaker,
    )

    # Assuming settings are correctly loaded elsewhere or directly via config
    from app.config import get_settings

    settings = get_settings()

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.error("SQLAlchemy components or settings not found.")
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore
    # Minimal dummy settings if import fails
    settings = type("obj", (object,), {"DATABASE_URL": None})()


# ==============================================================================
# Arq Task Definition
# ==============================================================================


async def run_profile_research(ctx: dict, url: str, account_id: UUID):
    """
    Arq task to run the LangGraph-based research agent.

    Retrieves dependencies (DB factory, LLM, Search client) from the worker
    context (`ctx`) and invokes the research graph.
    """
    task_id = ctx.get("job_id", "unknown_job")
    logger.info(
        f"[ResearcherGraphTask:{task_id}] Starting for URL: {url}, Account: {account_id}"
    )

    # --- Get Dependencies from Worker Context ---
    db_session_factory = ctx.get("db_session_factory")
    llm_client: Optional[BaseChatModel] = ctx.get("llm")
    search_client: Optional[SearchService] = ctx.get("search_client")

    # --- Validate Dependencies ---
    if not db_session_factory or not llm_client or not search_client:
        error_msg = (
            f"[ResearcherGraphTask:{task_id}] Missing dependencies in Arq context "
            f"(db_factory={bool(db_session_factory)}, llm={bool(llm_client)}, "
            f"search={bool(search_client)}). Aborting."
        )
        logger.error(error_msg)
        raise ValueError("Worker context missing essential dependencies.")  # Fail fast

    if not GRAPH_AVAILABLE:
        error_msg = f"[ResearcherGraphTask:{task_id}] Research graph definition not available. Aborting."
        logger.error(error_msg)
        raise ValueError("Research graph definition unavailable.")  # Fail fast

    # --- Prepare Graph Input and Config ---
    try:
        compiled_graph = create_research_graph()  # Compile the graph
    except Exception as graph_compile_err:
        logger.exception(
            f"[ResearcherGraphTask:{task_id}] Failed to compile research graph: {graph_compile_err}"
        )
        raise  # Fail fast if graph cannot be compiled

    # Sensible defaults for the initial state
    initial_input = ResearchState(
        account_id=account_id,
        initial_url=url,
        max_iterations=5,  # Example: Set max iterations
        urls_to_scrape=[],
        search_queries=[],
        scraped_data={},
        search_results={},
        combined_context=None,
        profile_draft=None,
        missing_info_summary=None,
        visited_urls=set(),
        iteration_count=0,
        error_message=None,
        next_action=None,
    )

    # Configuration dictionary to pass dependencies into the graph nodes
    graph_config = {
        "configurable": {
            "llm_instance": llm_client,
            "db_session_factory": db_session_factory,
            "search_client": search_client,
            # Add other shared resources here if needed by nodes
        }
    }

    # --- Execute Graph ---
    try:
        logger.debug(f"[ResearcherGraphTask:{task_id}] Invoking research graph...")
        final_state = await compiled_graph.ainvoke(
            initial_input, config={**graph_config, "recursion_limit": 50}
        )

        # Log final outcome
        final_error = final_state.get("error_message")
        final_iterations = final_state.get("iteration_count")
        if final_error:
            logger.error(
                f"[ResearcherGraphTask:{task_id}] Graph finished with error "
                f"after {final_iterations} iterations: {final_error}"
            )
        else:
            logger.success(
                f"[ResearcherGraphTask:{task_id}] Graph finished successfully "
                f"after {final_iterations} iterations."
            )

    except Exception as graph_exc:
        logger.exception(
            f"[ResearcherGraphTask:{task_id}] Unexpected error invoking research graph: {graph_exc}"
        )
        # Re-raise the exception to let Arq handle the job failure (e.g., retries, logging)
        raise


# ==============================================================================
# Arq Worker Configuration Callbacks
# ==============================================================================


async def startup(ctx: dict):
    """Initialize resources: DB factory, LLM client, Search client."""
    logger.info("Researcher worker starting up...")

    # Init DB
    if SQLALCHEMY_AVAILABLE and settings.DATABASE_URL:
        logger.info("Initializing database connection...")
        try:
            engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
            # expire_on_commit=False is recommended for background tasks
            session_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            ctx["db_session_factory"] = session_factory
            logger.info("Database session factory created.")
        except Exception as db_init_err:
            logger.exception(f"DB init failed: {db_init_err}")
            ctx["db_session_factory"] = None
    else:
        logger.warning("SQLAlchemy/DB URL unavailable. DB operations will fail.")
        ctx["db_session_factory"] = None

    # Init LLM
    if LANGCHAIN_AVAILABLE:
        logger.info("Initializing LLM client...")
        try:
            # Ensure OPENAI_API_KEY is set in environment
            # Consider loading model name from settings
            llm = ChatOpenAI(
                model="gpt-4.1-mini", temperature=0.0
            )  # Model for extraction/planning
            ctx["llm"] = llm
            logger.info(f"LLM client ({llm.__class__.__name__}) initialized.")
        except Exception as llm_init_err:
            logger.exception(f"LLM init failed: {llm_init_err}")
            ctx["llm"] = None
    else:
        logger.warning("LangChain unavailable. LLM operations will fail.")
        ctx["llm"] = None

    # Init Search Client
    if SEARCH_AVAILABLE:
        logger.info("Initializing Search client (Tavily)...")
        try:
            tavily_key = os.getenv("TAVILY_API_KEY")
            if not tavily_key:
                raise ValueError("TAVILY_API_KEY environment variable not set.")
            search_client = SearchService(api_key=tavily_key)
            ctx["search_client"] = search_client
            logger.info("Search client initialized.")
        except Exception as search_init_err:
            logger.exception(f"Search client init failed: {search_init_err}")
            ctx["search_client"] = None
    else:
        logger.warning("Search client unavailable. Search operations will fail.")
        ctx["search_client"] = None

    logger.info("Researcher worker startup complete.")


async def shutdown(ctx: dict):
    """Clean up resources."""
    logger.info("Researcher worker shutting down...")
    # Add cleanup if needed (e.g., engine.dispose() if engine stored in ctx)
    logger.info("Researcher worker shutdown complete.")


# ==============================================================================
# Arq Worker Settings Class
# ==============================================================================


class WorkerSettings:
    """Arq worker settings for the researcher tasks."""

    functions = [run_profile_research]
    queue_name = "researcher_queue"  # Ensure this matches API enqueue target
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 600  # 10 minutes timeout per research job
    # max_tries = 3 # Example: Allow up to 3 tries per job
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
    # redis_settings = RedisSettings(...) # Configure Redis connection here if needed
