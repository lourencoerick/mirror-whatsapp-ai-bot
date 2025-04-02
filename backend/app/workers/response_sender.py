import asyncio
import httpx
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.queue.redis_queue import RedisQueue
from app.services.sender.evolution import send_message as evolution_send_message
from app.services.repository import message as message_repo


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

    async def _process_one_message(self):
        """
        Processes one message from the queue: fetches the ID, looks up the message,
        and attempts delivery to the external provider.
        """
        try:
            payload = await asyncio.to_thread(self.queue.dequeue)
            if not payload:
                return

            logger.debug(f"[sender] Raw data dequeued: {payload}")

            message_id = payload.get("message_id")
            if not message_id:
                logger.warning("[sender] Payload missing 'message_id'")
                return

            async with get_db() as db:
                await self._handle_message(db, message_id)
                await db.commit()

        except Exception as e:
            logger.exception(f"[sender] Unexpected failure: {type(e).__name__} - {e}")

    async def run(self):
        """
        Starts the infinite loop to consume and process messages from the queue.
        """
        logger.info("[sender] Listening for messages to send...")

        while True:
            await self._process_one_message()
            await asyncio.sleep(0.1)  # Add a small delay to prevent busy-waiting

    async def _handle_message(self, db: AsyncSession, message_id: UUID):
        """
        Handles delivery of a specific message by ID.

        Args:
            db (AsyncSession): Active SQLAlchemy database session.
            message_id (UUID): The ID of the message to be delivered.
        """
        message = await message_repo.find_message_by_id(db, message_id)
        if not message:
            logger.warning(f"[sender] Message ID {message_id} not found in database")
            return

        try:
            response = await evolution_send_message(
                message=message, inbox=message.inbox
            )
            external_id = response.get("key", {}).get("id")
            status = response.get("status", "pending").lower()
            if external_id:
                message.source_id = external_id
            message.status = status

            logger.info(
                f"[sender] Message {message.id} delivered successfully "
                f"(external_id={external_id}, status={status})"
            )

        except httpx.HTTPError as e:
            message.status = "failed"
            logger.warning(f"[sender] HTTP error for message {message.id}: {e}")
        except Exception as e:
            message.status = "failed"
            logger.exception(f"[sender] Unexpected error for message {message.id}: {e}")


async def main():
    """main function"""
    sender = ResponseSender()
    await sender.run()


if __name__ == "__main__":
    asyncio.run(main())
