import asyncio
import httpx
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.services.queue.redis_queue import RedisQueue
from app.services.sender import evolution as evolution_sender
from app.services.sender import whatsapp_cloud as whatsapp_cloud_sender
from app.models.channels.channel_types import ChannelTypeEnum
from app.services.repository import message as message_repo
from app.services.repository import inbox as inbox_repo

from app.services.repository import evolution_instance as evolution_instance_repo
from app.services.helper.checkpoint import reset_checkpoint
from app.services.repository.message import (
    delete_messages_by_conversation,
)
from app.config import get_settings, Settings

settings: Settings = get_settings()


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
            payload = await self.queue.dequeue()
            if not payload:
                return

            logger.debug(f"[sender] Raw data dequeued: {payload}")

            message_id = payload.get("message_id")
            if not message_id:
                logger.warning("[sender] Payload missing 'message_id'")
                return

            async with AsyncSessionLocal() as db:
                try:
                    await self._handle_message(db, message_id)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                finally:
                    await db.close()

        except Exception as e:
            logger.exception(f"[sender] Unexpected failure: {type(e).__name__} - {e}")

    async def run(self):
        """
        Starts the infinite loop to consume and process messages from the queue.
        Waits until the Redis connection is established before starting.
        """
        logger.info("[sender] Listening for messages to send...")

        logger.info("[sender] Attempting to connect to Redis queues...")

        retry_delay = 5
        max_retries = 5
        retries = 0
        while not (self.queue.is_connected) and retries < max_retries:
            retries += 1
            logger.warning(
                f"[sender] Failed initial Redis connection {self.queue.is_connected}. "
                f"Retrying attempt {retries}/{max_retries} in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            if not self.queue.is_connected:
                await self.queue.connect()

        if not (self.queue.is_connected):
            logger.error(
                "[sender] Could not establish Redis connections after multiple attempts. Exiting."
            )
            return

        while True:
            await self._process_one_message()
            await asyncio.sleep(0.1)

    async def _handle_message(self, db: AsyncSession, message_id: UUID):
        """
        Handles delivery of a specific message by ID, with retries if not found initially.

        Args:
            db (AsyncSession): Active SQLAlchemy database session.
            message_id (UUID): The ID of the message to be delivered.
        """
        message = None
        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            message = await message_repo.find_message_by_id(db, message_id)
            if message:
                logger.debug(
                    f"[sender] Message {message_id} found on attempt {attempt + 1}."
                )
                break
            else:
                logger.warning(
                    f"[sender] Message ID {message_id} not found on attempt {attempt + 1}/{max_retries}. "
                    f"Retrying in {retry_delay}s..."
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

        if not message:
            logger.error(
                f"[sender] Message ID {message_id} not found after {max_retries} attempts. Giving up."
            )

            return

        try:

            await db.refresh(message, attribute_names=["contact", "inbox"])
        except Exception as refresh_err:
            logger.error(
                f"[sender] Failed to refresh message {message_id} relations: {refresh_err}. Proceeding without refresh."
            )

        try:
            if not message.inbox:
                logger.error(
                    f"[sender] Inbox relation not loaded for message {message_id}. Cannot send."
                )
                message.status = "failed"

                return

            message_content = message.content
            phone_number = message.contact.phone_number

            if message_content == settings.RESET_MESSAGE_TRIGGER:
                message_content = (
                    message_content + " Ativado! Deleção do histórico feito!"
                )

            inbox_with_config = await inbox_repo.find_inbox_by_id_and_account(
                db=db,
                inbox_id=message.inbox.id,
                account_id=message.account_id,
            )

            status_from_provider: str = "pending"
            external_id: str = None
            if inbox_with_config.channel_type == ChannelTypeEnum.WHATSAPP_EVOLUTION:
                api_response_data = await evolution_sender.send_message(
                    message_content=message_content,
                    phone_number=phone_number,
                    evolution_instance=inbox_with_config.evolution_instance,
                )

                external_id = api_response_data.get("key", {}).get("id")
                status_from_provider = api_response_data.get(
                    "status", "pending"
                ).lower()

            elif inbox_with_config.channel_type == ChannelTypeEnum.WHATSAPP_CLOUD:
                api_response_data = await whatsapp_cloud_sender.send_text_message(
                    message_content=message_content,
                    recipient_phone_number=phone_number,
                    config=inbox_with_config.whatsapp_cloud_config,
                )

                external_id = api_response_data.get("messages", [])[0].get("id")

            if external_id:
                logger.info(
                    f"[sender] Message {message.id} sent, external ID: {external_id}"
                )

            message.status = status_from_provider
            message.source_id = external_id
            db.add(message)

            logger.info(
                f"[sender] Message {message.id} status updated to '{status_from_provider}' based on provider response."
            )

            if message.content.lower().strip() == settings.RESET_MESSAGE_TRIGGER:
                thread_id_str = str(message.conversation_id)

                # await delete_messages_by_conversation(
                #     db=db, conversation_id=message.conversation_id
                # )
                await reset_checkpoint(db=db, thread_id=thread_id_str)

                logger.info(
                    "[sender] Deleting messages for testing bot agent from no history."
                )

        except httpx.HTTPError as e:
            message.status = "failed"
            db.add(message)
            logger.warning(f"[sender] HTTP error sending message {message.id}: {e}")
        except Exception as e:
            message.status = "failed"
            db.add(message)
            logger.exception(
                f"[sender] Unexpected error sending message {message.id}: {e}"
            )

        # O commit final será feito em _process_one_message após esta função retornar


async def main():
    """
    Main function to start the response sender.
    """
    sender = ResponseSender()
    await sender.run()


if __name__ == "__main__":
    asyncio.run(main())
