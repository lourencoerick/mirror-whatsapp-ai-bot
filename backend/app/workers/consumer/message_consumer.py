import asyncio
import json
import time
from typing import Optional, Union
from loguru import logger
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.repository import message as message_repo
from app.services.repository import conversation as conversation_repo
from app.services.queue.redis_queue import RedisQueue
from app.api.schemas.message import MessageCreate
from app.services.helper.conversation import (
    update_last_message_snapshot,
    parse_conversation_to_conversation_response,
)
from app.services.helper.websocket import (
    publish_to_conversation_ws,
    publish_to_account_conversations_ws,
)

# Import the enum
from app.models.conversation import ConversationStatusEnum, Conversation


class MessageConsumer:
    """
    Message consumer to process messages from the input queue and enqueue them to the output queue.
    """

    def __init__(
        self,
        input_queue_name: str = "message_queue",
        output_queue_name: str = "ready_for_processing_queue",
    ):
        """
        Initializes the consumer with input and output queues.

        Args:
            input_queue_name (str): Name of the input queue. Defaults to "message_queue".
            output_queue_name (str): Name of the output queue. Defaults to "ready_for_processing_queue".
        """
        self.input_queue = RedisQueue(queue_name=input_queue_name)
        self.output_queue = RedisQueue(queue_name=output_queue_name)
        logger.info("[MessageConsumer:init] Initialized")

    async def run(self):
        """
        Runs the message consumer in an infinite loop.
        Waits until the Redis connections are established before starting message processing.
        """
        logger.info("[consumer] Starting message consumer...")

        logger.info("[consumer] Attempting to connect to Redis queues...")
        await self.input_queue.connect()
        await self.output_queue.connect()

        retry_delay = 5
        max_retries = 5
        retries = 0
        while (
            not (self.input_queue.is_connected and self.output_queue.is_connected)
            and retries < max_retries
        ):
            retries += 1
            logger.warning(
                f"[consumer] Failed initial Redis connection (Input: {self.input_queue.is_connected}, Output: {self.output_queue.is_connected}). "
                f"Retrying attempt {retries}/{max_retries} in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            if not self.input_queue.is_connected:
                await self.input_queue.connect()
            if not self.output_queue.is_connected:
                await self.output_queue.connect()

        if not (self.input_queue.is_connected and self.output_queue.is_connected):
            logger.error(
                "[consumer] Could not establish Redis connections after multiple attempts. Exiting."
            )
            return

        while True:
            try:
                raw_message: Optional[Union[str, dict]] = (
                    await self.input_queue.dequeue()
                )

                if not raw_message:
                    await asyncio.sleep(0.1)
                    continue

                logger.debug(f"[consumer] Raw message dequeued: {raw_message}")
                data = (
                    raw_message
                    if isinstance(raw_message, dict)
                    else json.loads(raw_message)
                )

                start_time = time.time()
                async with AsyncSessionLocal() as db:
                    try:
                        # Pass db and data to the handler
                        await self._handle_message(db, data)
                        # Commit happens here if _handle_message was successful
                        await db.commit()
                        # Enqueue to output only after successful commit
                        await self.output_queue.enqueue(raw_message)
                        logger.debug(
                            f"[consumer] Enqueued raw_message in output_queue: {raw_message}"
                        )
                    except Exception as e:
                        # Rollback on any error within _handle_message or commit
                        logger.error(
                            f"[consumer] Rolling back transaction due to error: {e}"
                        )
                        await db.rollback()
                        # Re-raise the exception to be caught by the outer loop's handler
                        raise
                    # Session is automatically closed by the context manager

                elapsed = time.time() - start_time
                logger.debug(f"[consumer] Processed in {elapsed:.2f}s")

            except json.JSONDecodeError:
                logger.warning("[consumer] Received malformed JSON.")
            except Exception as e:
                logger.exception(
                    f"[consumer] Unexpected failure processing message: {type(e).__name__} - {e}"
                )
                # Optional: Add a delay or move to a dead-letter queue here
                await asyncio.sleep(1)  # Add a small delay before retrying the loop

    async def _handle_message(self, db: AsyncSession, data: dict):
        """
        Processes the message, saves it, updates conversation state, and publishes updates.

        Args:
            db (AsyncSession): Database session.
            data (dict): Message data.

        Raises:
            Exception: Propagates exceptions to allow for transaction rollback.
        """
        try:
            message_data = MessageCreate(**data)
        except Exception as e:
            logger.warning(f"[consumer] Invalid message payload: {e}")
            # Don't raise here, just skip this message
            return

        # This will raise an exception if saving fails, caught by the outer try/except
        message = await message_repo.get_or_create_message(
            db=db, message_data=message_data
        )

        if not message:
            # Should not happen if get_or_create_message raises on error, but good practice
            logger.warning(
                "[consumer] Failed to get or create message, skipping further processing."
            )
            return

        # Fetch the conversation associated with the message
        conversation = await conversation_repo.find_conversation_by_id(
            db=db,
            conversation_id=message.conversation_id,
            account_id=message.account_id,
        )

        if not conversation:
            logger.warning(
                f"[consumer] Conversation not found: {message.conversation_id}. Cannot update state."
            )
            # Decide if this is an error or just a warning. If the message was saved,
            # maybe the conversation was deleted? For now, log and continue.
            return  # Skip updates if conversation doesn't exist

        logger.info(
            f"[consumer] Message logged successfully: {message.id}. Processing conversation updates."
        )

        # --- Start Conversation Updates ---
        final_updated_conversation: Optional[Conversation] = None

        # 1. Increment Unread Count (only for incoming messages)
        if (
            message.direction == "in"
        ):  # Assuming sender_type distinguishes contact/agent
            logger.debug(
                f"Incrementing unread count for conversation {conversation.id}"
            )
            updated_conv_increment = (
                await conversation_repo.increment_conversation_unread_count(
                    db=db,
                    account_id=conversation.account_id,
                    conversation_id=conversation.id,
                )
            )
            if not updated_conv_increment:
                # Log warning, but rely on transaction rollback if it was a DB error
                logger.warning(
                    f"Failed to increment unread count for conversation {conversation.id}"
                )
                # Potentially raise an exception here if this is critical
                # raise Exception(f"Failed to increment unread count for conversation {conversation.id}")
                final_updated_conversation = (
                    conversation  # Use original if update failed
                )
            else:
                final_updated_conversation = updated_conv_increment
                logger.info(
                    f"Unread count incremented for conversation {conversation.id} to {final_updated_conversation.unread_agent_count}"
                )
        else:
            # If message is from AGENT or BOT, don't increment, use current conversation state
            final_updated_conversation = conversation

        # 2. Update Status if it was CLOSED (only for incoming CONTACT messages)
        # Use the state *before* potential increment for the check
        if (
            message.direction == "in"
            and conversation.status == ConversationStatusEnum.CLOSED
        ):
            logger.debug(f"Re-opening closed conversation {conversation.id} to PENDING")
            updated_conv_status = await conversation_repo.update_conversation_status(
                db=db,
                account_id=conversation.account_id,
                conversation_id=conversation.id,
                new_status=ConversationStatusEnum.PENDING,
            )
            if not updated_conv_status:
                logger.warning(
                    f"Failed to update status for conversation {conversation.id} from CLOSED to PENDING"
                )
                # Potentially raise an exception here if this is critical
                # raise Exception(f"Failed to update status for conversation {conversation.id}")
                # Keep the result from the increment step if status update failed
            else:
                # Update our final variable with the latest state
                final_updated_conversation = updated_conv_status
                logger.info(
                    f"Status updated for conversation {conversation.id} to {final_updated_conversation.status}"
                )

        # Ensure we have a conversation object to work with for subsequent steps
        if not final_updated_conversation:
            logger.error(
                f"Conversation object became None after updates for {conversation.id}. This shouldn't happen."
            )
            # Raise an exception to rollback transaction
            raise Exception(
                f"Conversation object lost during updates for {conversation.id}"
            )

        # 3. Update Last Message Snapshot (using the final updated conversation state)
        await update_last_message_snapshot(
            db=db, conversation=final_updated_conversation, message=message
        )
        # --- End Conversation Updates ---

        # --- WebSocket Publishing ---
        # Publish the incoming message to the specific conversation channel
        try:
            await publish_to_conversation_ws(
                conversation_id=message.conversation_id,
                data={
                    "type": "incoming_message",
                    "payload": jsonable_encoder(message),
                },
            )
        except Exception as e:
            logger.warning(
                f"[ws] Failed to publish message {message.id} to conversation websocket: {e}"
            )

        # Publish the updated conversation state to the general account channel
        try:
            # Use the final_updated_conversation which includes new count/status
            parsed_conversation = parse_conversation_to_conversation_response(
                final_updated_conversation
            )
            await publish_to_account_conversations_ws(
                final_updated_conversation.account_id,
                {
                    "type": "conversation_updated",
                    "payload": jsonable_encoder(parsed_conversation),
                },
            )
            logger.debug(
                f"[ws] Published conversation_updated for {final_updated_conversation.id}"
            )
        except Exception as e:
            logger.warning(
                f"[ws] Failed to publish conversation update for {final_updated_conversation.id} to account websocket: {e}"
            )
        # --- End WebSocket Publishing ---


async def main():
    """
    Main function to start the message consumer.
    """
    consumer = MessageConsumer()
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
