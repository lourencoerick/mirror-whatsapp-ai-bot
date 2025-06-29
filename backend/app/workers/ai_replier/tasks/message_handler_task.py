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
    from app.services.sales_agent.agent_graph import create_react_sales_agent_graph
    from app.services.sales_agent.agent_state import (
        AgentState,
        PendingFollowUpTrigger,
        TriggerEventType,
    )
    from app.services.sales_agent.serializers import JsonOnlySerializer

    GRAPH_AVAILABLE = True
    logger.info("MessageHandlerTask: Successfully imported LangGraph components.")
except ImportError as e:
    logger.error(
        f"MessageHandlerTask: Failed to import LangGraph components: {e}. AI reply limited."
    )
    GRAPH_AVAILABLE = False

    class AgentState(dict):
        pass  # type: ignore

    class TriggerEventType(str):
        pass  # type: ignore

    class JsonOnlySerializer:
        pass  # type: ignore


# --- LangGraph Checkpointer ---
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.managed.is_last_step import RemainingSteps

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

    class RemainingSteps:
        pass  # type: ignore


# --- LangChain Imports ---
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import (
        BaseMessage,
        HumanMessage,
        AIMessage,
        ToolMessage,
        SystemMessage,
    )

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

    class ToolMessage:
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
    from app.models.account import Account
    from app.models.usage_event import UsageEvent

    MODELS_SCHEMAS_AVAILABLE = True
    logger.info(
        "MessageHandlerTask: Successfully imported model and schema components."
    )
except ImportError:
    MODELS_SCHEMAS_AVAILABLE = False
    logger.error(
        "MessageHandlerTask: Models/Schemas unavailable. Data handling impaired."
    )

    class Account:
        pass  # type: ignore

    class UsageEvent:
        pass  # type: ignore

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
from app.services.helper.checkpoint import reset_checkpoint

from app.workers.ai_replier.utils.circuit_breaker import (
    check_and_update_ping_pong_circuit_breaker,
    PingPongLimitExceeded,
)
from app.models.conversation import ConversationStatusEnum

# --- Configuration Constants ---
CONVERSATION_HISTORY_LIMIT = 20
METER_EVENT_NAME_AI_MESSAGE = "generated_ia_messages"

# ==============================================================================
# Helper Functions
# ==============================================================================


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

    final_state = dict(final_state)
    current_utc_time = datetime.now(timezone.utc)

    message_data = MessageCreate(
        account_id=account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=contact_id,
        source_id=internal_source_id,
        bot_agent_id=agent_config_db.id,
        direction="out",
        status="processing",
        message_timestamp=current_utc_time,
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
    await db.flush()
    await db.refresh(ai_message)
    logger.info(
        f"{log_prefix} Created outgoing AI message record (ID: {ai_message.id})."
    )

    if not conversation.is_simulation:
        account_for_usage = await db.get(Account, account_id)

        if account_for_usage and account_for_usage.stripe_customer_id:
            usage_event = UsageEvent(
                account_id=account_id,
                stripe_customer_id=account_for_usage.stripe_customer_id,
                meter_event_name=METER_EVENT_NAME_AI_MESSAGE,
                quantity=1,
                event_timestamp=current_utc_time,
            )
            db.add(usage_event)
            logger.info(
                f"{log_prefix} UsageEvent for 1 '{METER_EVENT_NAME_AI_MESSAGE}' prepared for DB (Account: {account_id})."
            )
        elif not account_for_usage:
            logger.error(
                f"{log_prefix} Account {account_id} not found. Cannot determine stripe_customer_id for usage event."
            )
        else:
            logger.warning(
                f"{log_prefix} Account {account_id} does not have a stripe_customer_id. "
                f"Usage for '{METER_EVENT_NAME_AI_MESSAGE}' will not be reported to Stripe."
            )
    else:
        logger.info(
            f"{log_prefix} Skipping usage event logging for simulation message."
        )

    if conversation.is_simulation:
        logger.info(
            f"{log_prefix} Publishing simulation message {ai_message.id} via WebSocket."
        )
        try:
            message_payload_ws = jsonable_encoder(ai_message)
            await publish_to_conversation_ws(
                conversation_id=str(conversation.id),
                data={"type": "new_message", "payload": message_payload_ws},
            )
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
    else:
        sender_payload = {"message_id": str(ai_message.id)}
        output_queue = RedisQueue(queue_name=settings.RESPONSE_SENDER_QUEUE_NAME)
        await output_queue.enqueue(sender_payload)
        logger.info(
            f"{log_prefix} Enqueued message {ai_message.id} to '{settings.RESPONSE_SENDER_QUEUE_NAME}'."
        )


# ==============================================================================
# Arq Task Definition: handle_ai_reply_request
# ==============================================================================


async def handle_ai_reply_request(
    ctx: dict,
    account_id: UUID,
    conversation_id: UUID,
    user_input_content: Optional[str] = None,
    event_type: Optional[str] = None,  # e.g., "user_message", "follow_up_timeout"
    trigger_message_id: Optional[UUID] = None,
    follow_up_attempt_count: Optional[int] = 0,
    follow_up_reason_context: Optional[str] = None,
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
    is_integration_trigger = event_type == "integration_trigger"

    if is_follow_up_trigger:
        log_prefix = (
            f"{log_prefix_base}[FollowUpTrigger|Attempt:{follow_up_attempt_count}]"
        )
        logger.info(f"{log_prefix} Starting task for follow-up.")

    elif is_integration_trigger:
        log_prefix = f"{log_prefix_base}[IntegrationTrigger|MsgID:{trigger_message_id}]"
        logger.info(f"{log_prefix} Starting task triggered by integration.")
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
    arq_pool: Optional[ArqRedis] = ctx.get("arq_pool")

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
    final_state: Optional[AgentState] = None
    try:
        serializer = JsonOnlySerializer()

        db_conn_string_pg = str(settings.DATABASE_URL).replace(
            "postgresql+asyncpg://", "postgresql://"
        )

        async with AsyncPostgresSaver.from_conn_string(
            db_conn_string_pg, serde=serializer
        ) as checkpointer:
            logger.debug(
                f"{log_prefix} AsyncPostgresSaver checkpointer context acquired."
            )
            async with db_session_factory() as db:
                logger.debug(f"{log_prefix} Database session acquired.")
                profile_db = await profile_repo.get_profile_by_account_id(
                    db, account_id=account_id
                )
                conversation = await conversation_repo.find_conversation_by_id(
                    db, account_id=account_id, conversation_id=conversation_id
                )

                agent_config_db: Optional[BotAgentRead] = None
                customer_phone: Optional[str] = None
                if conversation and conversation.inbox_id:
                    agent_data_raw = await bot_agent_repo.get_bot_agent_for_inbox(
                        db, inbox_id=conversation.inbox_id, account_id=account_id
                    )
                    if agent_data_raw:
                        agent_config_db = BotAgentRead.model_validate(agent_data_raw)

                    customer_phone = conversation.contact_inbox.contact.phone_number

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
                if not agent_config_db:
                    logger.warning(
                        f"{log_prefix} No active BotAgent configuration found for inbox {conversation.inbox_id}. Skipping AI reply."
                    )
                    return f"No BotAgent for inbox {conversation.inbox_id}"

                try:
                    await check_and_update_ping_pong_circuit_breaker(
                        db=db, conversation=conversation, log_prefix=log_prefix
                    )
                except PingPongLimitExceeded:
                    # A função já logou o aviso e commitou a mudança de status.
                    # Apenas saímos da tarefa de forma limpa.
                    await _process_one_message(
                        db,
                        account_id,
                        task_id,
                        agent_config_db,
                        {},
                        conversation,
                        "Parece que estamos com dificuldades para nos comunicar. Por favor, aguarde um momento enquanto eu conecto você com um de nossos especialistas para continuar a conversa.",
                    )
                    return "Circuit breaker tripped. AI reply aborted."

                compiled_reply_graph = create_react_sales_agent_graph(
                    model=llm_primary_client,
                    company_profile=profile_db,
                    bot_agent=agent_config_db,
                    checkpointer=checkpointer,
                )
                logger.debug(f"{log_prefix} Reply graph compiled with checkpointer.")

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

                current_user_input_content: Optional[str] = None
                current_input_updates: Optional[Dict[str, Any]] = {}
                trigger_event_for_graph: TriggerEventType = "user_message"
                if is_follow_up_trigger:
                    trigger_event_for_graph = "follow_up_timeout"
                    reason_from_payload = (
                        follow_up_reason_context
                        if follow_up_reason_context
                        else "our previous discussion"
                    )

                    follow_up_directive_message = SystemMessage(
                        content=f"""
                        SYSTEM DIRECTIVE:
                        You are a friendly and professional assistant. Your task is to send a follow-up message (Attempt: {follow_up_attempt_count}).

                        YOUR RULES FOR THIS FOLLOW-UP:
                        1.  **FOLLOW THE COMMUNICATION RULES:** you must use the communications rules described on the company profile".
                        2.  **BE PROPORTIONAL:** If the context is just a simple greeting, your follow-up message must be equally simple and short.
                        3.  **BE BRIEF AND INVITING:** Keep the message short, friendly, and aim to re-engage the user to continue the conversation from where it left off.
                        4.  **AVOID REPETITION AND VARY YOUR APPROACH:** Do not repeat phrases from previous turns. Specifically, avoid generic closing questions like "How can I help you today?". Instead, try different re-engagement tactics. For example:
                            - Gently ask if they saw the previous message.
                            - Simply send a friendly check-in.
                            - Briefly reference the last point of the conversation.

                        Your primary goal is to re-engage the user.
                        
                        Craft the ideal follow-up message following all the rules above and regarding {reason_from_payload}.
                        """
                    )
                    current_input_updates["messages"] = [follow_up_directive_message]

                    # Updates for the state for THIS agent turn
                    current_input_updates["pending_follow_up_trigger"] = None
                    current_input_updates["current_sales_stage"] = (
                        "follow_up_in_progress"
                    )
                    # Set the attempt count for the state of THIS turn to what was passed in
                    current_input_updates["follow_up_attempt_count"] = (
                        follow_up_attempt_count
                    )
                    logger.info(
                        f"{log_prefix} Event type FOLLOW_UP_TIMEOUT. Attempt: {follow_up_attempt_count}. Added directive."
                    )

                elif is_integration_trigger:
                    trigger_event_for_graph = "integration_trigger"

                    # 1. Obter o conteúdo da mensagem sintética que criamos
                    #    O user_input_content contém nossa mensagem estruturada
                    synthetic_message_content = user_input_content or ""

                    # 2. Construir a SystemMessage de instrução

                    system_directive_content = (
                        "SYSTEM DIRECTIVE: This is a new conversation initiated by an external integration.\n"
                        "The context below was provided by the system, not the user.\n\n"
                        f"{synthetic_message_content}\n\n"
                        "Your primary goal is to proactively start the conversation based on this context. "
                        "Greet the user by name, introduce yourself and immediately reference their interest or the provided context. "
                        "Seek to connect with the person before presenting any product, service, or appointment opportunity. "
                        "Be concise; our communication is via WhatsApp—people don’t like receiving long messages. "
                        "Use active voice and strong action verbs (e.g., “Quero te mostrar…”). "
                        "Highlight the immediate benefit up front. "
                        "Conclude with a concise follow-up question inviting the user to ask for more details—aim for phrasing similar to “Posso te explicar melhor?”. "
                        "Keep it to at most three short sentences."
                    )

                    integration_directive_message = SystemMessage(
                        content=system_directive_content
                    )

                    current_input_updates["messages"] = [integration_directive_message]
                    current_input_updates["current_user_input_text"] = (
                        None  # Não há input direto do usuário
                    )
                    current_input_updates["pending_follow_up_trigger"] = None
                    current_input_updates["follow_up_attempt_count"] = 0

                    logger.info(
                        f"{log_prefix} Event type INTEGRATION_TRIGGER. Added directive to graph input."
                    )

                elif user_input_content:
                    current_user_input_content = user_input_content

                    human_message = HumanMessage(content=current_user_input_content)
                    current_input_updates["messages"] = [human_message]
                    current_input_updates["current_user_input_text"] = (
                        current_user_input_content
                    )
                    current_input_updates["pending_follow_up_trigger"] = None
                    current_input_updates["follow_up_attempt_count"] = 0

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
                        await reset_checkpoint(db=db, thread_id=str(conversation_id))

                        await _process_one_message(
                            db,
                            account_id,
                            task_id,
                            agent_config_db,
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
                agent_config_dict = agent_config_db.model_dump(mode="json")

                current_input: AgentState = {
                    "account_id": str(account_id),
                    "conversation_id": str(conversation_id),
                    "bot_agent_id": str(agent_config_db.id),
                    "customer_phone": customer_phone,
                    "company_profile": profile_dict,
                    "agent_config": agent_config_dict,
                    "trigger_event": trigger_event_for_graph,
                    "last_processing_error": None,
                    "remaining_steps": RemainingSteps(),
                    **current_input_updates,
                }

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

                final_state = AgentState(**final_state_values)

                logger.info(f"{log_prefix} Reply graph execution finished.")
                logger.trace(
                    f"{log_prefix} Final graph state: {json.dumps(final_state, indent=2, default=str)}"
                )

                graph_error = final_state.last_processing_error
                final_messages_lc_from_state = final_state.messages

                new_ai_messages_to_process: List[AIMessage] = []
                if isinstance(final_messages_lc_from_state, list):
                    for msg_lc in final_messages_lc_from_state:
                        if (
                            isinstance(msg_lc, AIMessage)
                            and hasattr(msg_lc, "id")
                            and not (
                                hasattr(msg_lc, "tool_calls")
                                and len(msg_lc.tool_calls) > 0
                            )  # it is not a tool call
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
                            agent_config_db,
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
                                agent_config_db=agent_config_db,
                                final_state=final_state,  # Pass the whole state
                                ai_response_text=str(ai_msg_lc.content),
                            )
                        else:
                            logger.warning(
                                f"{log_prefix} New AI Message (ID: {ai_msg_lc.id}) has no content. Skipping."
                            )

                # --- Follow-up Scheduling Logic ---
                if final_state.pending_follow_up_trigger and arq_pool:

                    current_pending_trigger: Optional[PendingFollowUpTrigger] = None
                    if isinstance(
                        final_state.pending_follow_up_trigger, PendingFollowUpTrigger
                    ):
                        current_pending_trigger = final_state.pending_follow_up_trigger
                    elif isinstance(final_state.pending_follow_up_trigger, dict):
                        try:
                            current_pending_trigger = (
                                PendingFollowUpTrigger.model_validate(
                                    final_state.pending_follow_up_trigger
                                )
                            )
                        except Exception as e_parse:
                            logger.warning(
                                f"{log_prefix} Could not parse pending_follow_up_trigger dict into object: {e_parse}"
                            )
                            current_pending_trigger = None  # Treat as malformed

                    if current_pending_trigger and hasattr(
                        current_pending_trigger, "due_timestamp"
                    ):
                        due_timestamp: float = current_pending_trigger.due_timestamp
                        current_time: float = time.time()

                        defer_seconds: float = current_pending_trigger.defer_by

                        origin_ts_for_job: float = (
                            final_state.last_agent_message_timestamp or current_time
                        )

                        attempt_count_for_next_follow_up: int = (
                            final_state.follow_up_attempt_count or 0
                        )

                        bot_agent_id_to_schedule: Optional[UUID] = None
                        if final_state.agent_config and final_state.agent_config.id:
                            bot_agent_id_to_schedule = final_state.agent_config.id
                        elif (
                            agent_config_db
                        ):  # Fallback to initially loaded if not in state model
                            bot_agent_id_to_schedule = agent_config_db.id

                        logger.info(
                            f"{log_prefix} Found pending follow-up in final_state. "
                            f"Deferring 'schedule_conversation_follow_up' by {defer_seconds:.2f}s. "
                            f"Attempt for Job: {attempt_count_for_next_follow_up}."
                        )

                        await arq_pool.enqueue_job(
                            "schedule_conversation_follow_up",
                            _queue_name=settings.AI_REPLY_QUEUE_NAME,
                            conversation_id=conversation_id,  # from task args
                            account_id=account_id,  # from task args
                            bot_agent_id=bot_agent_id_to_schedule,
                            follow_up_attempt_count_for_this_job=attempt_count_for_next_follow_up,
                            origin_agent_message_timestamp=origin_ts_for_job,
                            _defer_by=timedelta(seconds=10),
                        )
                        logger.info(
                            f"{log_prefix} Enqueued 'schedule_conversation_follow_up' for ConvID {conversation_id}."
                        )
                    else:
                        logger.warning(
                            f"{log_prefix} 'pending_follow_up_trigger' in final_state is present but malformed, "
                            f"not a valid PendingFollowUpTrigger object/dict, or missing 'due_timestamp'. "
                            f"Trigger data: {final_state.pending_follow_up_trigger}"
                        )
                elif not arq_pool:
                    logger.error(
                        f"{log_prefix} Arq pool not available, cannot schedule any follow-up."
                    )
                elif not final_state.pending_follow_up_trigger:
                    logger.info(
                        f"{log_prefix} No pending follow-up trigger found in final_state. No follow-up will be enqueued."
                    )

                await db.commit()
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
