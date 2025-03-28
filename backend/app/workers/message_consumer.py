import json
import time
from typing import Optional, Union
from loguru import logger
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.database import SessionLocal
from app.services.repository.message import get_or_create_message
from app.services.repository.conversation import find_by_id as conversation_find_by_id
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message import MessageCreate
from app.services.helper.conversation import update_last_message_snapshot
from app.services.helper.websocket import (
    publish_to_conversation_ws,
    publish_to_account_conversations_ws,
)


class MessageConsumer:
    def __init__(
        self,
        input_queue_name: str = "message_queue",
        output_queue_name: str = "ready_for_processing_queue",
    ):
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageConsumer:init] Initialized")

    async def run(self):
        logger.info("[consumer] Starting message consumer...")

        while True:
            try:
                raw_message: Optional[Union[str, dict]] = self.input_queue.dequeue()
                if not raw_message:
                    continue

                logger.debug(f"[consumer] Raw message dequeued: {raw_message}")
                data = (
                    raw_message
                    if isinstance(raw_message, dict)
                    else json.loads(raw_message)
                )

                start_time = time.time()
                db: Session = SessionLocal()
                try:
                    await self._handle_message(db, data)
                    db.commit()
                    self.output_queue.enqueue(raw_message)
                    logger.debug(
                        f"[consumer] Enqueue raw_message in output_queue {raw_message}s"
                    )
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()

                elapsed = time.time() - start_time
                logger.debug(f"[consumer] Processed in {elapsed:.2f}s")

            except json.JSONDecodeError:
                logger.warning("[consumer] Received malformed JSON.")
            except Exception as e:
                logger.exception(
                    f"[consumer] Unexpected failure: {type(e).__name__} - {e}"
                )

    async def _handle_message(self, db: Session, data: dict):
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            return

        message = get_or_create_message(db=db, message_data=message_data)

        if message:
            conversation = conversation_find_by_id(
                db=db, conversation_id=message.conversation_id
            )

            if conversation:
                update_last_message_snapshot(
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
                        "message": jsonable_encoder(message),
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
                        "conversation": jsonable_encoder(conversation),
                    },
                )
            except Exception as e:
                logger.warning(
                    f"[ws] Failed to publish message {message.id} to Redis: {e}"
                )

        else:
            logger.warning("[consumer] Failed to save message")


if __name__ == "__main__":
    import asyncio

    consumer = MessageConsumer()
    asyncio.run(consumer.run())
