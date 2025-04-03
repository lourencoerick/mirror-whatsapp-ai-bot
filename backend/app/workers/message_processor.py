import asyncio
import json
import time
from typing import Optional
from loguru import logger
from dotenv import load_dotenv

from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.response import ResponseMessage

load_dotenv()


class MessageProcessor:
    def __init__(
        self,
        input_queue_name: str = "ready_for_processing_queue",
        output_queue_name: str = "response_queue",
    ):
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageProcessor:init] Initialized")

    async def process_message(self, message: dict) -> Optional[ResponseMessage]:
        """
        Process the message and return a ResponseMessage object.
        """
        try:
            logger.debug(f"[MessageProcessor:process] message recieved: {message}")
            provider = "evolution"

            data = message.get("data")
            content = data.get("message").get("conversation")
            to_phone_number = data.get("key").get("remoteJid").split("@")[0]
            message_id = data.get("key").get("id")

            if not all([data, to_phone_number]):
                logger.warning("[MessageProcessor:process] Missing required fields")
                return None

            return ResponseMessage(
                to=str(to_phone_number),
                original_message_id=message_id,
                response_text=f"🤖 Auto-reply: '{content}'",
                provider=provider,
            )

        except Exception:
            logger.exception("[MessageProcessor:process] Unexpected failure")
            return None

    async def run(self):
        """
        Main loop to process messages from the input queue.
        """
        logger.info("[MessageProcessor:run] Starting main loop")

        while True:
            try:
                logger.debug("[queue] Waiting for message...")
                raw_message = await self.input_queue.dequeue()

                if not raw_message:
                    logger.debug("[queue] Empty queue slot")
                    await asyncio.sleep(0.1)  # Don't hog the CPU, sleep a bit
                    continue

                logger.debug(f"[queue] Message dequeued: {raw_message}")

                try:
                    message_dict = (
                        json.loads(raw_message)
                        if isinstance(raw_message, str)
                        else raw_message
                    )
                except Exception as e:
                    logger.warning(f"[processor:parse] Invalid JSON: {e}")
                    continue

                response = await self.process_message(message_dict)

                if response:
                    await self.output_queue.enqueue(response.model_dump_json())
                    logger.debug(f"[queue] Response enqueued: {response}")
                else:
                    logger.warning("[MessageProcessor:run] Skipped invalid message")

            except Exception as e:
                logger.exception(
                    f"[MessageProcessor:run] Fatal error in main loop: {e}"
                )
                await asyncio.sleep(5)

    async def start(self):
        """
        Start the message processor, including connecting to Redis.
        """
        await self.input_queue.connect()
        await self.output_queue.connect()
        await self.run()


async def main():
    """
    Main function to run the MessageProcessor.
    """
    processor = MessageProcessor()
    await processor.start()


if __name__ == "__main__":
    asyncio.run(main())
