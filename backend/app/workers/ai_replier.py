# backend/app/workers/ai_replier_arq.py

import os
import asyncio
import random
from uuid import UUID, uuid4
from loguru import logger
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

# --- Arq Imports ---
# from arq import Retry
from arq.connections import ArqRedis, RedisSettings


# --- LangGraph Imports ---
try:
    from app.services.ai_reply.graph import create_reply_graph
    from app.services.ai_reply.graph_state import ConversationState

    REPLY_GRAPH_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import reply graph components: {e}")
    REPLY_GRAPH_AVAILABLE = False

# --- LangChain Imports ---
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import (
        BaseMessage,
        HumanMessage,
        AIMessage,
    )

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain components unavailable.")

    class BaseChatModel:
        pass

    class BaseMessage:
        pass

    class HumanMessage:
        pass

    class AIMessage:
        pass


# --- Project Imports ---
# Database & Config
try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
    )
    from app.database import AsyncSessionLocal
    from app.config import get_settings

    settings = get_settings()
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.error("SQLAlchemy/config unavailable.")
    AsyncSession = None
    settings = type("obj", (object,), {"DATABASE_URL": None})()

# Repositories
try:
    from app.services.repository import message as message_repo
    from app.services.repository import conversation as conversation_repo
    from app.services.repository import (
        company_profile as profile_repo,
    )
    from app.services.repository import (
        bot_agent as bot_agent_repo,
    )

    REPO_AVAILABLE = True
except ImportError:
    REPO_AVAILABLE = False
    logger.error("One or more repositories unavailable.")

# Models & Schemas
try:
    from app.models.message import Message
    from app.api.schemas.message import MessageCreate
    from app.api.schemas.company_profile import CompanyProfileSchema
    from app.api.schemas.bot_agent import BotAgentRead

    MODELS_SCHEMAS_AVAILABLE = True
except ImportError:
    MODELS_SCHEMAS_AVAILABLE = False
    logger.error("Models/Schemas unavailable.")

    class Message:
        pass

    class MessageCreate:
        pass

    class CompanyProfileSchema:
        pass

    class BotAgentRead:
        pass


try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.error("Embedding utils unavailable.")


from app.services.queue.redis_queue import RedisQueue

# --- Configuration ---
RESPONSE_SENDER_QUEUE_NAME = "response_queue"
AI_DELAY_BASE_SECONDS = float(os.getenv("AI_DELAY_BASE_SECONDS", "0.5"))
AI_DELAY_PER_CHAR_SECONDS = float(os.getenv("AI_DELAY_PER_CHAR_SECONDS", "0.025"))
AI_DELAY_RANDOM_SECONDS = float(os.getenv("AI_DELAY_RANDOM_SECONDS", "1.5"))
AI_DELAY_MIN_SECONDS = float(os.getenv("AI_DELAY_MIN_SECONDS", "0.5"))
AI_DELAY_MAX_SECONDS = float(os.getenv("AI_DELAY_MAX_SECONDS", "5.0"))
CONVERSATION_HISTORY_LIMIT = 20


# ==============================================================================
# Helper Functions
# ==============================================================================


def _compute_delay(response_text: str) -> float:
    response_length = len(response_text)
    length_delay = response_length * AI_DELAY_PER_CHAR_SECONDS
    base_calculated_delay = AI_DELAY_BASE_SECONDS + length_delay
    random_offset = random.uniform(-AI_DELAY_RANDOM_SECONDS, AI_DELAY_RANDOM_SECONDS)
    total_delay = base_calculated_delay + random_offset
    return max(AI_DELAY_MIN_SECONDS, min(AI_DELAY_MAX_SECONDS, total_delay))


def _format_db_history_to_lc(db_messages: List[Message]) -> List[BaseMessage]:
    """Converts DB Message history to LangChain BaseMessage list."""
    formatted_history: List[BaseMessage] = []
    for msg in reversed(db_messages):
        if msg.direction == "in" and msg.content:
            formatted_history.append(HumanMessage(content=msg.content))
        elif msg.direction == "out" and msg.content:
            formatted_history.append(AIMessage(content=msg.content))
    logger.debug(f"Formatted {len(formatted_history)} DB messages to LangChain format.")
    return formatted_history


# ==============================================================================
# Arq Task Definition
# ==============================================================================


async def handle_ai_reply_request(
    ctx: dict,
    account_id: UUID,
    conversation_id: UUID,
    trigger_message_id: UUID,
):
    """
    Arq task to generate and queue an AI reply using the LangGraph agent.
    """
    task_id = ctx.get("job_id", "unknown_job")
    logger.info(
        f"[AIReplyTask:{task_id}] Starting for Conv: {conversation_id}, TriggerMsg: {trigger_message_id}"
    )

    # --- Get Dependencies from Worker Context ---
    db_session_factory: Optional[Any] = ctx.get("db_session_factory")
    llm_client: Optional[BaseChatModel] = ctx.get("llm")
    arq_pool: Optional[ArqRedis] = ctx.get("arq_pool")

    # --- Validate Dependencies ---
    if not db_session_factory or not llm_client or not arq_pool:
        error_msg = (
            "Missing dependencies in Arq context (db_factory, llm, or arq_pool)."
        )
        logger.error(f"[AIReplyTask:{task_id}] {error_msg}")
        raise ValueError(f"Worker context missing dependencies for task {task_id}")

    if not REPLY_GRAPH_AVAILABLE or not REPO_AVAILABLE or not MODELS_SCHEMAS_AVAILABLE:
        error_msg = "Core components unavailable (Graph, Repos, Models/Schemas)."
        logger.error(f"[AIReplyTask:{task_id}] {error_msg}")
        raise ValueError(f"Worker missing core components for task {task_id}")

    # --- Prepare Graph Input ---
    ai_response_text: Optional[str] = None
    final_state: Optional[ConversationState] = None
    try:
        async with db_session_factory() as db:
            logger.debug(f"[{task_id}] Loading data from DB...")
            profile = await profile_repo.get_profile_by_account_id(
                db, account_id=account_id
            )
            conversation = await conversation_repo.find_conversation_by_id(
                db,
                account_id=account_id,
                conversation_id=conversation_id,
            )

            agent_config: Optional[BotAgentRead] = None
            if (
                conversation
                and conversation.inbox
                and conversation.inbox.bot_agent_inboxes
            ):
                agent_data = await bot_agent_repo.get_bot_agent_for_inbox(
                    db,
                    inbox_id=conversation.inbox.id,
                    account_id=account_id,
                )
                if agent_data:
                    agent_config = BotAgentRead.model_validate(agent_data)

            history_db = await message_repo.find_messages_by_conversation(
                db,
                account_id=account_id,
                conversation_id=conversation_id,
                limit=CONVERSATION_HISTORY_LIMIT,
            )

            if not profile:
                raise ValueError(f"CompanyProfile not found for account {account_id}")
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            if not agent_config:
                raise ValueError(
                    f"No active BotAgent configured for inbox {conversation.inbox_id}"
                )
            if not history_db:
                raise ValueError(
                    f"Cannot reply to conversation {conversation_id} with no history."
                )

            last_user_message = history_db[0]
            if last_user_message.direction != "in" or not last_user_message.content:
                logger.warning(
                    f"[{task_id}] Last message is not from user or has no content. Skipping reply."
                )
                return

            formatted_history = _format_db_history_to_lc(history_db)

            # Graph
            compiled_reply_graph = create_reply_graph()

            initial_input = ConversationState(
                account_id=account_id,
                conversation_id=conversation_id,
                bot_agent_id=agent_config.id,
                company_profile=CompanyProfileSchema.model_validate(profile),
                agent_config=agent_config,
                messages=formatted_history,
                input_message=last_user_message.content,
                retrieved_context=None,
                generation=None,
                error=None,
            )

            graph_config = {
                "configurable": {
                    "llm_instance": llm_client,
                    "db_session_factory": db_session_factory,
                }
            }

            logger.debug(f"[{task_id}] Invoking reply graph...")
            final_state = await compiled_reply_graph.ainvoke(
                initial_input, config=graph_config
            )

            graph_error = final_state.get("error")
            ai_response_text = final_state.get("generation")

            if graph_error:
                raise RuntimeError(f"Reply graph execution failed: {graph_error}")
            if not ai_response_text:
                raise ValueError("Reply graph finished but generated no response text.")

            logger.success(f"[{task_id}] Reply graph generated response successfully.")

            logger.info(f"[{task_id}] Creating outgoing message record...")
            internal_source_id = f"ai-reply-graph-{uuid4().hex}"
            message_data = MessageCreate(
                account_id=account_id,
                inbox_id=conversation.inbox_id,
                conversation_id=conversation.id,
                contact_id=(
                    conversation.contact_inbox.contact_id
                    if conversation.contact_inbox
                    else None
                ),
                source_id=internal_source_id,
                direction="out",
                status="processing",
                message_timestamp=datetime.now(timezone.utc),
                content=ai_response_text,
                content_type="text",
                content_attributes={
                    "source": "ai-reply-graph",
                    "channel_type": conversation.inbox.channel_type,
                },
                triggering_message_id=trigger_message_id,
            )

            ai_message = await message_repo.create_message(
                db=db, message_data=message_data
            )

            await db.refresh(ai_message)
            logger.info(
                f"[{task_id}] Created outgoing AI message record with ID: {ai_message.id}"
            )

            final_delay = _compute_delay(ai_response_text)
            if final_delay > 0:
                logger.debug(f"[{task_id}] Applying delay: {final_delay:.2f}s")
                await asyncio.sleep(final_delay)

            sender_payload = {"message_id": str(ai_message.id)}

            output_queue = RedisQueue(queue_name=RESPONSE_SENDER_QUEUE_NAME)
            await output_queue.enqueue(sender_payload)

            logger.info(
                f"[{task_id}] Enqueued message {ai_message.id} to '{RESPONSE_SENDER_QUEUE_NAME}' for sending."
            )

            await db.commit()
            logger.debug(f"[{task_id}] DB transaction committed.")

    except Exception as e:
        logger.exception(f"[{task_id}] Error processing AI reply request: {e}")
        raise


# ==============================================================================
# Arq Worker Configuration Callbacks
# ==============================================================================


async def startup(ctx: dict):
    """Initialize resources: DB factory, LLM client, Arq Pool."""
    logger.info("AI Replier (Arq) worker starting up...")

    # Init DB Factory
    db_session_factory = None
    if SQLALCHEMY_AVAILABLE and settings.DATABASE_URL:
        logger.info("Initializing database connection...")
        try:
            db_session_factory = AsyncSessionLocal
            ctx["db_session_factory"] = db_session_factory
            logger.info("Database session factory created.")
        except Exception as db_init_err:
            logger.exception(f"DB init failed: {db_init_err}")
            ctx["db_session_factory"] = None
    else:
        logger.warning("SQLAlchemy/DB URL unavailable.")
        ctx["db_session_factory"] = None

    # Init LLM Client
    if LANGCHAIN_AVAILABLE:
        logger.info("Initializing LLM client...")
        try:
            llm = ChatOpenAI(
                model="gpt-4o", temperature=0.1
            )  # Usar modelo principal aqui
            ctx["llm"] = llm
            logger.info(f"LLM client ({llm.__class__.__name__}) initialized.")
        except Exception as llm_init_err:
            logger.exception(f"LLM init failed: {llm_init_err}")
            ctx["llm"] = None
    else:
        logger.warning("LangChain unavailable.")
        ctx["llm"] = None

    try:
        from app.core.arq_manager import _arq_redis_pool
        from app.core.arq_manager import get_arq_pool

        arq_redis_pool = _arq_redis_pool
        if arq_redis_pool is None:
            from app.core.arq_manager import init_arq_pool

            await init_arq_pool()
            arq_redis_pool = get_arq_pool()
        if arq_redis_pool:
            ctx["arq_pool"] = arq_redis_pool
            logger.info("Using existing ARQ Redis pool.")
        else:
            raise ValueError("ARQ Pool from manager is None")
    except (ImportError, ValueError, Exception) as pool_err:
        logger.warning(
            f"Could not get ARQ pool from manager ({pool_err}). Will create separate client if needed."
        )
        ctx["arq_pool"] = None

    logger.info("AI Replier (Arq) worker startup complete.")


async def shutdown(ctx: dict):
    """Clean up resources."""
    logger.info("AI Replier (Arq) worker shutting down...")
    arq_pool_client = ctx.get("arq_pool")
    logger.info("AI Replier (Arq) worker shutdown complete.")


# ==============================================================================
# Arq Worker Settings Class
# ==============================================================================


class WorkerSettings:
    """Arq worker settings for the AI reply tasks."""

    functions = [handle_ai_reply_request]
    queue_name = "ai_reply_queue"
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 120
    # max_tries = 3 # Considerar retentativas
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=0,
    )
