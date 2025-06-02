# backend/app/tasks/follow_up_task.py

import os
import time  # For potential future use, not directly used in current logic
from uuid import UUID, uuid4
from typing import Optional, Dict, Any
from loguru import logger

# --- LangGraph Checkpointer ---
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    CHECKPOINTER_AVAILABLE = True
    logger.info("FollowUpTask: Successfully imported LangGraph AsyncPostgresSaver.")
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    logger.error(
        "FollowUpTask: Failed to import AsyncPostgresSaver. Follow-up persistence checks disabled."
    )

    class AsyncPostgresSaver:  # type: ignore
        @classmethod
        def from_conn_string(cls, *args, **kwargs):
            class DummyCheckpointer:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    pass

                async def aget(self, *args, **kwargs):
                    return None

            return DummyCheckpointer()

    class JsonPlusSerializer:
        pass  # type: ignore


# --- Project Imports ---
try:
    from arq.connections import ArqRedis  # For type hinting ctx['arq_pool']
    from app.config import get_settings  # Use the centralized settings
    from app.services.sales_agent.agent_state import (
        AgentState,
        PendingFollowUpTrigger,
    )  # For type hinting state

    settings = get_settings()
    # AsyncSessionLocal might be needed if checkpointer requires db session factory directly
    from app.database import AsyncSessionLocal

    PROJECT_IMPORTS_AVAILABLE = True
    logger.info("FollowUpTask: Successfully imported project dependencies.")
except ImportError as e:
    logger.error(f"FollowUpTask: Failed to import project dependencies: {e}.")
    PROJECT_IMPORTS_AVAILABLE = False
    ArqRedis = None  # type: ignore
    RichConversationState = dict  # type: ignore
    settings = type(
        "obj",
        (object,),
        {  # Minimal fallback settings
            "DATABASE_URL": None,
            "AI_REPLY_QUEUE_NAME": "ai_reply_queue",
        },
    )()
from app.services.repository import conversation as conversation_repo
from app.models.conversation import ConversationStatusEnum
from app.services.sales_agent.serializers import JsonOnlySerializer


async def schedule_conversation_follow_up(
    ctx: Dict[
        str, Any
    ],  # ARQ context, must contain 'arq_pool' and 'db_session_factory'
    conversation_id: UUID,
    account_id: UUID,
    bot_agent_id: Optional[UUID],
    follow_up_attempt_count_for_this_job: int,
    origin_agent_message_timestamp: float,
    **kwargs,  # To catch any other args ARQ might pass
):
    """
    ARQ task to check if a scheduled follow-up is still valid and, if so,
    trigger the AI reply handler for a follow-up event.

    This task is deferred and runs after a specified timeout. It checks
    the conversation's state to prevent redundant or outdated follow-ups.

    Args:
        ctx: The ARQ context, containing 'arq_pool' and 'db_session_factory'.
        conversation_id: The ID of the conversation for the follow-up.
        account_id: The ID of the account.
        bot_agent_id: The ID of the bot agent associated with the conversation.
        follow_up_attempt_count_for_this_job: The attempt number for this follow-up.
        origin_agent_message_timestamp: Timestamp of the agent message that scheduled
                                         this follow-up, used for staleness check.
        **kwargs: Additional keyword arguments.
    """
    job_id = ctx.get("job_id", f"adhoc-followup-{uuid4().hex[:6]}")
    conversation_id_str = str(conversation_id)
    log_prefix = f"[FollowUpTask:{job_id}|Conv:{conversation_id_str}|Acc:{account_id}|Attempt:{follow_up_attempt_count_for_this_job}]"

    logger.info(f"{log_prefix} Starting follow-up check.")

    if not PROJECT_IMPORTS_AVAILABLE or not CHECKPOINTER_AVAILABLE:
        logger.error(
            f"{log_prefix} Critical project or checkpointer imports missing. Cannot proceed."
        )
        return f"Critical imports missing for follow-up on {conversation_id_str}"

    arq_write_pool: Optional[ArqRedis] = ctx.get("arq_pool")
    # db_session_factory = ctx.get("db_session_factory") # Needed by AsyncPostgresSaver

    if (
        not arq_write_pool
    ):  # Removed db_session_factory check as checkpointer handles its own connection
        logger.error(
            f"{log_prefix} ARQ pool missing in context. Cannot enqueue AI reply task."
        )
        return f"ARQ pool missing for follow-up on {conversation_id_str}"

    try:
        serializer = JsonOnlySerializer()
        # Ensure DATABASE_URL is correctly formatted for AsyncPostgresSaver
        db_conn_string_pg = str(settings.DATABASE_URL).replace(
            "postgresql+asyncpg://", "postgresql://"
        )

        async with AsyncSessionLocal() as db:
            conversation = await conversation_repo.find_conversation_by_id(
                db=db, account_id=account_id, conversation_id=conversation_id
            )
            logger.debug(f"{log_prefix} Checking status of the conversation.")
            if conversation.status != ConversationStatusEnum.BOT:
                logger.debug(
                    f"{log_prefix} Converation is not on the BOT status. Aborting follow-up."
                )
                return

        async with AsyncPostgresSaver.from_conn_string(
            db_conn_string_pg, serde=serializer
        ) as checkpointer:
            logger.debug(
                f"{log_prefix} AsyncPostgresSaver checkpointer context acquired."
            )

            config_load_state = {"configurable": {"thread_id": conversation_id_str}}
            # Fetch the latest checkpoint for the conversation
            # The checkpoint contains the full state, including 'values' which is the RichConversationState
            checkpoint = await checkpointer.aget(config=config_load_state)

            if not checkpoint or not checkpoint.values:
                logger.warning(
                    f"{log_prefix} No state checkpoint found for conversation. Aborting follow-up."
                )
                return f"No state checkpoint for {conversation_id_str}"

            # The actual conversation state is within checkpoint.values
            current_convo_state: Dict[str, Any] = checkpoint.get("channel_values", {})

            pending_trigger_data_from_state: Optional[Dict[str, Any]] = (
                current_convo_state.get("pending_follow_up_trigger")
            )

            if not pending_trigger_data_from_state:
                logger.info(
                    f"{log_prefix} No 'pending_follow_up_trigger' found in current state. Follow-up might have been cancelled or already processed. Discarding task."
                )
                return f"Follow-up trigger not found in state for {conversation_id_str}"

            # --- 2. Validate and Parse the Trigger Data ---
            try:
                # Assuming pending_trigger_data_from_state is a dict from JSON
                current_pending_trigger = PendingFollowUpTrigger.model_validate(
                    pending_trigger_data_from_state
                )
            except Exception as e:
                logger.error(
                    f"{log_prefix} Failed to parse PendingFollowUpTrigger from state: {e}. Data: {pending_trigger_data_from_state}"
                )
                return f"Malformed follow-up trigger data for {conversation_id_str}"

            # if current_pending_trigger.due_timestamp > (
            #     time.time() + 60
            # ):  # Example: if it's more than 60s in the future, something is wrong with scheduling
            #     logger.warning(
            #         f"{log_prefix} Follow-up trigger found, but its due_timestamp ({current_pending_trigger.due_timestamp}) is significantly in the future. Current time: {time.time()}. This might be an issue with ARQ scheduling or a stale trigger. Discarding."
            #     )
            #     return f"Follow-up trigger due time mismatch for {conversation_id_str}"

            # --- 4. Staleness Check: Has the conversation progressed significantly since this follow-up was scheduled? ---
            last_agent_msg_ts_in_state: Optional[float] = current_convo_state.get(
                "last_agent_message_timestamp"
            )

            # The origin_agent_message_timestamp is the timestamp of the agent message
            # that *led to this specific PendingFollowUpTrigger being created*.
            if (
                last_agent_msg_ts_in_state is not None
                and origin_agent_message_timestamp
                is not None  # Ensure origin_ts is not None
                and last_agent_msg_ts_in_state > origin_agent_message_timestamp
            ):
                logger.info(
                    f"{log_prefix} Conversation has progressed since this follow-up was scheduled. "
                    f"(State's LastAgentMsgTS: {last_agent_msg_ts_in_state} > Follow-up's OriginTS: {origin_agent_message_timestamp}). "
                    f"This follow-up is stale. Discarding task."
                )
                return (
                    f"Follow-up stale (timestamp comparison) for {conversation_id_str}"
                )
            # --- All checks passed, prepare to trigger the main AI handler ---
            follow_up_reason_for_handler = current_pending_trigger.context.get(
                "reason", "your previous discussion"
            )
            # The follow_up_attempt_count_for_this_job is the attempt number of the PFT being processed.
            # This was set when this PFT was scheduled.

            payload_for_ai_replier = {
                "account_id": account_id,
                "conversation_id": conversation_id,
                "bot_agent_id": bot_agent_id,  # The bot_agent_id at the time of original scheduling
                "event_type": "follow_up_timeout",
                "follow_up_attempt_count": follow_up_attempt_count_for_this_job,
                "follow_up_reason_context": follow_up_reason_for_handler,  # Pass the reason
            }

            logger.info(
                f"{log_prefix} Follow-up validation passed. Enqueuing 'handle_ai_reply_request'."
            )
            await arq_write_pool.enqueue_job(
                "handle_ai_reply_request",
                _queue_name=settings.AI_REPLY_QUEUE_NAME,
                **payload_for_ai_replier,
            )
            logger.info(
                f"{log_prefix} Successfully enqueued 'handle_ai_reply_request' for follow-up."
            )
            return f"Follow-up notification sent for {conversation_id_str}"

    except Exception as e:
        logger.exception(f"{log_prefix} Error processing follow-up: {e}")
        raise  # Re-raise to let ARQ handle it
