import json
import time
from typing import Optional, Union
from loguru import logger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.repository.message import get_or_create_message
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message_schema import MessageCreate


class MessageConsumer:
    def __init__(
        self,
        input_queue_name: str = "message_queue",
        output_queue_name: str = "ready_for_processing_queue",
    ):
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageConsumer:init] Initialized")

    def run(self):
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
                    self._handle_message(db, data)
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

    def _handle_message(self, db: Session, data: dict):
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            return

        saved = get_or_create_message(db=db, message_data=message_data)
        if saved:
            logger.info(f"[consumer] Message logged successfully: {saved.id}")
        else:
            logger.warning("[consumer] Failed to save message")
