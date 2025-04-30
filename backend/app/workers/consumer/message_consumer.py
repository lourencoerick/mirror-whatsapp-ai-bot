# backend/app/workers/message_consumer.py

import asyncio
import json
import time
from typing import Optional, Union, Dict, Any
from uuid import UUID
from loguru import logger
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

# --- DB Imports ---
from app.database import AsyncSessionLocal

# --- Repository Imports ---
from app.services.repository import message as message_repo
from app.services.repository import conversation as conversation_repo

# --- Queue Imports ---
from app.services.queue.redis_queue import RedisQueue

# --- Importar Arq ---
from arq.connections import ArqRedis, Job
from redis.exceptions import (
    ConnectionError as ArqConnectionError,
    TimeoutError as EnqueueTimeout,
)
from app.core.arq_manager import (
    get_arq_pool,
    init_arq_pool,
    close_arq_pool,
)  #


# --- Schema & Model Imports ---
from app.api.schemas.message import MessageCreate
from app.models.conversation import ConversationStatusEnum, Conversation
from app.models.message import Message

# --- Helper Imports ---
from app.services.helper.conversation import (
    update_last_message_snapshot,
    parse_conversation_to_conversation_response,
)
from app.services.helper.websocket import (
    publish_to_conversation_ws,
    publish_to_account_conversations_ws,
)


# --- Configuration ---
MESSAGE_QUEUE_NAME = "message_queue"
AI_REPLY_TASK_NAME = "handle_ai_reply_request"
AI_REPLY_QUEUE_NAME = settings.AI_REPLY_QUEUE_NAME


class MessageConsumer:
    """
    Message consumer to process messages from the input queue, save them,
    update conversation state, publish WS events, and enqueue tasks
    for the AI Replier Arq worker.
    """

    def __init__(
        self,
        input_queue_name: str = MESSAGE_QUEUE_NAME,
    ):
        """
        Initializes the consumer with the input queue.
        Arq pool will be initialized in run method.

        Args:
            input_queue_name (str): Name of the input queue (RedisQueue).
        """
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.arq_pool: Optional[ArqRedis] = None
        logger.info(
            f"[MessageConsumer:init] Initialized input queue: '{input_queue_name}'"
        )

    async def run(self):
        """
        Runs the message consumer loop. Initializes Arq pool.
        """
        logger.info("[consumer] Starting message consumer...")

        logger.info("[consumer] Initializing ARQ Redis pool...")
        try:
            await init_arq_pool()
            self.arq_pool = await get_arq_pool()
            if not self.arq_pool:
                raise ValueError("Failed to get ARQ pool after initialization.")
            logger.info("[consumer] ARQ Redis pool initialized.")
        except Exception as pool_err:
            logger.critical(
                f"[consumer] Could not initialize ARQ Redis pool: {pool_err}. Exiting."
            )
            return

        logger.info("[consumer] Connecting to input Redis queue...")
        await self.input_queue.connect()
        if not self.input_queue.is_connected:
            logger.critical(
                "[consumer] Could not connect to input Redis queue. Exiting."
            )
            await close_arq_pool()
            return

        logger.info("[consumer] Connections established. Listening for messages...")
        while True:
            ai_task_to_enqueue: Optional[Dict[str, Any]] = None
            try:
                raw_message: Optional[Union[str, dict]] = (
                    await self.input_queue.dequeue()
                )
                if not raw_message:
                    await asyncio.sleep(0.1)
                    continue

                logger.debug(f"[consumer] Raw message dequeued: {raw_message}")
                data = (
                    raw_message
                    if isinstance(raw_message, dict)
                    else json.loads(raw_message)
                )
                start_time = time.time()

                async with AsyncSessionLocal() as db:
                    try:
                        ai_task_to_enqueue = await self._handle_message(db, data)
                        await db.commit()
                        logger.debug("[consumer] Database transaction committed.")
                    except Exception as e:
                        logger.error(
                            f"[consumer] Rolling back transaction due to error: {e}"
                        )
                        await db.rollback()
                        raise

                if ai_task_to_enqueue:
                    if not self.arq_pool:
                        logger.error(
                            "[consumer] CRITICAL: Arq Pool not available for enqueueing AI task AFTER DB commit."
                        )
                    else:
                        try:
                            await self.arq_pool.enqueue_job(
                                AI_REPLY_TASK_NAME,
                                _queue_name=AI_REPLY_QUEUE_NAME,
                                **ai_task_to_enqueue,
                            )
                            logger.info(
                                f"[consumer] Enqueued task via Arq for AI Replier: {ai_task_to_enqueue}"
                            )
                        except (ArqConnectionError, EnqueueTimeout) as q_err:
                            logger.exception(
                                f"[consumer] CRITICAL: Arq enqueue error AFTER DB commit. Payload: {ai_task_to_enqueue}. Error: {q_err}"
                            )
                        except Exception as enqueue_err:
                            logger.exception(
                                f"[consumer] CRITICAL: Unexpected Arq enqueue error AFTER DB commit. Payload: {ai_task_to_enqueue}. Error: {enqueue_err}"
                            )

                elapsed = time.time() - start_time
                logger.debug(f"[consumer] Processed message in {elapsed:.2f}s")

            except json.JSONDecodeError:
                logger.warning("[consumer] Received malformed JSON.")
            except Exception as e:
                logger.exception(
                    f"[consumer] Unexpected failure processing message loop: {type(e).__name__} - {e}"
                )
                await asyncio.sleep(1)

        # logger.info("[consumer] Shutting down...")
        # await close_arq_pool()
        # await self.input_queue.disconnect()

    async def _handle_message(
        self, db: AsyncSession, data: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Processes message, saves, updates state, publishes WS events.
        Returns dict with args for AI task if applicable, otherwise None.
        """
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            return None

        message = await message_repo.get_or_create_message(
            db=db, message_data=message_data
        )
        if not message:
            logger.warning("[consumer] Failed to get or create message.")
            return None

        conversation = await conversation_repo.find_conversation_by_id(
            db=db,
            conversation_id=message.conversation_id,
            account_id=message.account_id,
        )
        if not conversation:
            logger.warning(
                f"[consumer] Conversation not found: {message.conversation_id}."
            )
            return None

        logger.info(f"[consumer] Message logged: {message.id}. Processing updates.")
        final_updated_conversation: Optional[Conversation] = None
        if message.direction == "in":
            updated_conv_increment = (
                await conversation_repo.increment_conversation_unread_count(
                    db=db,
                    account_id=conversation.account_id,
                    conversation_id=conversation.id,
                )
            )
            final_updated_conversation = updated_conv_increment or conversation
            if conversation.status == ConversationStatusEnum.CLOSED:
                inbox = conversation.inbox
                if inbox:
                    updated_conv_status = (
                        await conversation_repo.update_conversation_status(
                            db=db,
                            account_id=conversation.account_id,
                            conversation_id=conversation.id,
                            new_status=inbox.initial_conversation_status,
                        )
                    )
                    if updated_conv_status:
                        final_updated_conversation = updated_conv_status
        else:
            final_updated_conversation = conversation
        if not final_updated_conversation:
            raise Exception(
                f"Conversation object lost during updates for {conversation.id}"
            )
        await update_last_message_snapshot(
            db=db, conversation=final_updated_conversation, message=message
        )

        # --- WebSocket Publishing ---
        try:
            await publish_to_conversation_ws(
                conversation_id=message.conversation_id,
                data={"type": "incoming_message", "payload": jsonable_encoder(message)},
            )
        except Exception as e:
            logger.warning(f"[ws] Failed to publish message {message.id}: {e}")
        try:
            parsed_conversation = parse_conversation_to_conversation_response(
                final_updated_conversation
            )
            await publish_to_account_conversations_ws(
                final_updated_conversation.account_id,
                {
                    "type": "conversation_updated",
                    "payload": jsonable_encoder(parsed_conversation),
                },
            )
            logger.debug(
                f"[ws] Published conversation_updated for {final_updated_conversation.id}"
            )
        except Exception as e:
            logger.warning(
                f"[ws] Failed to publish conversation update for {final_updated_conversation.id}: {e}"
            )
        # --- End WebSocket Publishing ---

        if (
            message.direction == "in"
            and message.content
            and final_updated_conversation.status == ConversationStatusEnum.BOT
        ):
            ai_task_args = {
                "account_id": message.account_id,
                "conversation_id": message.conversation_id,
                "trigger_message_id": message.id,
            }
            logger.debug(
                f"Message {message.id} eligible for AI reply. Returning args: {ai_task_args}"
            )
            return ai_task_args
        else:
            logger.debug(f"Message {message.id} not eligible for AI reply.")
            return None


async def main():
    consumer = MessageConsumer()
    await consumer.run()


if __name__ == "__main__":
    try:
        logger.info("Starting Message Consumer...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Message Consumer stopped by user.")
    finally:
        logger.info("Message Consumer finished.")
