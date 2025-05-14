# backend/app/tasks/message_handler_task.py

import os
import asyncio
import random
import json
import time
from uuid import UUID, uuid4
from loguru import logger
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

# --- Third-Party Imports ---
from fastapi.encoders import jsonable_encoder
from arq.connections import ArqRedis  # For type hinting ctx['arq_pool']

# --- LangGraph Imports ---
try:
    from app.services.new_agent.graph import create_agent_graph
    from app.services.new_agent.state_definition import (
        RichConversationState,
        TriggerEventType,
    )

    GRAPH_AVAILABLE = True
    logger.info("MessageHandlerTask: Successfully imported LangGraph components.")
except ImportError as e:
    logger.error(
        f"MessageHandlerTask: Failed to import LangGraph components: {e}. AI reply limited."
    )
    GRAPH_AVAILABLE = False

    class RichConversationState(dict):
        pass  # type: ignore

    class TriggerEventType(str):
        pass  # type: ignore


# --- LangGraph Checkpointer ---
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    CHECKPOINTER_AVAILABLE = True
    logger.info(
        "MessageHandlerTask: Successfully imported LangGraph AsyncPostgresSaver."
    )
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    logger.error(
        "MessageHandlerTask: Failed to import AsyncPostgresSaver. Persistence disabled."
    )

    class AsyncPostgresSaver:  # type: ignore
        @classmethod
        def from_conn_string(cls, *args, **kwargs):
            class DummyCheckpointer:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    pass

            return DummyCheckpointer()

    class JsonPlusSerializer:
        pass  # type: ignore


# --- LangChain Imports ---
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

    LANGCHAIN_AVAILABLE = True
    logger.info("MessageHandlerTask: Successfully imported LangChain components.")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("MessageHandlerTask: LangChain components unavailable. LLM limited.")

    class BaseChatModel:
        pass  # type: ignore

    class BaseMessage:
        pass  # type: ignore

    class HumanMessage:
        pass  # type: ignore

    class AIMessage:
        pass  # type: ignore


# --- Project Imports ---
# Database & Configuration
try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.config import get_settings  # Use the centralized settings

    settings = get_settings()
    SQLALCHEMY_AVAILABLE = True
    logger.info(
        "MessageHandlerTask: Successfully imported SQLAlchemy components and settings."
    )
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.error(
        "MessageHandlerTask: SQLAlchemy/config components unavailable. DB operations will fail."
    )
    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    # Minimal fallback settings if app.config.settings is not available
    settings = type(
        "obj",
        (object,),
        {
            "DATABASE_URL": None,
            "RESPONSE_SENDER_QUEUE_NAME": "response_sender_queue",
            "FOLLOW_UP_SCHEDULER_QUEUE_NAME": "follow_up_scheduler_queue",
            "RESET_MESSAGE_TRIGGER": "/reset_conversation",
            "PRIMARY_LLM_MODEL_NAME": "gpt-4o-mini",  # Ensure these are present for fallback
            "PRIMARY_LLM_TEMPERATURE": 0.7,
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
    logger.info("MessageHandlerTask: Successfully imported repository components.")
except ImportError:
    REPO_AVAILABLE = False
    logger.error("MessageHandlerTask: Repositories unavailable. Data access will fail.")

# Models & Schemas
try:
    from app.models.message import Message
    from app.models.conversation import Conversation
    from app.api.schemas.message import MessageCreate
    from app.api.schemas.company_profile import CompanyProfileSchema
    from app.api.schemas.bot_agent import BotAgentRead

    MODELS_SCHEMAS_AVAILABLE = True
    logger.info(
        "MessageHandlerTask: Successfully imported model and schema components."
    )
except ImportError:
    MODELS_SCHEMAS_AVAILABLE = False
    logger.error(
        "MessageHandlerTask: Models/Schemas unavailable. Data handling impaired."
    )

    class Message:
        pass  # type: ignore

    class Conversation:  # type: ignore
        is_simulation: bool = False
        inbox_id: Optional[UUID] = None
        contact_inbox: Any = None
        account_id: Optional[UUID] = None
        inbox: Any = None
        current_sales_stage: Optional[str] = None
        last_spin_question_type: Optional[str] = None

    class MessageCreate:
        pass  # type: ignore

    class CompanyProfileSchema:
        pass  # type: ignore

    class BotAgentRead:
        id: Optional[UUID] = None  # type: ignore


# Queue & WebSocket Services
from app.services.queue.redis_queue import (
    RedisQueue,
)  # Assuming this is a simple wrapper
from app.services.helper.websocket import publish_to_conversation_ws
from app.workers.ai_replier.utils.datetime import calculate_follow_up_delay

# --- Configuration Constants ---
AI_DELAY_BASE_SECONDS = float(os.getenv("AI_DELAY_BASE_SECONDS", "0.5"))
AI_DELAY_PER_CHAR_SECONDS = float(os.getenv("AI_DELAY_PER_CHAR_SECONDS", "0.025"))
AI_DELAY_RANDOM_SECONDS = float(os.getenv("AI_DELAY_RANDOM_SECONDS", "1.5"))
AI_DELAY_MIN_SECONDS = float(os.getenv("AI_DELAY_MIN_SECONDS", "0.02"))
AI_DELAY_MAX_SECONDS = float(
    os.getenv("AI_DELAY_MAX_SECONDS", "0.03")
)  # Ensure this is a reasonable max
CONVERSATION_HISTORY_LIMIT = 20

# ==============================================================================
# Helper Functions
# ==============================================================================


def _compute_delay(response_text: str) -> float:
    """
    Calculates simulated typing delay based on response length.

    Args:
        response_text: The text of the AI's response.

    Returns:
        The calculated delay in seconds, clamped within min/max limits.
    """
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
    logger.debug(
        f"Computed delay: Clamped={clamped_delay:.2f}s for text length {response_length}"
    )
    return clamped_delay


async def _process_one_message(
    db: AsyncSession,
    account_id: UUID,
    task_id: str,
    agent_config_db: Optional[BotAgentRead],  # Can be None if not found
    final_state: Dict[str, Any],
    conversation: Conversation,
    ai_response_text: str,
):
    """
    Creates, stores, and dispatches a single AI-generated message.

    Handles DB record creation, WebSocket publishing for simulations,
    and enqueuing to the response sender for real messages.

    Args:
        db: The active SQLAlchemy async session.
        account_id: The ID of the account.
        task_id: The ID of the current ARQ task.
        agent_config_db: The configuration of the bot agent.
        final_state: The final state from the LangGraph execution.
        conversation: The conversation object.
        ai_response_text: The content of the AI's response.
    """
    log_prefix = f"[MessageHandlerTask:{task_id}|MsgProc|Conv:{conversation.id}|Acc:{account_id}]"
    logger.debug(
        f"{log_prefix} Creating outgoing message record for response: '{ai_response_text[:50]}...'"
    )

    internal_source_id = f"ai-reply-graph-{task_id}-{uuid4().hex[:8]}"
    contact_id = (
        conversation.contact_inbox.contact_id if conversation.contact_inbox else None
    )
    bot_agent_id_str = (
        str(agent_config_db.id) if agent_config_db and agent_config_db.id else None
    )

    message_data = MessageCreate(
        account_id=account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=contact_id,
        source_id=internal_source_id,
        direction="out",
        status="processing",
        message_timestamp=datetime.now(timezone.utc),
        content=ai_response_text,
        content_type="text",
        content_attributes={
            "source": "ai-reply-graph",
            "final_sales_stage": final_state.get("current_sales_stage", ""),
            "intent_classified": final_state.get("intent", ""),
            "bot_agent_id": bot_agent_id_str,
        },
        is_simulation=conversation.is_simulation,
    )
    ai_message = await message_repo.create_message(db=db, message_data=message_data)
    await db.flush()  # Ensure ID is populated
    await db.refresh(ai_message)
    logger.info(
        f"{log_prefix} Created outgoing AI message record (ID: {ai_message.id})."
    )

    if conversation.is_simulation:
        logger.info(
            f"{log_prefix} Publishing simulation message {ai_message.id} via WebSocket."
        )
        try:
            message_payload_ws = jsonable_encoder(ai_message)
            await publish_to_conversation_ws(
                conversation_id=str(conversation.id),  # Ensure string for WS
                data={"type": "new_message", "payload": message_payload_ws},
            )
            ai_message.status = "delivered"  # Mark as delivered for simulations
            db.add(ai_message)
            await db.flush([ai_message])  # Persist status update
            logger.info(
                f"{log_prefix} Published simulation message {ai_message.id} to WS and marked delivered."
            )
        except Exception as ws_err:
            logger.error(
                f"{log_prefix} Failed to publish simulation message {ai_message.id} to WS: {ws_err}"
            )
    else:
        final_delay = _compute_delay(ai_response_text)
        logger.info(
            f"{log_prefix} Applying delay of {final_delay:.2f}s before queueing message {ai_message.id}."
        )
        if final_delay > 0:
            await asyncio.sleep(final_delay)

        sender_payload = {"message_id": str(ai_message.id)}
        # Assuming RedisQueue is a simple wrapper, direct use of arq_pool for enqueueing
        # might be an option if RedisQueue is complex or not available in this context.
        # For now, keeping RedisQueue as per original.
        output_queue = RedisQueue(queue_name=settings.RESPONSE_SENDER_QUEUE_NAME)
        await output_queue.enqueue(sender_payload)
        logger.info(
            f"{log_prefix} Enqueued message {ai_message.id} to '{settings.RESPONSE_SENDER_QUEUE_NAME}'."
        )

    # Commit is handled by the main task function after all messages are processed.
    # await db.commit() # DO NOT COMMIT HERE, commit in the main task handler


# ==============================================================================
# Arq Task Definition: handle_ai_reply_request
# ==============================================================================


async def handle_ai_reply_request(
    ctx: dict,
    account_id: UUID,
    conversation_id: UUID,
    user_input_content: Optional[str] = None,
    event_type: Optional[str] = None,  # e.g., "user_message", "follow_up_timeout"
    follow_up_attempt_count: Optional[int] = 0,
    **kwargs,
):
    """
    Arq task to generate and handle AI replies using LangGraph.

    This task is triggered by new user messages or scheduled follow-up events.
    It orchestrates data loading, LangGraph execution, message processing,
    and scheduling of subsequent follow-ups.

    Args:
        ctx: The ARQ context dictionary, containing shared resources like
             db_session_factory, LLM clients, and arq_pool.
        account_id: The ID of the account this conversation belongs to.
        conversation_id: The ID of the conversation to process.
        trigger_message_id: The ID of the user message that triggered this task.
                            Can be None for follow-up events.
        event_type: The type of event that triggered this task.
        follow_up_attempt_count: The attempt number for follow-up events.
        **kwargs: Additional keyword arguments passed by ARQ.
    """
    task_id = ctx.get("job_id", f"adhoc-{uuid4().hex[:6]}")
    log_prefix_base = (
        f"[MessageHandlerTask:{task_id}|Conv:{conversation_id}|Acc:{account_id}]"
    )

    is_follow_up_trigger = event_type == "follow_up_timeout"

    if is_follow_up_trigger:
        log_prefix = (
            f"{log_prefix_base}[FollowUpTrigger|Attempt:{follow_up_attempt_count}]"
        )
        logger.info(f"{log_prefix} Starting task for follow-up.")
    elif user_input_content:
        log_prefix = f"{log_prefix_base}[MsgTrigger]"
        logger.info(f"{log_prefix} Starting task triggered by message.")
    else:
        logger.error(
            f"{log_prefix_base} Invalid trigger. Missing IDs or valid event_type. EventType: {event_type}"
        )
        return "Invalid task trigger: Missing user_input_content for non-follow-up or invalid event_type."

    # --- 1. Get Dependencies from Context ---
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = ctx.get(
        "db_session_factory"
    )
    llm_primary_client: Optional[BaseChatModel] = ctx.get("llm_primary")
    llm_fast_client: Optional[BaseChatModel] = ctx.get("llm_fast")
    arq_pool: Optional[ArqRedis] = ctx.get(
        "arq_pool"
    )  # ARQ Redis pool for enqueuing other tasks

    # --- 2. Validate Dependencies ---
    if not all([db_session_factory, llm_primary_client, llm_fast_client, arq_pool]):
        error_msg = (
            "Critical dependencies missing from context (db_factory, llms, arq_pool)."
        )
        logger.error(f"{log_prefix} {error_msg}")
        # Not raising ValueError here to allow graceful exit if possible,
        # but the task won't be able to do much.
        return f"Worker context missing dependencies for task {task_id}"

    if not CHECKPOINTER_AVAILABLE:
        error_msg = "LangGraph checkpointer (AsyncPostgresSaver) unavailable."
        logger.error(f"{log_prefix} {error_msg}")
        return f"Checkpointer unavailable for task {task_id}"

    if not all(
        [GRAPH_AVAILABLE, REPO_AVAILABLE, MODELS_SCHEMAS_AVAILABLE, LANGCHAIN_AVAILABLE]
    ):
        error_msg = (
            "Core application components (Graph, Repo, Models, LangChain) unavailable."
        )
        logger.error(f"{log_prefix} {error_msg}")
        return f"Worker missing core components for task {task_id}"

    # --- 3. Main Processing Block ---
    final_state: Optional[RichConversationState] = None
    try:
        serializer = JsonPlusSerializer()
        # Ensure DATABASE_URL is correctly formatted for AsyncPostgresSaver
        db_conn_string_pg = str(settings.DATABASE_URL).replace(
            "postgresql+asyncpg://", "postgresql://"
        )

        async with AsyncPostgresSaver.from_conn_string(
            db_conn_string_pg, serde=serializer
        ) as checkpointer:
            logger.debug(
                f"{log_prefix} AsyncPostgresSaver checkpointer context acquired."
            )
            compiled_reply_graph = create_agent_graph(checkpointer=checkpointer)
            logger.debug(f"{log_prefix} Reply graph compiled with checkpointer.")

            async with db_session_factory() as db:
                logger.debug(f"{log_prefix} Database session acquired.")
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

                agent_config_db_model: Optional[BotAgentRead] = None
                if conversation and conversation.inbox_id:
                    agent_data_raw = await bot_agent_repo.get_bot_agent_for_inbox(
                        db, inbox_id=conversation.inbox_id, account_id=account_id
                    )
                    if agent_data_raw:
                        agent_config_db_model = BotAgentRead.model_validate(
                            agent_data_raw
                        )

                if not profile_db:
                    logger.error(
                        f"{log_prefix} CompanyProfile not found for account {account_id}. Aborting."
                    )
                    return f"CompanyProfile not found: {account_id}"
                if not conversation:
                    logger.error(
                        f"{log_prefix} Conversation not found: {conversation_id}. Aborting."
                    )
                    return f"Conversation not found: {conversation_id}"
                if not agent_config_db_model:
                    logger.warning(
                        f"{log_prefix} No active BotAgent configuration found for inbox {conversation.inbox_id}. Skipping AI reply."
                    )
                    return f"No BotAgent for inbox {conversation.inbox_id}"
                # History can be empty for the first message, but graph should handle it.
                # if not history_db and not is_follow_up_trigger: # Allow follow-up on empty history if logic supports
                #     logger.warning(f"{log_prefix} No message history found for conversation {conversation_id}. Skipping AI reply unless it's a follow-up.")
                #     # Depending on graph logic, this might be an error or a valid start.
                #     # For now, let the graph decide.

                current_user_input_content: Optional[str] = None
                trigger_event_for_graph: TriggerEventType = "user_message"
                if is_follow_up_trigger:
                    trigger_event_for_graph = "follow_up_timeout"
                    logger.info(f"{log_prefix} Event type set to FOLLOW_UP_TIMEOUT.")
                elif user_input_content:
                    current_user_input_content = user_input_content

                    if (
                        current_user_input_content.lower().strip()
                        == settings.RESET_MESSAGE_TRIGGER.lower().strip()
                    ):
                        logger.info(
                            f"{log_prefix} Reset trigger '{settings.RESET_MESSAGE_TRIGGER}' detected. Processing reset."
                        )
                        # For reset, we might want a simpler response rather than full graph invocation.
                        # Or, the graph itself should handle a "reset" intent.
                        # For now, let's assume graph handles it or we send a canned response.
                        # This example sends back the reset command as a simple echo.
                        await _process_one_message(
                            db,
                            account_id,
                            task_id,
                            agent_config_db_model,
                            {},
                            conversation,
                            "Conversa resetada! Mande uma nova mensagem, e inicie uma conversa sem histórico.",
                        )
                        await db.commit()  # Commit this specific action
                        logger.info(
                            f"{log_prefix} Conversation reset processed and committed."
                        )
                        return "Conversation reset processed"
                else:
                    # This case should have been caught by the initial log_prefix logic
                    logger.error(
                        f"{log_prefix} Task triggered without user message or valid follow-up event. Aborting."
                    )
                    return "Invalid trigger: no user message or follow-up event"

                profile_dict = CompanyProfileSchema.model_validate(
                    profile_db
                ).model_dump(mode="json")
                agent_config_dict = agent_config_db_model.model_dump(mode="json")

                current_input: RichConversationState = {
                    "account_id": str(account_id),
                    "conversation_id": str(conversation_id),
                    "bot_agent_id": str(agent_config_db_model.id),
                    "company_profile": profile_dict,
                    "agent_config": agent_config_dict,
                    "messages": (
                        [HumanMessage(content=current_user_input_content)]
                        if current_user_input_content
                        else []
                    ),  # Checkpointer loads historical messages
                    "current_user_input_text": current_user_input_content,
                    "is_simulation": conversation.is_simulation,
                    "last_interaction_timestamp": time.time(),
                    "trigger_event": trigger_event_for_graph,
                    # Fields to be reset or populated by the graph each turn
                    "next_agent_action_command": None,
                    "action_parameters": {},
                    "retrieved_knowledge_for_next_action": None,
                    "last_agent_generation_text": None,
                    "final_agent_message_text": None,
                    "user_input_analysis_result": None,
                    "last_processing_error": None,
                    "conversation_summary_for_llm": None,
                    "disengagement_reason": None,
                    "current_turn_extracted_questions": [],
                }

                if is_follow_up_trigger:
                    current_input["follow_up_attempt_count"] = follow_up_attempt_count

                logger.trace(
                    f"{log_prefix} Current graph input prepared: {json.dumps(current_input, indent=2, default=str)}"
                )

                graph_config = {
                    "configurable": {
                        "thread_id": str(conversation_id),
                        "llm_primary_instance": llm_primary_client,
                        "llm_fast_instance": llm_fast_client,
                        "db_session_factory": db_session_factory,  # Pass the factory
                    }
                }
                logger.debug(
                    f"{log_prefix} Graph config prepared with thread_id: {conversation_id}"
                )

                # Get snapshot of messages from checkpoint *before* invoking with new input
                # This helps identify *new* messages added by the current invocation.
                snapshot_before = await compiled_reply_graph.aget_state(graph_config)
                previous_messages_lc = (
                    snapshot_before.values.get("messages", [])
                    if snapshot_before
                    else []
                )
                # Create a set of IDs from AIMessages that have an 'id' attribute from the checkpoint
                previous_ai_message_ids_in_checkpoint = set()
                if isinstance(previous_messages_lc, list):
                    for msg in previous_messages_lc:
                        if isinstance(msg, AIMessage) and hasattr(msg, "id") and msg.id:
                            previous_ai_message_ids_in_checkpoint.add(str(msg.id))
                logger.debug(
                    f"{log_prefix} Found {len(previous_ai_message_ids_in_checkpoint)} AI message IDs in checkpoint before invocation."
                )

                logger.info(f"{log_prefix} Invoking reply graph...")
                # The graph's `stream` or `invoke` will internally use the checkpointer
                # to load the full state for `thread_id`, merge `current_input`, run, and save.
                final_state_values = await compiled_reply_graph.ainvoke(
                    current_input, config={**graph_config, "recursion_limit": 50}
                )
                # final_state_values is the dict of the RichConversationState
                final_state = RichConversationState(**final_state_values)

                logger.info(f"{log_prefix} Reply graph execution finished.")
                logger.trace(
                    f"{log_prefix} Final graph state: {json.dumps(final_state, indent=2, default=str)}"
                )

                graph_error = final_state.get("last_processing_error")
                final_messages_lc_from_state = final_state.get("messages", [])

                new_ai_messages_to_process: List[AIMessage] = []
                if isinstance(final_messages_lc_from_state, list):
                    for msg_lc in final_messages_lc_from_state:
                        if (
                            isinstance(msg_lc, AIMessage)
                            and hasattr(msg_lc, "id")
                            and msg_lc.id
                        ):
                            if (
                                str(msg_lc.id)
                                not in previous_ai_message_ids_in_checkpoint
                            ):
                                new_ai_messages_to_process.append(msg_lc)
                                logger.debug(
                                    f"{log_prefix} Identified new AI message (ID: {msg_lc.id}, Content: '{str(msg_lc.content)[:50]}...') to process."
                                )
                        elif isinstance(msg_lc, AIMessage) and not hasattr(
                            msg_lc, "id"
                        ):
                            # This case is for AIMessages that might be added by the graph but don't have an ID
                            # (e.g., simple AIMessage(content="...") without metadata).
                            # We might want to process these too, or ensure all graph-generated AIMessages get IDs.
                            # For now, let's assume we only care about those with IDs for deduping.
                            logger.warning(
                                f"{log_prefix} Found AIMessage without an ID in final state: '{str(msg_lc.content)[:50]}...'. It won't be processed by the standard new message logic."
                            )

                if graph_error:
                    logger.error(
                        f"{log_prefix} Graph execution finished with error: {graph_error}"
                    )
                    # Potentially send a fallback message if no AI messages were generated
                    if not new_ai_messages_to_process:
                        await _process_one_message(
                            db,
                            account_id,
                            task_id,
                            agent_config_db_model,
                            final_state,
                            conversation,
                            "I encountered an issue processing your request. Please try again later.",
                        )

                if not new_ai_messages_to_process and not graph_error:
                    logger.warning(
                        f"{log_prefix} Graph finished, but no new AI messages were identified for processing."
                    )
                elif new_ai_messages_to_process:
                    logger.success(
                        f"{log_prefix} Graph generated {len(new_ai_messages_to_process)} new AI message(s) to process."
                    )
                    for ai_msg_lc in new_ai_messages_to_process:
                        if ai_msg_lc.content:  # Ensure there's content
                            await _process_one_message(
                                db=db,
                                account_id=account_id,
                                task_id=task_id,
                                conversation=conversation,
                                agent_config_db=agent_config_db_model,
                                final_state=final_state,  # Pass the whole state
                                ai_response_text=str(ai_msg_lc.content),
                            )
                        else:
                            logger.warning(
                                f"{log_prefix} New AI Message (ID: {ai_msg_lc.id}) has no content. Skipping."
                            )

                # --- Follow-up Scheduling Logic ---
                if final_state.get("follow_up_scheduled") and arq_pool:
                    agent_config_from_state = final_state.get(
                        "agent_config", {}
                    )  # agent_config from the graph state
                    follow_up_delay_seconds = agent_config_from_state.get(
                        "follow_up_timeout_seconds", 1
                    )  # Default 1 second to test
                    next_follow_up_attempt = final_state.get(
                        "follow_up_attempt_count", 0
                    )  # This should be the attempt for the *next* follow-up
                    last_agent_msg_ts = final_state.get(
                        "last_message_from_agent_timestamp", time.time()
                    )

                    logger.info(
                        f"{log_prefix} Scheduling follow-up. Delay: {follow_up_delay_seconds}s, Next Attempt: {next_follow_up_attempt}"
                    )

                    # TODO: parametrize the factor and base_delay_seconds
                    computed_follow_up_delay = calculate_follow_up_delay(
                        attempt_number=(next_follow_up_attempt + 1),
                        base_delay_seconds=60,
                        factor=11,
                    )

                    await arq_pool.enqueue_job(
                        "schedule_conversation_follow_up",  # Name of the task in follow_up_task.py
                        _queue_name=settings.AI_REPLY_QUEUE_NAME,
                        conversation_id=conversation_id,
                        account_id=account_id,
                        bot_agent_id=(
                            agent_config_db_model.id if agent_config_db_model else None
                        ),
                        follow_up_attempt_count_for_this_job=next_follow_up_attempt,
                        origin_agent_message_timestamp=last_agent_msg_ts,
                        _defer_by=computed_follow_up_delay,  # timedelta(seconds=1),
                    )
                    logger.info(
                        f"{log_prefix} Enqueued 'schedule_conversation_follow_up' to '{settings.AI_REPLY_QUEUE_NAME}' "
                        f"for ConvID {conversation_id}, scheduled in {computed_follow_up_delay}s."
                    )
                else:
                    if not arq_pool:
                        logger.error(
                            f"{log_prefix} Arq pool not available, cannot schedule follow-up."
                        )
                    elif not final_state.get("follow_up_scheduled"):
                        logger.info(
                            f"{log_prefix} Follow-up not scheduled by the graph."
                        )

                await db.commit()  # Commit all DB changes for this task run
                logger.info(
                    f"{log_prefix} Database transaction committed successfully."
                )

    except Exception as e:
        logger.exception(
            f"{log_prefix} Unhandled error processing AI reply request: {e}"
        )
        # Depending on retry policy, ARQ might retry.
        # If a db session was active and an error occurred, it should be rolled back by context manager exit.
        # Consider if specific errors should lead to specific return values or re-queueing strategies.
        raise  # Re-raise to let ARQ handle it (e.g., move to dead-letter queue or retry)

    finally:
        logger.info(f"{log_prefix} Task finished.")
        # DB session is closed automatically by `async with db_session_factory() as db:`
        # Checkpointer is closed automatically by `async with AsyncPostgresSaver.from_conn_string(...) as checkpointer:`

    return f"Processed AI reply request for conversation {conversation_id}"
