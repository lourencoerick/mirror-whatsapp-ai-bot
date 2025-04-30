import asyncio
from uuid import UUID
from loguru import logger
from typing import Optional
from arq.connections import RedisSettings

# Project Imports
try:
    from app.services.knowledge.ingestion_service import KnowledgeIngestionService

    INGESTION_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import KnowledgeIngestionService: {e}")
    INGESTION_SERVICE_AVAILABLE = False

# Database Session & Config (needed to initialize the service)
try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine,
        async_sessionmaker,
    )
    from app.config import get_settings, Settings

    settings: Settings = get_settings()
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.error("SQLAlchemy components or settings not found.")
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore
    settings = type("obj", (object,), {"DATABASE_URL": None})()

# Optional: update document status on finalization
try:
    from app.models.knowledge_document import DocumentStatus
    from app.services.repository.knowledge_document import update_document_status

    DOCUMENT_REPO_AVAILABLE = True
except ImportError:
    DOCUMENT_REPO_AVAILABLE = False
    logger.warning(
        "KnowledgeDocument repo not found; final status update may be skipped."
    )

    class DocumentStatus:
        FAILED = "failed"

    async def update_document_status(*args, **kwargs):
        pass


# ==============================================================================
# Arq Task Definition
# ==============================================================================


async def process_knowledge_source(
    ctx: dict,
    account_id: UUID,
    source_type: str,
    source_uri: str,
    source_identifier: str,
    document_id: Optional[UUID] = None,
):
    """
    Arq task to ingest a knowledge source into the vector database.

    Args:
        ctx: Arq context containing dependencies.
        account_id: The account ID.
        source_type: 'file', 'url', or 'text'.
        source_uri: Path or content of the source.
        source_identifier: Original filename, URL, or description.
        document_id: Optional parent KnowledgeDocument ID.
    """
    task_id = ctx.get("job_id", "unknown_job")
    logger.info(
        f"[KnowledgeIngesterTask:{task_id}] Starting ingestion for "
        f"Account: {account_id}, Source: {source_identifier} ({source_type})"
    )

    ingestion_service: Optional[KnowledgeIngestionService] = ctx.get(
        "ingestion_service"
    )
    if not ingestion_service:
        error_msg = (
            f"[KnowledgeIngesterTask:{task_id}] Missing IngestionService in context."
        )
        logger.error(error_msg)
        # Update document status to FAILED if possible
        if DOCUMENT_REPO_AVAILABLE and document_id and ctx.get("db_session_factory"):
            db_session_factory = ctx["db_session_factory"]
            try:
                async with db_session_factory() as db:
                    await update_document_status(
                        db,
                        document_id=document_id,
                        status=DocumentStatus.FAILED,
                        error_message="Worker configuration error",
                    )
                    await db.commit()
            except Exception as db_err:
                logger.error(f"Failed to update status on init error: {db_err}")
        raise ValueError("Worker context missing IngestionService.")

    try:
        success = await ingestion_service.ingest_source(
            account_id=account_id,
            source_type=source_type,
            source_uri=source_uri,
            source_identifier=source_identifier,
            document_id=document_id,
        )

        if success:
            logger.success(
                f"[KnowledgeIngesterTask:{task_id}] Ingestion completed successfully for source: {source_identifier}"
            )
        else:
            logger.error(
                f"[KnowledgeIngesterTask:{task_id}] Ingestion failed for source: {source_identifier}."
            )
            raise RuntimeError(f"Ingestion failed for source {source_identifier}")

    except Exception as e:
        logger.exception(
            f"[KnowledgeIngesterTask:{task_id}] Error during ingestion task: {e}"
        )
        # Update document status to FAILED if not already
        if DOCUMENT_REPO_AVAILABLE and document_id and ctx.get("db_session_factory"):
            db_session_factory = ctx["db_session_factory"]
            try:
                async with db_session_factory() as db:
                    await update_document_status(
                        db,
                        document_id=document_id,
                        status=DocumentStatus.FAILED,
                        error_message=f"Unhandled worker error: {e}",
                    )
                    await db.commit()
            except Exception as db_err:
                logger.error(f"Failed to update status on task error: {db_err}")
        raise


# ==============================================================================
# Arq Worker Callbacks
# ==============================================================================


async def startup(ctx: dict):
    """Initialize resources for the ingester worker."""
    logger.info("Knowledge Ingester worker starting up...")

    db_session_factory = None
    if SQLALCHEMY_AVAILABLE and settings.DATABASE_URL:
        logger.info("Initializing database connection...")
        try:
            engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
            db_session_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            ctx["db_session_factory"] = db_session_factory
            logger.info("Database session factory created.")
        except Exception as db_init_err:
            logger.exception(f"DB init failed: {db_init_err}")
            ctx["db_session_factory"] = None
    else:
        logger.warning("SQLAlchemy or DB URL unavailable.")
        ctx["db_session_factory"] = None

    if INGESTION_SERVICE_AVAILABLE and db_session_factory:
        logger.info("Initializing KnowledgeIngestionService...")
        try:
            service = KnowledgeIngestionService(db_session_factory=db_session_factory)
            ctx["ingestion_service"] = service
            logger.info("KnowledgeIngestionService initialized.")
        except Exception as service_init_err:
            logger.exception(f"Service init failed: {service_init_err}")
            ctx["ingestion_service"] = None
    else:
        logger.warning("Cannot initialize KnowledgeIngestionService.")
        ctx["ingestion_service"] = None

    logger.info("Worker startup complete.")


async def shutdown(ctx: dict):
    """Clean up worker resources before shutdown."""
    logger.info("Knowledge Ingester worker shutting down...")
    logger.info("Worker shutdown complete.")


class WorkerSettings:
    """Arq worker settings for knowledge ingestion tasks."""

    functions = [process_knowledge_source]
    queue_name = "knowledge_ingestion_queue"
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 900  # Task timeout in seconds (15 min)
    # max_tries = 2  # Retries can help with transient failures
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
