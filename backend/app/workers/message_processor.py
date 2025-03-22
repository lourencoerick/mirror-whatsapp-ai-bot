import time
from typing import Optional, Dict
from loguru import logger
from dotenv import load_dotenv

from app.services.queue.redis_queue import RedisQueue

load_dotenv()


class MessageProcessor:
    def __init__(
        self,
        input_queue_name: str = "message_queue",
        output_queue_name: str = "response_queue",
    ):
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageProcessor:init] Initialized")

    def process_message(self, message: Dict) -> Optional[Dict]:
        """
        Process a parsed WhatsApp message and return a response.
        """
        try:
            content = message.get("content")
            contact_id = message.get("contact_id")
            source_id = message.get("source_id")

            if not all([content, contact_id, source_id]):
                logger.warning("[MessageProcessor:process] Missing required fields")
                return None

            return {
                "to": contact_id,
                "original_message_id": source_id,
                "response_text": f"🤖 Auto-reply: '{content}'",
                "timestamp": time.time(),
            }

        except Exception:
            logger.exception("[MessageProcessor:process] Unexpected failure")
            return None

    def run(self):
        """
        Blocking main loop: waits for new message, processes it, and enqueues response.
        """
        logger.info("[MessageProcessor:run] Starting main loop")

        while True:
            try:
                logger.debug("[queue] Waiting for message...")
                raw = self.input_queue.dequeue()

                if not raw:
                    logger.debug("[queue] Empty queue slot")
                    continue

                logger.debug(f"[queue] Message dequeued: {raw}")
                response = self.process_message(raw)

                if response:
                    self.output_queue.enqueue(response)
                    logger.debug(f"[queue] Response enqueued: {response}")
                else:
                    logger.warning("[MessageProcessor:run] Skipped invalid message")

            except Exception:
                logger.exception("[MessageProcessor:run] Fatal error in main loop")


if __name__ == "__main__":
    MessageProcessor().run()
