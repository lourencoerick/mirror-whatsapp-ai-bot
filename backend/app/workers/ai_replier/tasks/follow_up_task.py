# backend/app/tasks/follow_up_task.py

import os
import time  # For potential future use, not directly used in current logic
from uuid import UUID, uuid4
from typing import Optional, Dict, Any
from loguru import logger

# --- LangGraph Checkpointer ---
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

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
    from app.services.new_agent.state_definition import (
        RichConversationState,
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
        serializer = JsonPlusSerializer()
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
            current_convo_state: RichConversationState = checkpoint.get(
                "channel_values", {}
            )

            if not current_convo_state.get("follow_up_scheduled"):
                logger.info(
                    f"{log_prefix} Follow-up was cancelled or completed (flag 'follow_up_scheduled' is false in state). Discarding task."
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
                    f"{log_prefix} Conversation has progressed since this follow-up was scheduled. "
                    f"(State TS: {current_last_agent_msg_ts_in_state} > Origin TS: {origin_agent_message_timestamp}). "
                    f"This follow-up is stale. Discarding task."
                )
                return f"Follow-up stale (timestamp) for {conversation_id_str}"

            # If all checks pass, enqueue the main AI reply handler task with a follow-up event
            payload_for_ai_replier = {
                "account_id": account_id,
                "conversation_id": conversation_id,
                "bot_agent_id": bot_agent_id,  # Pass it along
                "event_type": "follow_up_timeout",  # Critical: informs the AI handler
                "follow_up_attempt_count": follow_up_attempt_count_for_this_job,
                # trigger_message_id is intentionally None for follow-ups
            }

            logger.info(
                f"{log_prefix} Follow-up conditions met. Enqueuing 'handle_ai_reply_request' to '{settings.AI_REPLY_QUEUE_NAME}'."
            )
            await arq_write_pool.enqueue_job(
                "handle_ai_reply_request",  # The main task in message_handler_task.py
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

    # No finally block needed for checkpointer as it's an async context manager
    # ARQ pool is managed by the worker, not closed here.
