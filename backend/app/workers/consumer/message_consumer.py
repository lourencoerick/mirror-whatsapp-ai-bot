# backend/app/workers/message_consumer.py

import asyncio
import json
import time

from typing import Optional, Union, Dict, Any
from uuid import UUID
from loguru import logger
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.repository import message as message_repo
from app.services.repository import conversation as conversation_repo
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message import MessageCreate
from app.services.helper.conversation import (
    update_last_message_snapshot,
    parse_conversation_to_conversation_response,
)
from app.services.helper.websocket import (
    publish_to_conversation_ws,
    publish_to_account_conversations_ws,
)
from app.models.conversation import ConversationStatusEnum, Conversation
from app.models.message import Message

# --- Configuration ---
MESSAGE_QUEUE_NAME = "message_queue"
AI_REPLY_QUEUE_NAME = "ai_reply_queue"


class MessageConsumer:
    """
    Message consumer to process messages from the input queue, save them,
    update conversation state, publish WS events, and enqueue tasks
    for the AI Replier.
    """

    def __init__(
        self,
        input_queue_name: str = MESSAGE_QUEUE_NAME,
        output_queue_name: str = AI_REPLY_QUEUE_NAME,
    ):
        """
        Initializes the consumer with input and output queues.

        Args:
            input_queue_name (str): Name of the input queue.
            output_queue_name (str): Name of the output queue for AI tasks.
        """
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        # MODIFIED: Log message updated for clarity
        logger.info(
            f"[MessageConsumer:init] Initialized queues: input='{input_queue_name}', output='{output_queue_name}'"
        )

    async def run(self):
        """
        Runs the message consumer in an infinite loop.
        Waits until the Redis connections are established before starting message processing.
        """
        logger.info("[consumer] Starting message consumer...")

        logger.info("[consumer] Attempting to connect to Redis queues...")
        # Ensure connections are attempted before the loop
        await self.input_queue.connect()
        await self.output_queue.connect()

        retry_delay = 5
        max_retries = 5
        retries = 0
        while (
            not (self.input_queue.is_connected and self.output_queue.is_connected)
            and retries < max_retries
        ):
            retries += 1
            logger.warning(
                f"[consumer] Failed initial Redis connection (Input: {self.input_queue.is_connected}, Output: {self.output_queue.is_connected}). "
                f"Retrying attempt {retries}/{max_retries} in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            if not self.input_queue.is_connected:
                await self.input_queue.connect()
            if not self.output_queue.is_connected:
                await self.output_queue.connect()

        if not (self.input_queue.is_connected and self.output_queue.is_connected):
            logger.error(
                "[consumer] Could not establish Redis connections after multiple attempts. Exiting."
            )
            return

        logger.info(
            "[consumer] Redis connections established. Listening for messages..."
        )
        while True:
            ai_task_payload: Optional[Dict[str, Any]] = None
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
                        ai_task_ids = await self._handle_message(db, data)

                        await db.commit()
                        logger.debug("[consumer] Database transaction committed.")

                        if ai_task_ids:
                            ai_task_payload = {
                                "message_id": str(ai_task_ids["message_id"]),
                                "conversation_id": str(ai_task_ids["conversation_id"]),
                                "account_id": str(ai_task_ids["account_id"]),
                            }

                    except Exception as e:
                        logger.error(
                            f"[consumer] Rolling back transaction due to error: {e}"
                        )
                        await db.rollback()
                        raise

                if ai_task_payload:
                    try:
                        await self.output_queue.enqueue(ai_task_payload)
                        logger.info(
                            f"[consumer] Enqueued task for AI Replier: {ai_task_payload}"
                        )
                    except Exception as enqueue_err:
                        logger.exception(
                            f"[consumer] CRITICAL: Failed to enqueue task to '{self.output_queue.queue_name}' AFTER DB commit. Payload: {ai_task_payload}. Error: {enqueue_err}"
                        )

                elapsed = time.time() - start_time
                logger.debug(f"[consumer] Processed message in {elapsed:.2f}s")

            except json.JSONDecodeError:
                logger.warning("[consumer] Received malformed JSON.")
            except Exception as e:
                logger.exception(
                    f"[consumer] Unexpected failure processing message: {type(e).__name__} - {e}"
                )
                await asyncio.sleep(1)

    async def _handle_message(
        self, db: AsyncSession, data: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Processes the message, saves it, updates conversation state, publishes updates,
        and returns necessary IDs for the AI task payload upon success.

        Args:
            db (AsyncSession): Database session.
            data (dict): Message data.

        Returns:
            A dictionary containing 'message_id', 'conversation_id', 'account_id'
            if the message should be processed by AI, otherwise None.

        Raises:
            Exception: Propagates exceptions to allow for transaction rollback.
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
            logger.warning("[consumer] Failed to get or create message, skipping.")
            return None

        conversation = await conversation_repo.find_conversation_by_id(
            db=db,
            conversation_id=message.conversation_id,
            account_id=message.account_id,
        )
        if not conversation:
            logger.warning(
                f"[consumer] Conversation not found: {message.conversation_id}. Skipping AI task."
            )
            return None

        logger.info(
            f"[consumer] Message logged successfully: {message.id}. Processing conversation updates."
        )
        final_updated_conversation: Optional[Conversation] = None
        if message.direction == "in":
            updated_conv_increment = (
                await conversation_repo.increment_conversation_unread_count(
                    db=db,
                    account_id=conversation.account_id,
                    conversation_id=conversation.id,
                )
            )
            if updated_conv_increment:
                final_updated_conversation = updated_conv_increment
            else:
                final_updated_conversation = conversation

            if conversation.status == ConversationStatusEnum.CLOSED:
                inbox = conversation.inbox

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
            logger.error(
                f"Conversation object became None after updates for {conversation.id}."
            )
            raise Exception(
                f"Conversation object lost during updates for {conversation.id}"
            )

        await update_last_message_snapshot(
            db=db, conversation=final_updated_conversation, message=message
        )
        # --- End Conversation Updates ---

        # --- WebSocket Publishing (logic remains the same) ---
        try:
            await publish_to_conversation_ws(
                conversation_id=message.conversation_id,
                data={"type": "incoming_message", "payload": jsonable_encoder(message)},
            )
        except Exception as e:
            logger.warning(
                f"[ws] Failed to publish message {message.id} to conversation websocket: {e}"
            )
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
                f"[ws] Failed to publish conversation update for {final_updated_conversation.id} to account websocket: {e}"
            )
        # --- End WebSocket Publishing ---

        # Only return IDs if it's an incoming message suitable for AI reply
        if (
            message.direction == "in"
            and message.content
            and final_updated_conversation.status == ConversationStatusEnum.BOT
        ):
            ai_task_ids = {
                "message_id": message.id,
                "conversation_id": message.conversation_id,
                "account_id": message.account_id,
            }
            logger.debug(
                f"Message {message.id} is eligible for AI reply. Returning IDs."
            )
            return ai_task_ids
        else:
            logger.debug(
                f"Message {message.id} is not eligible for AI reply (direction='{message.direction}', has_content={bool(message.content)})."
            )
            return None


# --- Main execution block (remains the same) ---
async def main():
    """
    Main function to start the message consumer.
    """
    consumer = MessageConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
