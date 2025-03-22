import json
import time
from typing import Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.logging.message_logger import log_message
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message_schema import MessageCreate


class MessageConsumer:
    def __init__(
        self,
        queue_name: str = "message_queue",
        redis_queue: Optional[RedisQueue] = None,
    ):
        self.queue = redis_queue or RedisQueue()
        self.queue_name = queue_name

    def run(self):
        logger.info("[consumer] Starting message consumer...")

        while True:
            try:
                raw = self.queue.dequeue()
                if not raw:
                    continue

                logger.debug(f"[consumer] Raw message dequeued: {raw}")
                data = json.loads(raw)

                start_time = time.time()
                with get_db() as db:
                    self._handle_message(db, data)
                elapsed = time.time() - start_time
                logger.debug(f"[consumer] Processed in {elapsed:.2f}s")

            except json.JSONDecodeError:
                logger.warning("[consumer] Received malformed JSON.")
            except Exception:
                logger.exception(
                    "[consumer] Unexpected failure while processing message"
                )

    def _handle_message(self, db: Session, data: dict):
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            return

        saved = log_message(db=db, **message_data.model_dump())
        if saved:
            logger.info(f"[consumer] Message logged successfully: {saved.id}")
        else:
            logger.warning("[consumer] Failed to save message")
