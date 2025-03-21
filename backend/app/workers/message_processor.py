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
        logger.info("[init] MessageProcessor initialized.")

    def process_message(self, message: Dict) -> Optional[Dict]:
        """
        Given a raw message from the queue, apply business logic
        and return a response payload.
        """
        try:
            text = message.get("text")
            phone_number = message.get("phone_number")
            message_id = message.get("message_id")

            if not all([text, phone_number, message_id]):
                logger.warning("[process] Incomplete message payload")
                return None

            response = {
                "to": phone_number,
                "original_message_id": message_id,
                "response_text": f"Bot: You said '{text}'",
                "timestamp": time.time(),
            }

            return response

        except Exception:
            logger.exception("[process] Failed to generate response")
            return None

    def run(self):
        """
        Main loop: consume, process and enqueue.

        We do not use sleep here because BRPOP is a blocking call.
        The process remains idle until a message is available.
        """
        logger.info("[worker] Starting main loop...")

        while True:
            try:
                logger.debug("[queue] Waiting for message...")
                message = self.input_queue.dequeue()
                logger.debug(f"[queue] Message dequeued: {message}")

                response = self.process_message(message)

                if response:
                    self.output_queue.enqueue(response)
                    logger.debug(f"[queue:response] Response enqueued: {response}")
                else:
                    logger.warning("[worker] Skipped empty or invalid response")

            except Exception:
                logger.exception("[worker:error] Unhandled exception in main loop")


if __name__ == "__main__":
    processor = MessageProcessor()
    processor.run()
