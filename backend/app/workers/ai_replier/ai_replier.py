# backend/app/workers/ai_replier_arq.py

import os
import asyncio
import random
import json
from uuid import UUID, uuid4
from loguru import logger
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

# --- Third-Party Imports ---
from fastapi.encoders import jsonable_encoder
from arq.connections import ArqRedis, RedisSettings

# --- LangGraph Imports ---
try:
    from app.services.ai_reply.graph import create_reply_graph
    from app.services.ai_reply.graph_state import ConversationState

    REPLY_GRAPH_AVAILABLE = True
    logger.info("Successfully imported LangGraph components.")
except ImportError as e:
    logger.error(f"Failed to import LangGraph components: {e}. AI reply limited.")
    REPLY_GRAPH_AVAILABLE = False

    class ConversationState(dict):
        pass


# --- LangGraph Checkpointer ---
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    CHECKPOINTER_AVAILABLE = True
    logger.info("Successfully imported LangGraph AsyncPostgresSaver.")
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    logger.error("Failed to import AsyncPostgresSaver. Persistence disabled.")

    class AsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, *args, **kwargs):
            class DummyCheckpointer:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    pass

            return DummyCheckpointer()


# --- LangChain Imports ---
try:
    from langchain_openai import AzureChatOpenAI
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    LANGCHAIN_AVAILABLE = True
    logger.info("Successfully imported LangChain components.")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain components unavailable. LLM limited.")

    class BaseChatModel:
        pass

    class BaseMessage:
        pass

    class HumanMessage:
        pass

    class AIMessage:
        pass


# --- Project Imports ---
# Database & Configuration
try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.database import AsyncSessionLocal
    from app.config import get_settings

    settings = get_settings()
    SQLALCHEMY_AVAILABLE = True
    logger.info("Successfully imported SQLAlchemy components and settings.")
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.error("SQLAlchemy/config components unavailable. DB operations will fail.")
    AsyncSession = None
    async_sessionmaker = None
    settings = type(
        "obj",
        (object,),
        {
            "DATABASE_URL": None,
            "REDIS_HOST": "localhost",
            "REDIS_PORT": 6379,
            "REDIS_DB": 0,
            "MESSAGE_QUEUE_NAME": "message_queue",
            "RESPONSE_SENDER_QUEUE_NAME": "response_queue",
            "AI_REPLY_QUEUE_NAME": "ai_reply_queue",
            "OPENAI_MODEL_NAME": "gpt-4o-mini",
            "OPENAI_TEMPERATURE": 0.7,
            "FAST_LLM_MODEL_NAME": "gpt-4o-mini",
            "FAST_LLM_TEMPERATURE": 0.1,
        },
    )()

# Repositories
try:
    from app.services.repository import message as message_repo
    from app.services.repository import conversation as conversation_repo
    from app.services.repository import company_profile as profile_repo
    from app.services.repository import bot_agent as bot_agent_repo

    REPO_AVAILABLE = True
    logger.info("Successfully imported repository components.")
except ImportError:
    REPO_AVAILABLE = False
    logger.error("Repositories unavailable. Data access will fail.")

# Models & Schemas
try:
    from app.models.message import Message
    from app.models.conversation import Conversation
    from app.api.schemas.message import MessageCreate
    from app.api.schemas.company_profile import CompanyProfileSchema
    from app.api.schemas.bot_agent import BotAgentRead

    MODELS_SCHEMAS_AVAILABLE = True
    logger.info("Successfully imported model and schema components.")
except ImportError:
    MODELS_SCHEMAS_AVAILABLE = False
    logger.error("Models/Schemas unavailable. Data handling impaired.")

    class Message:
        pass

    # Dummy with new fields
    class Conversation:
        is_simulation: bool = False
        inbox_id: Optional[UUID] = None
        contact_inbox: Any = None
        account_id: Optional[UUID] = None
        inbox: Any = None
        current_sales_stage: Optional[str] = None
        last_spin_question_type: Optional[str] = None

    class MessageCreate:
        pass

    # Dummy
    class CompanyProfileSchema:
        pass

    class BotAgentRead:
        id: Optional[UUID] = None


# Embedding Utilities (Optional)
try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
    logger.info("Successfully imported embedding utilities.")
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.warning("Embedding utilities unavailable. RAG might be affected.")

# Queue & WebSocket Services
from app.services.queue.redis_queue import RedisQueue, IQueue
from app.services.helper.websocket import publish_to_conversation_ws

# --- Configuration Constants ---
RESPONSE_SENDER_QUEUE_NAME = settings.RESPONSE_SENDER_QUEUE_NAME
AI_DELAY_BASE_SECONDS = float(os.getenv("AI_DELAY_BASE_SECONDS", "0.5"))
AI_DELAY_PER_CHAR_SECONDS = float(os.getenv("AI_DELAY_PER_CHAR_SECONDS", "0.025"))
AI_DELAY_RANDOM_SECONDS = float(os.getenv("AI_DELAY_RANDOM_SECONDS", "1.5"))
AI_DELAY_MIN_SECONDS = float(os.getenv("AI_DELAY_MIN_SECONDS", "0.02"))
AI_DELAY_MAX_SECONDS = float(os.getenv("AI_DELAY_MAX_SECONDS", "0.03"))
CONVERSATION_HISTORY_LIMIT = 20

# ==============================================================================
# Helper Functions
# ==============================================================================


def _compute_delay(response_text: str) -> float:
    """Calculates simulated typing delay."""
    if not response_text:
        return AI_DELAY_MIN_SECONDS
    response_length = len(response_text)
    length_delay = response_length * AI_DELAY_PER_CHAR_SECONDS
    base_calculated_delay = AI_DELAY_BASE_SECONDS + length_delay
    random_offset = random.uniform(
        -AI_DELAY_RANDOM_SECONDS / 2, AI_DELAY_RANDOM_SECONDS / 2
    )
    total_delay = base_calculated_delay + random_offset
    clamped_delay = max(AI_DELAY_MIN_SECONDS, min(AI_DELAY_MAX_SECONDS, total_delay))
    logger.debug(f"Computed delay: Clamped={clamped_delay:.2f}s")
    return clamped_delay


def _format_db_history_to_lc(db_messages: List[Message]) -> List[BaseMessage]:
    """Converts DB Message list to LangChain BaseMessage list (chronological)."""
    if not LANGCHAIN_AVAILABLE or not db_messages:
        return []
    formatted_history: List[BaseMessage] = []
    # Iterate chronologically (oldest first for LangChain)
    for msg in reversed(db_messages):
        if msg.direction == "in" and msg.content:
            formatted_history.append(HumanMessage(content=msg.content))
        elif msg.direction == "out" and msg.content:
            formatted_history.append(AIMessage(content=msg.content))
    logger.debug(f"Formatted {len(formatted_history)} DB messages to LangChain format.")
    return formatted_history


# ==============================================================================
# Arq Task Definition: handle_ai_reply_request
# ==============================================================================


async def _process_one_message(
    db: AsyncSession,
    account_id: UUID,
    trigger_message_id: str,
    task_id: str,
    agent_config_db: Dict[str, Any],
    final_state: Dict[str, Any],
    conversation: Conversation,
    ai_response_text: str,
):
    log_prefix = f"[AIReplyTask:{task_id}|Conv:{conversation.id}|Acc:{account_id}]"
    # --- Create Outgoing Message ---
    logger.debug(f"{log_prefix} Creating outgoing message record...")
    internal_source_id = f"ai-reply-graph-{task_id}-{uuid4().hex[:8]}"
    contact_id = (
        conversation.contact_inbox.contact_id if conversation.contact_inbox else None
    )

    message_data = MessageCreate(
        account_id=account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=contact_id,
        source_id=internal_source_id,
        direction="out",
        status="processing",  # Will be sent or delivered later
        message_timestamp=datetime.now(timezone.utc),
        content=ai_response_text,
        content_type="text",
        content_attributes={
            "source": "ai-reply-graph",
            "final_sales_stage": final_state.get(
                "current_sales_stage", ""
            ),  # Get final stage from state
            "intent_classified": final_state.get(
                "intent", ""
            ),  # Get final intent from state
            "bot_agent_id": (str(agent_config_db.id) if agent_config_db else None),
        },
        triggering_message_id=trigger_message_id,
        is_simulation=conversation.is_simulation,
    )
    ai_message = await message_repo.create_message(db=db, message_data=message_data)
    await db.flush()
    await db.refresh(ai_message)
    logger.info(
        f"{log_prefix} Created outgoing AI message record (ID: {ai_message.id})."
    )

    # --- Handle Simulation vs Real ---
    if conversation.is_simulation:
        logger.info(
            f"{log_prefix} Publishing simulation message {ai_message.id} via WebSocket."
        )
        try:
            message_payload_ws = jsonable_encoder(ai_message)  # Use jsonable_encoder
            await publish_to_conversation_ws(
                conversation_id=conversation.id,
                data={"type": "new_message", "payload": message_payload_ws},
            )
            # Update status in DB for simulation after successful WS publish
            ai_message.status = "delivered"
            db.add(ai_message)
            await db.flush([ai_message])
            logger.info(
                f"{log_prefix} Published simulation message {ai_message.id} to WS and marked delivered."
            )
        except Exception as ws_err:
            logger.error(
                f"{log_prefix} Failed to publish simulation message {ai_message.id} to WS: {ws_err}"
            )
            # Keep status as 'processing' or potentially move to 'failed'
    else:
        # Apply delay and enqueue for real sending
        final_delay = _compute_delay(ai_response_text)
        logger.info(
            f"{log_prefix} Applying delay of {final_delay:.2f}s before queueing message {ai_message.id}."
        )
        if final_delay > 0:
            await asyncio.sleep(final_delay)

        sender_payload = {"message_id": str(ai_message.id)}
        output_queue = RedisQueue(queue_name=RESPONSE_SENDER_QUEUE_NAME)
        await output_queue.enqueue(sender_payload)
        logger.info(
            f"{log_prefix} Enqueued message {ai_message.id} to '{RESPONSE_SENDER_QUEUE_NAME}'."
        )
        # Status remains 'processing' until the sender confirms delivery

    # --- Commit Transaction ---
    await db.commit()
    logger.info(f"{log_prefix} Database transaction committed successfully.")


async def handle_ai_reply_request(
    ctx: dict,
    account_id: UUID,
    conversation_id: UUID,
    trigger_message_id: UUID,
):
    """
    Arq task using LangGraph with persistence to generate and handle AI replies.
    """
    task_id = ctx.get("job_id", f"adhoc-{uuid4().hex[:6]}")
    log_prefix = f"[AIReplyTask:{task_id}|Conv:{conversation_id}|Acc:{account_id}]"
    logger.info(f"{log_prefix} Starting task triggered by Msg: {trigger_message_id}")

    # --- 1. Get Dependencies ---
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = ctx.get(
        "db_session_factory"
    )
    llm_primary_client: Optional[BaseChatModel] = ctx.get("llm_primary")
    llm_fast_client: Optional[BaseChatModel] = ctx.get("llm_fast")
    arq_pool: Optional[ArqRedis] = ctx.get("arq_pool")

    # --- 2. Validate Dependencies ---
    if not all([db_session_factory, llm_primary_client, llm_fast_client, arq_pool]):
        error_msg = "Critical dependencies missing (db_factory, llms, arq_pool)."
        logger.error(f"{log_prefix} {error_msg}")
        raise ValueError(f"Worker context missing dependencies for task {task_id}")

    if not CHECKPOINTER_AVAILABLE:
        error_msg = "LangGraph checkpointer unavailable."
        logger.error(f"{log_prefix} {error_msg}")
        raise ValueError(f"Checkpointer unavailable for task {task_id}")

    if not all(
        [
            REPLY_GRAPH_AVAILABLE,
            REPO_AVAILABLE,
            MODELS_SCHEMAS_AVAILABLE,
            LANGCHAIN_AVAILABLE,
        ]
    ):
        error_msg = "Core application components unavailable."
        logger.error(f"{log_prefix} {error_msg}")
        raise ValueError(f"Worker missing core components for task {task_id}")

    # --- 3. Main Processing Block ---
    ai_response_text: Optional[str] = None
    final_state: Optional[ConversationState] = None
    try:
        # --- 3a. Use Checkpointer Context Manager ---
        serializer = JsonPlusSerializer()
        db_conn_string = str(settings.DATABASE_URL).replace("+asyncpg", "")
        async with AsyncPostgresSaver.from_conn_string(
            db_conn_string, serde=serializer
        ) as checkpointer:
            logger.debug(
                f"{log_prefix} AsyncPostgresSaver checkpointer context acquired."
            )

            # --- 3b. Compile Graph *with* Checkpointer ---
            logger.debug(f"{log_prefix} Compiling reply graph with checkpointer...")
            compiled_reply_graph = create_reply_graph(checkpointer=checkpointer)
            logger.debug(f"{log_prefix} Reply graph compiled.")

            # --- 3c. Use DB Session from Factory ---
            async with db_session_factory() as db:
                # --- Load Data ---
                logger.debug(f"{log_prefix} Loading data from database...")
                profile_db = await profile_repo.get_profile_by_account_id(
                    db, account_id=account_id
                )
                conversation = await conversation_repo.find_conversation_by_id(
                    db, account_id=account_id, conversation_id=conversation_id
                )
                history_db = await message_repo.find_messages_by_conversation(
                    db,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    limit=CONVERSATION_HISTORY_LIMIT,
                )
                agent_config_db: Optional[BotAgentRead] = None
                if conversation and conversation.inbox_id:
                    agent_data = await bot_agent_repo.get_bot_agent_for_inbox(
                        db, inbox_id=conversation.inbox_id, account_id=account_id
                    )
                    if agent_data:
                        agent_config_db = BotAgentRead.model_validate(agent_data)

                logger.info(
                    "{log_prefix} Initial history has {initial_lc_history_len} Messages"
                )
                # --- Validate Data ---
                if not profile_db:
                    raise ValueError(f"CompanyProfile not found: {account_id}")
                if not conversation:
                    raise ValueError(f"Conversation not found: {conversation_id}")
                if not agent_config_db:
                    logger.warning(f"{log_prefix} No BotAgent. Skipping.")
                    return
                if not history_db:
                    logger.warning(f"{log_prefix} No history. Skipping.")
                    return

                last_db_message = history_db[
                    0
                ]  # Most recent is first due to query order
                if last_db_message.direction != "in" or not last_db_message.content:
                    logger.info(
                        f"{log_prefix} Latest msg not suitable (not 'in' or no content). Skipping."
                    )
                    return

                # --- Prepare Graph State Input ---
                # Checkpointer handles loading persisted state. We provide current context.
                logger.debug(f"{log_prefix} Preparing initial input for LangGraph...")
                formatted_history = _format_db_history_to_lc([last_db_message])

                profile_dict = CompanyProfileSchema.model_validate(
                    profile_db
                ).model_dump(mode="json")
                agent_config_dict = BotAgentRead.model_validate(agent_data).model_dump(
                    mode="json"
                )

                # Provide the *inputs* needed for this turn, checkpointer merges with saved state
                current_input: ConversationState = {
                    "account_id": account_id,  # Pass identifiers
                    "conversation_id": conversation_id,
                    "bot_agent_id": agent_config_db.id,
                    "company_profile": profile_dict,
                    "agent_config": agent_config_dict,
                    "messages": formatted_history,
                    "input_message": last_db_message.content,
                    "is_simulation": conversation.is_simulation,
                    # Initialize fields that might be calculated anew each turn or have defaults
                    "retrieved_context": None,
                    "generation": None,
                    "error": None,
                    # "loop_count": 0,  # Reset loop count? Or let checkpoint manage? Let checkpoint manage.
                    # "current_objection": None,
                    # "objection_loop_count": 0,
                    # Fields managed entirely by checkpoint (don't need to initialize here unless setting default)
                    # "current_sales_stage": None,
                    # "customer_needs": [],
                    # "customer_pain_points": [],
                    # "spin_question_type": None,
                    # "problem_mentioned": None,
                    # "need_expressed": None,
                    # "last_spin_question_type": None,
                    # "explicit_need_identified": False, # Checkpointer should load this
                    # "intent": None,
                    # "classification_details": None,
                    # "certainty_level": None,
                    # "certainty_focus": None,
                    # "proposed_solution_details": None,
                }
                logger.trace(
                    f"{log_prefix} Current graph input prepared: {current_input}"
                )

                # --- Prepare Graph Config ---
                graph_config = {
                    "configurable": {
                        "thread_id": str(
                            conversation_id
                        ),  # Use conversation ID as thread ID
                        "llm_primary_instance": llm_primary_client,
                        "llm_fast_instance": llm_fast_client,
                        "db_session_factory": db_session_factory,
                    }
                }
                logger.debug(
                    f"{log_prefix} Graph config prepared with thread_id: {conversation_id}"
                )

                snapshot = await compiled_reply_graph.aget_state(graph_config)
                previous_messages_state = snapshot.values.get("messages", [])
                previous_checkpoint_message_ids = set()
                if isinstance(previous_messages_state, list):
                    previous_checkpoint_message_ids = {
                        str(msg.id)
                        for msg in previous_messages_state
                        if isinstance(msg, AIMessage) and hasattr(msg, "id")
                    }

                # logger.debug(
                #     f"{log_prefix} Snapshot of the messages of the Current Graph: {previous_checkpoint_message_ids}"
                # )

                # --- Invoke Graph ---

                if (
                    last_db_message.content.lower().strip()
                    == settings.RESET_MESSAGE_TRIGGER
                ):
                    logger.info(
                        f"{log_prefix}  Trigger de reset conversation process..."
                    )
                    graph_error = None
                    ai_response_text = settings.RESET_MESSAGE_TRIGGER
                    final_state = {}
                    new_ai_messages_lc: List[AIMessage] = [
                        AIMessage(content=ai_response_text)
                    ]
                else:
                    logger.info(
                        f"{log_prefix} Invoking reply graph with checkpointer..."
                    )
                    final_state = await compiled_reply_graph.ainvoke(
                        current_input, config={**graph_config, "recursion_limit": 50}
                    )

                    logger.info(f"{log_prefix} Reply graph execution finished.")
                    logger.trace(
                        f"{log_prefix} Final graph state from checkpointer: {final_state}"
                    )

                    # --- Process Graph Output ---
                    graph_error = final_state.get("error")
                    final_messages_lc = final_state.get("messages", [])

                    new_ai_messages_lc: List[AIMessage] = []
                    for msg in final_messages_lc:
                        if (
                            isinstance(msg, AIMessage)
                            and hasattr(msg, "id")
                            and str(msg.id) not in previous_checkpoint_message_ids
                        ):
                            new_ai_messages_lc.append(msg)
                            logger.debug(
                                f"{log_prefix} Identified new AI message ID: {msg.id}"
                            )

                    logger.debug(
                        f"{log_prefix} final messages: {final_messages_lc}, final ai messages: {new_ai_messages_lc}"
                    )

                    if graph_error:
                        logger.error(
                            f"{log_prefix} Graph execution finished with error: {graph_error}"
                        )

                    if not new_ai_messages_lc and not graph_error:
                        logger.warning(
                            f"{log_prefix} Graph finished but no new AI messages were added."
                        )

                    elif not new_ai_messages_lc and graph_error:
                        logger.error(
                            f"{log_prefix} Graph failed and no fallback message generated."
                        )
                        raise RuntimeError(f"Graph failed: {graph_error}")
                    else:
                        logger.success(
                            f"{log_prefix} Graph generated {len(new_ai_messages_lc)} new AI message(s)."
                        )

                    USE_GENERATION_RESPONSE = True
                    if USE_GENERATION_RESPONSE:
                        new_ai_messages_lc = [
                            AIMessage(content=final_state.get("generation", ""))
                        ]

                for _, ai_msg_lc in enumerate(new_ai_messages_lc):
                    if isinstance(ai_msg_lc, AIMessage) and ai_msg_lc.content:
                        ai_response_text = ai_msg_lc.content.replace(
                            "**", "*"
                        )  # correct the bold style for whatsapp
                        await _process_one_message(
                            db=db,
                            account_id=account_id,
                            trigger_message_id=trigger_message_id,
                            task_id=task_id,
                            conversation=conversation,
                            agent_config_db=agent_config_db,
                            final_state=final_state,
                            ai_response_text=ai_response_text,
                        )

    except Exception as e:
        logger.exception(
            f"{log_prefix} Unhandled error processing AI reply request: {e}"
        )

        raise

    finally:
        logger.info(f"{log_prefix} Task finished.")


# ==============================================================================
# Arq Worker Configuration Callbacks
# ==============================================================================


async def startup(ctx: dict):
    """Initializes resources needed by the worker task."""
    worker_id = os.getpid()
    logger.info(f"AI Replier Arq worker (PID: {worker_id}) starting up...")

    # Init DB Factory
    db_session_factory = None
    if SQLALCHEMY_AVAILABLE and settings.DATABASE_URL:
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

    # Init LLM Clients
    llm_primary_client = None
    llm_fast_client = None
    if LANGCHAIN_AVAILABLE:
        logger.info("Initializing LLM clients...")
        try:
            openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            if not openai_api_key:
                raise EnvironmentError("AZURE_OPENAI_API_KEY not set.")

            llm_primary_client = AzureChatOpenAI(
                azure_deployment=settings.OPENAI_MODEL_NAME,
                temperature=settings.OPENAI_TEMPERATURE,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version="2025-01-01-preview",  # settings.OPENAI_API_VERSION,
            )

            llm_response_test = llm_primary_client.invoke("Olá")
            logger.debug(f"Primary LLM client is working :{llm_response_test.content}")

            ctx["llm_primary"] = llm_primary_client
            logger.info(f"Primary LLM client initialized: {settings.OPENAI_MODEL_NAME}")

            fast_model_name = getattr(settings, "FAST_LLM_MODEL_NAME", "gpt4o")
            fast_temperature = float(getattr(settings, "FAST_LLM_TEMPERATURE", 0.0))

            llm_fast_client = AzureChatOpenAI(
                azure_deployment=fast_model_name,
                temperature=fast_temperature,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version="2025-01-01-preview",
            )

            llm_response_test = llm_fast_client.invoke("Olá")
            logger.debug(f"Fast LLM client is working :{llm_response_test.content}")

            ctx["llm_fast"] = llm_fast_client
            logger.info(f"Fast LLM client initialized: {fast_model_name}")

            logger.success("LLM clients initialized.")
        except EnvironmentError as env_err:
            logger.error(f"LLM initialization failed: {env_err}")
        except Exception as llm_init_err:
            logger.exception(f"LLM init failed: {llm_init_err}")
        finally:
            # Ensure keys exist even if initialization failed
            if "llm_primary" not in ctx:
                ctx["llm_primary"] = None
            if "llm_fast" not in ctx:
                ctx["llm_fast"] = None
    else:
        logger.warning("LangChain unavailable. LLM functionality limited.")
        ctx["llm_primary"] = None
        ctx["llm_fast"] = None

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
    logger.info(f"AI Replier Arq worker (PID: {worker_id}) shutting down...")

    logger.info(f"AI Replier Arq worker (PID: {worker_id}) shutdown complete.")


# ==============================================================================
# Arq Worker Settings Class
# ==============================================================================


class WorkerSettings:
    """Configuration class for the Arq worker."""

    functions = [handle_ai_reply_request]
    queue_name = settings.AI_REPLY_QUEUE_NAME
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 120  # seconds
    keep_alive = 60  # seconds
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )

    logger.info(
        f"Arq Worker configured for queue '{queue_name}' on {settings.REDIS_HOST}:{settings.REDIS_PORT} DB {settings.REDIS_DB}"
    )
