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
    Message consumer to process messages from the input queue and enqueue to output queue.
    """

    def __init__(
        self,
        input_queue_name: str = "message_queue",
        output_queue_name: str = "ready_for_processing_queue",
    ):
        """init

        Args:
            input_queue_name (str, optional): input_queue_name. Defaults to "message_queue".
            output_queue_name (str, optional): output_queue_name. Defaults to "ready_for_processing_queue".
        """
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageConsumer:init] Initialized")

    async def run(self):
        """
        Runs the message consumer in an infinite loop.
        """
        logger.info("[consumer] Starting message consumer...")

        while True:
            try:
                raw_message: Optional[Union[str, dict]] = await asyncio.to_thread(
                    self.input_queue.dequeue
                )
                if not raw_message:
                    await asyncio.sleep(0.1)  # avoid busy-waiting
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
                        await asyncio.to_thread(self.output_queue.enqueue, raw_message)
                        logger.debug(
                            f"[consumer] Enqueue raw_message in output_queue {raw_message}s"
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
        """handle messages

        Args:
            db (AsyncSession): db
            data (dict): data
        """
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            return

        message = await message_repo.get_or_create_message(
            db=db, message_data=message_data
        )

        await db.refresh(message, attribute_names=["contact"])

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
                    f"[ws] Failed to publish message {message.id} to Redis: {e}"
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
                    f"[ws] Failed to publish message {message.id} to Redis: {e}"
                )

        else:
            logger.warning("[consumer] Failed to save message")


async def main():
    """main function"""
    consumer = MessageConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
