import json
from loguru import logger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.queue.redis_queue import RedisQueue
from app.services.sender.evolution import send_message as evolution_send_message
from app.services.repository import message as message_repo
import httpx


class ResponseSender:
    """
    Background worker responsible for sending messages to external providers (e.g., Evolution).
    It listens to the `ready_for_sending_queue`, fetches the message by ID, and attempts delivery.
    """

    def __init__(self, queue_name: str = "response_queue"):
        """
        Initializes the Redis queue listener.

        Args:
            queue_name (str): The name of the Redis queue to consume from.
        """
        self.queue = RedisQueue(queue_name=queue_name)
        logger.info(f"[sender:init] ResponseSender initialized queue: {queue_name}")

    def _process_one_message(self):
        """
        Processes one message from the queue: fetches the ID, looks up the message,
        and attempts delivery to the external provider.
        """
        try:
            payload = self.queue.dequeue()
            if not payload:
                return

            logger.debug(f"[sender] Raw data dequeued: {payload}")

            message_id = payload.get("message_id")
            if not message_id:
                logger.warning("[sender] Payload missing 'message_id'")
                return

            with SessionLocal() as db:
                self._handle_message(db, message_id)
                db.commit()

        except Exception as e:
            logger.exception(f"[sender] Unexpected failure: {type(e).__name__} - {e}")

    def run(self):
        """
        Starts the infinite loop to consume and process messages from the queue.
        """
        logger.info("[sender] Listening for messages to send...")

        while True:
            self._process_one_message()

    def _handle_message(self, db: Session, message_id: int):
        """
        Handles delivery of a specific message by ID.

        Args:
            db (Session): Active SQLAlchemy database session.
            message_id (int): The ID of the message to be delivered.
        """
        message = message_repo.find_by_id(db, message_id)
        if not message:
            logger.warning(f"[sender] Message ID {message_id} not found in database")
            return

        try:
            response = evolution_send_message(message)
            external_id = response.get("key", {}).get("id")
            status = response.get("status", "pending").lower()
            if external_id:
                message.source_id = external_id
            message.status = status

            logger.info(
                f"[sender] Message {message.id} delivered successfully "
                f"(external_id={external_id}, status={status})"
                f"response: {response}"
            )

        except httpx.HTTPError as e:
            message.status = "failed"
            logger.warning(f"[sender] HTTP error for message {message.id}: {e}")
        except Exception as e:
            message.status = "failed"
            logger.exception(f"[sender] Unexpected error for message {message.id}: {e}")


if __name__ == "__main__":
    ResponseSender().run()
