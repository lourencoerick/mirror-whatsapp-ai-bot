import json
import time
from typing import Optional
from loguru import logger
from dotenv import load_dotenv
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.response_message import ResponseMessage

load_dotenv()


class MessageProcessor:
    def __init__(
        self,
        input_queue_name: str = "ready_for_processing_queue",
        output_queue_name: str = "response_queue",
    ):
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[processor:init] Initialized")

    def process_message(self, message: ResponseMessage) -> Optional[ResponseMessage]:
        try:
            if not all([message.text, message.number, message.original_message_id]):
                logger.warning("[processor:process] Missing required fields")
                return None

            return ResponseMessage(
                to=message.number,
                original_message_id=message.original_message_id,
                response_text=f"🤖 Auto-reply: '{message.text}'",
                provider=message.provider,
                timestamp=time.time(),
            )

        except Exception:
            logger.exception("[processor:process] Unexpected failure")
            return None

    def run(self):
        logger.info("[processor:run] Starting main loop")

        while True:
            try:
                logger.debug("[queue] Waiting for message...")
                raw = self.input_queue.dequeue()

                if not raw:
                    logger.debug("[queue] Empty queue slot")
                    continue

                logger.debug(f"[queue] Message dequeued: {raw}")

                try:
                    parsed = ResponseMessage.model_validate_json(raw)
                except Exception as e:
                    logger.warning(f"[processor:parse] Invalid message format: {e}")
                    continue

                response = self.process_message(parsed)

                if response:
                    self.output_queue.enqueue(response.model_dump_json())
                    logger.debug(f"[queue] Response enqueued: {response}")
                else:
                    logger.warning("[processor:run] Skipped invalid message")

            except Exception:
                logger.exception("[processor:run] Fatal error in main loop")


if __name__ == "__main__":
    MessageProcessor().run()
