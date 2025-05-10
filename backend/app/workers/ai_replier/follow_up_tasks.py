# app/tasks/follow_up_tasks.py
from uuid import UUID
from typing import Optional, Dict, Any
from loguru import logger
import asyncio
import os

try:
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from arq import create_pool
    from arq.connections import RedisSettings, ArqRedis
    from app.config import get_settings
    from app.services.new_agent.state_definition import RichConversationState
    from app.database import AsyncSessionLocal
    from app.core.arq_manager import get_arq_pool, init_arq_pool

    settings = get_settings()
    PROJECT_IMPORTS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Follow-up Task: Failed to import project dependencies: {e}.")
    PROJECT_IMPORTS_AVAILABLE = False
    RichConversationState = dict  # type: ignore
    AsyncPostgresSaver = None  # type: ignore
    settings = type("obj", (object,), {"AI_REPLY_QUEUE_NAME": "ai_reply_queue", "SQLITE_CHECKPOINTER_DB_PATH": "agent_memory.sqlite"})()  # type: ignore
    create_pool = None  # type: ignore
    RedisSettings = None  # type: ignore
    ArqRedis = None


async def schedule_conversation_follow_up(
    ctx: Optional[Dict[str, Any]],
    conversation_id: UUID,
    account_id: UUID,
    bot_agent_id: Optional[UUID],
    follow_up_attempt_count_for_this_job: int,
    origin_agent_message_timestamp: float,
):
    job_id = ctx.get("job_id", "N/A") if ctx else "N/A"
    conversation_id_str = str(conversation_id)
    logger.info(
        f"[ARQ FOLLOW-UP JOB - ID: {job_id}] Checking follow-up for {conversation_id_str}, "
        f"attempt {follow_up_attempt_count_for_this_job}"
    )

    if (
        not PROJECT_IMPORTS_AVAILABLE
        or not AsyncPostgresSaver
        or not create_pool
        or not RedisSettings
    ):
        logger.error(
            f"[ARQ FOLLOW-UP JOB - {job_id}] Critical project imports missing. Cannot proceed."
        )
        return f"Critical imports missing for {conversation_id_str}"

    arq_write_pool: Optional[ArqRedis] = ctx.get("arq_pool")
    checkpointer = None  # type: ignore
    try:

        serializer = JsonPlusSerializer()
        db_conn_string = str(settings.DATABASE_URL).replace("+asyncpg", "")
        async with AsyncPostgresSaver.from_conn_string(
            db_conn_string, serde=serializer
        ) as checkpointer:

            config_load_state = {"configurable": {"thread_id": conversation_id_str}}
            current_checkpoint = await checkpointer.aget(config=config_load_state)

            if not current_checkpoint:
                logger.warning(
                    f"[ARQ FOLLOW-UP JOB - {job_id}] No state found for {conversation_id_str}. Aborting follow-up."
                )
                return f"No state for {conversation_id_str}"

            current_convo_state: RichConversationState = current_checkpoint.get("channel_values", {})  # type: ignore

            if not current_convo_state.get("follow_up_scheduled"):
                logger.info(
                    f"[ARQ FOLLOW-UP JOB - {job_id}] Follow-up for {conversation_id_str} was cancelled (flag is false in state). Discarding task."
                )
                return f"Follow-up cancelled (flag) for {conversation_id_str}"

            current_last_agent_msg_ts_in_state = current_convo_state.get(
                "last_message_from_agent_timestamp"
            )
            if (
                current_last_agent_msg_ts_in_state is not None
                and current_last_agent_msg_ts_in_state > origin_agent_message_timestamp
            ):
                logger.info(
                    f"[ARQ FOLLOW-UP JOB - {job_id}] Conversation {conversation_id_str} has progressed "
                    f"(state_ts: {current_last_agent_msg_ts_in_state} > origin_ts: {origin_agent_message_timestamp}). "
                    f"This follow-up is stale. Discarding task."
                )
                return f"Follow-up stale (timestamp) for {conversation_id_str}"

            # Construir o payload para o worker ai_replier
            payload_for_ai_replier = {
                "event_type": "follow_up_timeout",  # Novo campo para distinguir
                "conversation_id": str(conversation_id),
                "account_id": str(account_id),
                "bot_agent_id": str(bot_agent_id) if bot_agent_id else None,
                "follow_up_attempt_count": follow_up_attempt_count_for_this_job,
                # Não precisamos de trigger_message_id aqui, pois não há mensagem de usuário
            }

            await init_arq_pool()  # Ensure pool is created if not already
            arq_write_pool = await get_arq_pool()  # Get the shared pool instance
            await arq_write_pool.enqueue_job(
                "handle_ai_reply_request",  # A função principal do seu ai_replier
                _queue_name=settings.AI_REPLY_QUEUE_NAME,
                # _job_id=f"follow_up_trigger_{conversation_id_str}_{follow_up_attempt_count_for_this_job}",  # ID de job opcional
                **payload_for_ai_replier,  # Passar o payload como kwargs para a função do job
            )
            logger.info(
                f"[ARQ FOLLOW-UP JOB - {job_id}] Successfully enqueued task to '{settings.AI_REPLY_QUEUE_NAME}' for ai_replier."
            )
            return f"Follow-up notification sent for {conversation_id_str}"

    except Exception as e:
        logger.exception(
            f"[ARQ FOLLOW-UP JOB - ID: {job_id}] Error processing follow-up for {conversation_id_str}: {e}"
        )
        raise
    finally:
        if checkpointer and hasattr(checkpointer, "aclose"):
            await checkpointer.aclose()
        if arq_write_pool and hasattr(arq_write_pool, "close"):
            await arq_write_pool.close()


async def startup(ctx: dict):
    """Initializes resources needed by the worker task."""
    worker_id = os.getpid()
    logger.info(f"AI Replier Arq worker (PID: {worker_id}) starting up...")

    # Init DB Factory
    db_session_factory = None
    if settings.DATABASE_URL:
        logger.info("Initializing database connection pool...")
        try:
            db_session_factory = AsyncSessionLocal
            ctx["db_session_factory"] = db_session_factory
            logger.success("Database session factory created.")
        except Exception as db_init_err:
            logger.exception(f"DB init failed: {db_init_err}")
            ctx["db_session_factory"] = None
    else:
        logger.warning("SQLAlchemy/DB URL unavailable. Database operations will fail.")
        ctx["db_session_factory"] = None

    # Init Arq Redis Pool
    arq_redis_pool = None
    logger.info("Initializing ARQ Redis pool connection...")
    try:
        # Assuming arq_manager provides these functions
        from app.core.arq_manager import get_arq_pool, init_arq_pool

        await init_arq_pool()  # Ensure pool is created if not already
        arq_redis_pool = await get_arq_pool()  # Get the shared pool instance
        if arq_redis_pool:
            ctx["arq_pool"] = arq_redis_pool
            logger.success("ARQ Redis pool obtained/initialized.")
        else:
            raise ValueError("ARQ Pool from arq_manager is None.")
    except ImportError:
        logger.error("Could not import arq_manager. ARQ queue operations might fail.")
        ctx["arq_pool"] = None
    except Exception as pool_err:
        logger.exception(f"Failed to init/get ARQ Redis pool: {pool_err}")
        ctx["arq_pool"] = None

    logger.info(f"AI Replier Arq worker (PID: {worker_id}) startup complete.")


async def shutdown(ctx: dict):
    """Cleans up resources when the worker stops."""
    worker_id = os.getpid()
    logger.info(f"Follow up task  (PID: {worker_id}) shutting down...")


# Configurações do Worker arq
class ArqWorkerSettings:
    job_timeout = 300
    max_jobs = 10  # Quantos jobs o worker pode processar concorrentemente
    functions = [schedule_conversation_follow_up]  # Registra a função
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
    # health_check_interval = 60 # Opcional
    # on_startup = async def(ctx): logger.info("ARQ Worker starting up...")
    # on_shutdown = async def(ctx): logger.info("ARQ Worker shutting down...")
