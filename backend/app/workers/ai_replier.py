# backend/app/workers/ai_replier.py
import os
import asyncio
import random
from uuid import UUID, uuid4
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timezone

# Database and Queue imports (adjust paths as needed)
from app.database import AsyncSessionLocal
from app.services.queue.redis_queue import RedisQueue
from app.services.repository import message as message_repo
from app.services.repository import conversation as conversation_repo

from app.models.message import Message  # Import the Message model for type hinting
from app.api.schemas.message import MessageCreate

# AI Reply Service import
from app.services.ai_reply import processor as ai_processor

# --- Configuration ---
# Consider moving queue names to environment variables/settings
AI_REPLY_QUEUE_NAME = "ai_reply_queue"
RESPONSE_SENDER_QUEUE_NAME = "response_queue"  # Queue the ResponseSender listens to

# Base delay in seconds
AI_DELAY_BASE_SECONDS = float(os.getenv("AI_DELAY_BASE_SECONDS", 0.5))

# Adjust for desired "typing speed"
AI_DELAY_PER_CHAR_SECONDS = float(os.getenv("AI_DELAY_PER_CHAR_SECONDS", 0.025))
# Maximum random variation (plus/minus) in seconds
AI_DELAY_RANDOM_SECONDS = float(os.getenv("AI_DELAY_RANDOM_SECONDS", 1.5))
# Absolute minimum delay
AI_DELAY_MIN_SECONDS = float(os.getenv("AI_DELAY_MIN_SECONDS", 2.0))
# Absolute maximum delay
AI_DELAY_MAX_SECONDS = float(os.getenv("AI_DELAY_MAX_SECONDS", 3.0))


class AiReplier:
    """
    Background worker that listens for messages needing an AI reply,
    processes them using the ai_reply service, creates a new outgoing
    message record with the AI response, and queues it for sending.
    """

    def __init__(
        self,
        input_queue_name: str = AI_REPLY_QUEUE_NAME,
        output_queue_name: str = RESPONSE_SENDER_QUEUE_NAME,
    ):
        """
        Initializes the Redis queue listeners/producers.

        Args:
            input_queue_name (str): Name of the queue to consume AI requests from.
            output_queue_name (str): Name of the queue to push sender tasks to.
        """
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info(
            f"[ai_replier:init] Initialized queues: input='{input_queue_name}', output='{output_queue_name}'"
        )

    def _compute_delay(self, response_text: str) -> float:
        response_length = len(response_text)
        # Calculate delay based on length
        length_delay = response_length * AI_DELAY_PER_CHAR_SECONDS
        # Add base delay
        base_calculated_delay = AI_DELAY_BASE_SECONDS + length_delay
        # Add random variation (+/-)
        random_offset = random.uniform(
            -AI_DELAY_RANDOM_SECONDS, AI_DELAY_RANDOM_SECONDS
        )
        total_delay = base_calculated_delay + random_offset
        # Apply min and max limits
        return max(AI_DELAY_MIN_SECONDS, min(AI_DELAY_MAX_SECONDS, total_delay))

    async def _process_one_task(self):
        """
        Processes one task from the input queue: fetches original message,
        generates AI reply, creates outgoing message, queues for sending.
        """
        payload = None
        try:
            payload = await self.input_queue.dequeue()
            if not payload:
                return  # No task found, wait and try again

            logger.debug(f"[ai_replier] Raw task dequeued: {payload}")

            # --- Validate Payload ---
            message_id_str = payload.get("message_id")
            conversation_id_str = payload.get("conversation_id")
            account_id = payload.get("account_id")

            if not all([message_id_str, conversation_id_str, account_id]):
                logger.warning(
                    f"[ai_replier] Task payload missing required fields: {payload}"
                )
                return

            try:
                message_id = UUID(message_id_str)
                conversation_id = UUID(conversation_id_str)
            except ValueError:
                logger.warning(
                    f"[ai_replier] Invalid UUID format in payload: {payload}"
                )
                return

            # --- Process Task ---
            async with AsyncSessionLocal() as db:
                try:
                    await self._handle_ai_request(
                        db,
                        message_id=message_id,
                        conversation_id=conversation_id,
                        account_id=account_id,
                    )
                    # Commit happens here if _handle_ai_request succeeds
                    await db.commit()
                    logger.debug(
                        f"[ai_replier] Successfully processed task for message {message_id}"
                    )
                except Exception as handler_exc:
                    # Log the specific error from the handler
                    logger.error(
                        f"[ai_replier] Error handling task for message {message_id}: {handler_exc}"
                    )
                    await db.rollback()
                    # Optionally: Add logic for retries or dead-letter queue here
                finally:
                    await db.close()

        except Exception as e:
            logger.exception(
                f"[ai_replier] Unexpected failure processing task. Payload: {payload}. Error: {e}"
            )
            # Optionally: Add logic for retries or dead-letter queue here for dequeue/parsing errors

    async def run(self):
        """
        Starts the infinite loop to consume and process tasks from the input queue.
        Waits until Redis connections are established.
        """
        logger.info("[ai_replier] Starting worker...")

        logger.info("[ai_replier] Attempting to connect to Redis queues...")
        retry_delay = 5
        max_retries = 5
        retries = 0
        # Wait for both queues to connect
        while (
            not (self.input_queue.is_connected and self.output_queue.is_connected)
            and retries < max_retries
        ):
            retries += 1
            logger.warning(
                f"[ai_replier] Redis connection status: input={self.input_queue.is_connected}, output={self.output_queue.is_connected}. "
                f"Retrying attempt {retries}/{max_retries} in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            # Attempt reconnection if needed
            if not self.input_queue.is_connected:
                await self.input_queue.connect()
            if not self.output_queue.is_connected:
                await self.output_queue.connect()

        if not (self.input_queue.is_connected and self.output_queue.is_connected):
            logger.critical(
                "[ai_replier] Could not establish Redis connections after multiple attempts. Exiting."
            )
            return

        logger.info(
            "[ai_replier] Redis connections established. Listening for tasks..."
        )
        while True:
            await self._process_one_task()
            # Small sleep to prevent high CPU usage in case of empty queue
            await asyncio.sleep(0.1)

    async def _handle_ai_request(
        self,
        db: AsyncSession,
        message_id: UUID,
        account_id: UUID,
        conversation_id: UUID,
    ):
        """
        Handles the AI reply generation and queuing for a specific message.

        Args:
            db: Active SQLAlchemy database session.
            message_id: The ID of the original incoming message.
            conversation_id: The ID of the conversation thread.
            account_id: The company identifier.
        """
        # 1. Fetch Original Message (to get text and context like contact_id, inbox_id)
        # Using find_message_by_id like in ResponseSender for consistency
        original_message: Optional[Message] = await message_repo.find_message_by_id(
            db, message_id
        )

        if not original_message:
            # This shouldn't happen often if the task is created right after the message
            logger.error(
                f"[ai_replier] Original message {message_id} not found in DB. Cannot process."
            )
            # Raise an exception to trigger rollback in _process_one_task
            raise ValueError(f"Original message {message_id} not found.")

        if not original_message.content:  # Check if message has text content
            logger.warning(
                f"[ai_replier] Original message {message_id} has no text content. Skipping AI reply."
            )
            # Optionally update original message status here?
            # original_message.status = "processed_no_reply_needed"
            # db.add(original_message)
            return  # Successfully processed (by skipping), commit will happen

        # Ensure relations needed for creating the reply are loaded
        # (contact_id, inbox_id might be directly on the message or need refresh)
        try:
            await db.refresh(original_message, attribute_names=["contact", "inbox"])
            contact_id = original_message.contact_id
            inbox_id = original_message.inbox_id
            if not contact_id or not inbox_id:
                raise ValueError("Missing contact_id or inbox_id after refresh")
        except Exception as refresh_err:
            logger.error(
                f"[ai_replier] Failed to refresh message {message_id} relations: {refresh_err}. Cannot create reply."
            )
            raise ValueError(
                f"Failed to load relations for message {message_id}"
            ) from refresh_err

        # 2. Generate AI Response using the processor
        logger.info(f"[ai_replier] Generating AI reply for message {message_id}...")
        ai_response_text = await ai_processor.process_message(
            db=db,
            account_id=account_id,
            message_text=original_message.content,
            conversation_id=str(
                conversation_id
            ),  # Pass as string if processor expects string
        )

        if not ai_response_text:
            logger.warning(
                f"[ai_replier] AI processor returned no response for message {message_id}. No reply will be sent."
            )
            # Optionally update original message status
            # original_message.status = "processed_no_reply_generated"
            # db.add(original_message)
            return  # Successfully processed (no reply needed), commit will happen

        # 3. Create the Outgoing Message record in DB
        logger.info(
            f"[ai_replier] Creating outgoing message record for AI reply to {message_id}..."
        )

        conversation = await conversation_repo.find_conversation_by_id(
            db, conversation_id=conversation_id, account_id=account_id
        )
        # Generate an internal source_id for tracking
        internal_source_id = f"ai-replier-{uuid4().hex}"

        message_data = MessageCreate(
            account_id=account_id,
            inbox_id=conversation.inbox_id,
            conversation_id=conversation.id,
            contact_id=(
                conversation.contact_inbox.contact_id
                if conversation.contact_inbox
                else None
            ),
            source_id=internal_source_id,
            direction="out",
            status="processing",
            message_timestamp=datetime.now(timezone.utc),
            content=ai_response_text,
            content_type="text",
            content_attributes={
                "source": "ai-replier",
                "channel_type": (
                    conversation.inbox.channel_type if conversation.inbox else None
                ),
            },
        )
        try:
            # Assuming a repository function exists to create the message
            # You might need to adjust parameters based on your actual function/model
            ai_message = await message_repo.get_or_create_message(
                db=db,
                message_data=message_data,
            )
            # Flush to get the ai_message.id assigned by the DB
            await db.flush()
            await db.refresh(ai_message)
            logger.info(
                f"[ai_replier] Created outgoing AI message record with ID: {ai_message.id}"
            )

        except Exception as create_exc:
            logger.exception(
                f"[ai_replier] Failed to create outgoing message record in DB for reply to {message_id}"
            )
            # Raise exception to trigger rollback
            raise ValueError("Failed to create outgoing message record") from create_exc

        final_delay = self._compute_delay(ai_response_text)
        response_length = len(ai_response_text)
        try:
            if final_delay > 0:
                logger.debug(
                    f"[ai_replier] Applying dynamic delay of {final_delay:.2f}s (length: {response_length}) before enqueueing message {ai_message.id}..."
                )
                await asyncio.sleep(final_delay)
                logger.debug(
                    f"[ai_replier] Delay finished for message {ai_message.id}."
                )
            else:
                logger.debug(
                    f"[ai_replier] Calculated delay is zero or negative, skipping sleep for message {ai_message.id}."
                )

        except Exception as delay_exc:
            # Log if delay calculation fails, but don't stop the process
            logger.warning(
                f"[ai_replier] Error calculating dynamic delay for message {ai_message.id}: {delay_exc}. Proceeding without delay."
            )

        # 4. Enqueue the new message ID for the ResponseSender
        sender_payload = {"message_id": str(ai_message.id)}
        try:
            await self.output_queue.enqueue(sender_payload)
            logger.info(
                f"[ai_replier] Enqueued message {ai_message.id} to '{self.output_queue.queue_name}' for sending."
            )
        except Exception as enqueue_exc:
            logger.exception(
                f"[ai_replier] Failed to enqueue message {ai_message.id} to output queue '{self.output_queue.queue_name}'"
            )
            # Raise exception to trigger rollback (important: DB record was created but not queued)
            raise ValueError("Failed to enqueue message for sender") from enqueue_exc

        # 5. (Optional) Update original message status
        # original_message.status = "processed_reply_generated"
        # db.add(original_message)
        # logger.debug(f"[ai_replier] Updated status for original message {message_id}")

        # If we reach here, all steps succeeded. The commit will happen in _process_one_task.


# --- Main execution block ---
async def main():
    """Main function to start the AI reply worker."""
    worker = AiReplier()
    await worker.run()


if __name__ == "__main__":
    # Consider adding signal handling for graceful shutdown
    logger.info("Starting AI Reply Worker...")
    asyncio.run(main())
    logger.info("AI Reply Worker stopped.")
