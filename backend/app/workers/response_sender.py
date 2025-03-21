from typing import Optional, Dict
from loguru import logger
from dotenv import load_dotenv

from app.services.queue.redis_queue import RedisQueue

# Load environment variables from .env file.
# NOTE: Not currently used in this file, but kept for future configuration (e.g., queue names, API keys).
load_dotenv()


class ResponseSender:
    """
    Worker responsible for sending response messages to the external messaging platform.
    Currently, it simulates the behavior and logs the output.
    """

    def __init__(self, queue_name: str = "response_queue"):
        self.queue = RedisQueue(queue_name=queue_name)
        logger.info("[init] ResponseSender initialized.")

    def is_valid_message(self, message: Dict) -> bool:
        """Validate required fields for sending."""
        required_fields = ["to", "response_text"]
        for field in required_fields:
            if field not in message or not message[field]:
                logger.warning(f"[validate] Missing or empty field: {field}")
                return False
        return True

    def send_to_platform(self, message: Dict) -> None:
        """
        Simulates sending a message. Replace with actual API call.
        """
        logger.info(
            f"[send] Sending message to {message['to']}: {message['response_text']}"
        )
        # Future: requests.post(...)

    def run(self) -> None:
        """
        Main loop to consume messages from queue and send them.
        Uses BRPOP under the hood (blocking).
        """
        logger.info("[worker] ResponseSender main loop started.")

        while True:
            try:
                logger.debug("[queue] Waiting for message...")
                message: Optional[Dict] = self.queue.dequeue()
                logger.debug(f"[queue] Message dequeued: {message}")

                if self.is_valid_message(message):
                    self.send_to_platform(message)
                else:
                    logger.warning("[worker] Skipping invalid message.")

            except Exception:
                logger.exception(
                    "[worker:error] Unexpected failure during message send."
                )


if __name__ == "__main__":
    sender = ResponseSender()
    sender.run()
