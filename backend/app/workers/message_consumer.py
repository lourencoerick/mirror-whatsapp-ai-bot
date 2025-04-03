import asyncio
import json
import time
from typing import Optional, Union
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


class MessageConsumer:
    """
    Message consumer to process messages from the input queue and enqueue them to the output queue.
    """

    def __init__(
        self,
        input_queue_name: str = "message_queue",
        output_queue_name: str = "ready_for_processing_queue",
    ):
        """
        Initializes the consumer with input and output queues.

        Args:
            input_queue_name (str): Name of the input queue. Defaults to "message_queue".
            output_queue_name (str): Name of the output queue. Defaults to "ready_for_processing_queue".
        """
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageConsumer:init] Initialized")

    async def run(self):
        """
        Runs the message consumer in an infinite loop.
        Waits until the Redis connections are established before starting message processing.
        """
        logger.info("[consumer] Starting message consumer...")

        logger.info("[consumer] Attempting to connect to Redis queues...")
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

        while True:
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
                        await self._handle_message(db, data)
                        await db.commit()
                        await self.output_queue.enqueue(raw_message)
                        logger.debug(
                            f"[consumer] Enqueued raw_message in output_queue: {raw_message}"
                        )
                    except Exception:
                        await db.rollback()
                        raise
                    finally:
                        await db.close()

                elapsed = time.time() - start_time
                logger.debug(f"[consumer] Processed in {elapsed:.2f}s")

            except json.JSONDecodeError:
                logger.warning("[consumer] Received malformed JSON.")
            except Exception as e:
                logger.exception(
                    f"[consumer] Unexpected failure: {type(e).__name__} - {e}"
                )

    async def _handle_message(self, db: AsyncSession, data: dict):
        """
        Processes the message, saves it to the database, and publishes updates via websocket.

        Args:
            db (AsyncSession): Database session.
            data (dict): Message data.
        """
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            return

        message = await message_repo.get_or_create_message(
            db=db, message_data=message_data
        )

        if message:
            conversation = await conversation_repo.find_conversation_by_id(
                db=db,
                conversation_id=message.conversation_id,
                account_id=message.account_id,
            )

            if conversation:
                await update_last_message_snapshot(
                    db=db, conversation=conversation, message=message
                )
            else:
                logger.warning(
                    f"[consumer] Conversation not found: {message.conversation_id}"
                )

            logger.info(f"[consumer] Message logged successfully: {message.id}")

            try:
                await publish_to_conversation_ws(
                    conversation_id=message.conversation_id,
                    data={
                        "type": "incoming_message",
                        "payload": jsonable_encoder(message),
                    },
                )
            except Exception as e:
                logger.warning(
                    f"[ws] Failed to publish message {message.id} to conversation websocket: {e}"
                )

            try:
                await publish_to_account_conversations_ws(
                    conversation.account_id,
                    {
                        "type": "conversation_updated",
                        "payload": jsonable_encoder(
                            parse_conversation_to_conversation_response(conversation)
                        ),
                    },
                )
            except Exception as e:
                logger.warning(
                    f"[ws] Failed to publish message {message.id} to account conversations websocket: {e}"
                )
        else:
            logger.warning("[consumer] Failed to save message")


async def main():
    """
    Main function to start the message consumer.
    """
    consumer = MessageConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
