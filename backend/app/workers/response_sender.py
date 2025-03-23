import json
from typing import Optional
from loguru import logger
from app.services.queue.redis_queue import RedisQueue
from app.services.sender.whatsapp_sender import send_message as send_whatsapp_message
from app.services.sender.evolution_sender import send_message as send_evolution_message


class ResponseSender:
    """
    Worker responsible for consuming response messages from a Redis queue
    and dispatching them to the appropriate external provider.
    """

    def __init__(self, queue_name: str = "response_queue"):
        """
        Initialize the ResponseSender with a given Redis queue name.

        Args:
            queue_name (str): Name of the Redis queue to consume messages from.
        """
        self.queue = RedisQueue(queue_name=queue_name)
        logger.info("[init] ResponseSender initialized.")

    def _process_one_message(self) -> None:
        """
        Process a single message from the response queue.
        This method is testable in isolation.
        """
        try:
            logger.debug("[queue] Waiting for message...")
            raw_message: Optional[str] = self.queue.dequeue()
            if not raw_message:
                return

            logger.debug(f"[queue] Message dequeued: {raw_message}")
            message = (
                raw_message
                if isinstance(raw_message, dict)
                else json.loads(raw_message)
            )

            provider = message.get("provider")
            if provider == "whatsapp":
                send_whatsapp_message(message)
            elif provider == "evolution":
                logger.debug(f"[worker] sending message to evolution")
                send_evolution_message(message)
            else:
                logger.warning(f"[worker] Unknown provider: {provider}")

        except json.JSONDecodeError:
            logger.warning("[worker] Received malformed JSON.")
        except Exception:
            logger.exception("[worker] Unexpected failure during send.")

    def run(self) -> None:
        """
        Starts the infinite loop that listens for messages from the queue
        and sends them via the appropriate provider.
        """
        logger.info("[worker] ResponseSender main loop started.")

        while True:
            self._process_one_message()


if __name__ == "__main__":
    sender = ResponseSender()
    sender.run()
