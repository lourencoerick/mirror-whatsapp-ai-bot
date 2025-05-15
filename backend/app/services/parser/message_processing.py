# app/services/parser/message_processing_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from loguru import logger
from fastapi.encoders import jsonable_encoder  # For WebSocket encoding
from typing import Optional

# Standardized DTO received by this function
from app.api.schemas.internal_messaging import InternalIncomingMessageDTO

# Schema to create our MessageModel
from app.api.schemas.message import MessageCreate as MessageCreateSchema

# Schema for the WebSocket payload that updates conversations
from app.api.schemas.conversation import ConversationSearchResult

# Repositories
from app.services.repository import conversation as conversation_repo
from app.services.repository import message as message_repo
from app.services.repository import (
    inbox as inbox_repo,
)  # To fetch inbox and its initial status

# Models
from app.models.conversation import Conversation, ConversationStatusEnum
from app.models.message import Message as MessageModel  # Your SQLAlchemy Message model

# Helpers
from app.services.helper.conversation import (
    update_last_message_snapshot,
    parse_conversation_to_conversation_response,
)
from app.services.helper.websocket import (
    publish_to_conversation_ws,
    publish_to_account_conversations_ws,
)


async def process_incoming_message_logic(
    db: AsyncSession, internal_message: InternalIncomingMessageDTO
):
    """
    Core logic to process a standardized InternalIncomingMessageDTO.

    This function is called by an ARQ task after the initial transformation
    of an external webhook payload (e.g., from WhatsApp Cloud or Evolution API).

    It handles:
    1. Getting or creating the Message record in the database (idempotently).
    2. Finding the associated Conversation.
    3. Updating Conversation state (unread count, last message, status).
    4. Publishing WebSocket events to notify clients.
    5. Committing all database changes as a single transaction.
    """
    logger.info(
        f"Processing message logic for internal DTO, source: {internal_message.source_api}, source_id: {internal_message.external_message_id}"
    )
    logger.debug(f"Internal DTO payload: {internal_message.model_dump_json(indent=2)}")

    try:
        # --- 1. Prepare MessageCreateSchema for the repository ---
        # IDs (account, inbox, contact, conversation) are already in the DTO
        message_create_for_repo = MessageCreateSchema(
            account_id=internal_message.account_id,
            inbox_id=internal_message.inbox_id,
            contact_id=internal_message.contact_id,
            conversation_id=internal_message.conversation_id,
            source_id=internal_message.external_message_id,
            direction="in",  # This service handles incoming messages
            status="received",  # Initial status when received by the platform
            message_timestamp=internal_message.message_timestamp,
            content=internal_message.message_content,
            content_type=internal_message.internal_content_type,
            content_attributes=internal_message.raw_message_attributes,
        )

        # --- 2. Get or Create Message (Idempotent) ---
        # get_or_create_message must be idempotent based on (source_id, inbox_id, account_id) or similar.
        # If the message already exists and has been processed (e.g., status != "received"),
        # we may choose to skip conversation updates to avoid duplication.
        db_message = await message_repo.get_or_create_message(
            db=db, message_data=message_create_for_repo
        )

        if not db_message:
            logger.error(
                f"Failed to get or create message for source_id: {internal_message.external_message_id}. Aborting processing for this message."
            )
            # Do not raise to avoid infinite retries in ARQ due to bad data.
            return

        logger.info(
            f"Message record {db_message.id} (external: {db_message.source_id}) obtained/created."
        )

        # --- 3. Find associated Conversation ---
        conversation = await conversation_repo.find_conversation_by_id(
            db=db,
            conversation_id=db_message.conversation_id,
            account_id=db_message.account_id,
        )

        if not conversation:
            logger.error(
                f"Conversation {db_message.conversation_id} not found for message {db_message.id}. "
                "This is unexpected as it should have been created/found by the transformer. Aborting."
            )
            raise Exception(
                f"Data integrity issue: Conversation {db_message.conversation_id} not found after message creation."
            )

        logger.info(
            f"Processing updates for conversation {conversation.id} (current status: {conversation.status.value})"
        )

        # --- 4. Update Conversation State ---
        final_updated_conversation: Conversation = conversation

        # For simplicity, assume that reaching this point means the message is "new"
        # and eligible for conversation updates (unread count, status, etc.)
        if db_message.direction == "in":
            updated_conv_increment = (
                await conversation_repo.increment_conversation_unread_count(
                    db=db,
                    account_id=conversation.account_id,
                    conversation_id=conversation.id,
                )
            )
            if updated_conv_increment:
                final_updated_conversation = updated_conv_increment
            logger.debug(
                f"Incremented unread count for conversation {conversation.id}. New count: {final_updated_conversation.unread_agent_count}"
            )

            if final_updated_conversation.status == ConversationStatusEnum.CLOSED:
                target_inbox = await inbox_repo.find_inbox_by_id_and_account(
                    db=db,
                    inbox_id=final_updated_conversation.inbox_id,
                    account_id=final_updated_conversation.account_id,
                )
                if target_inbox and target_inbox.initial_conversation_status:
                    new_status_on_reopen = target_inbox.initial_conversation_status
                    updated_conv_status = (
                        await conversation_repo.update_conversation_status(
                            db=db,
                            account_id=final_updated_conversation.account_id,
                            conversation_id=final_updated_conversation.id,
                            new_status=new_status_on_reopen,
                        )
                    )
                    if updated_conv_status:
                        final_updated_conversation = updated_conv_status
                    logger.info(
                        f"Re-opened conversation {final_updated_conversation.id} to status {new_status_on_reopen.value}"
                    )
                else:
                    logger.warning(
                        f"Could not find inbox {final_updated_conversation.inbox_id} or it has no initial_conversation_status defined. Conversation {final_updated_conversation.id} remains {final_updated_conversation.status.value}."
                    )

        await update_last_message_snapshot(
            db=db, conversation=final_updated_conversation, message=db_message
        )
        logger.debug(
            f"Updated last message snapshot for conversation {final_updated_conversation.id}"
        )

        # --- 5. WebSocket Publishing ---
        try:
            message_for_ws = jsonable_encoder(db_message, exclude_none=True)
            await publish_to_conversation_ws(
                conversation_id=str(db_message.conversation_id),
                data={"type": "new_message", "payload": message_for_ws},
            )
            logger.debug(
                f"WebSocket: Published new_message event for conversation {db_message.conversation_id}"
            )
        except Exception as e:
            logger.warning(
                f"WebSocket: Failed to publish new_message {db_message.id}: {e}",
                exc_info=True,
            )

        try:
            reloaded_conversation_for_ws = (
                await conversation_repo.find_conversation_by_id(
                    db=db,
                    conversation_id=final_updated_conversation.id,
                    account_id=final_updated_conversation.account_id,
                )
            )
            if reloaded_conversation_for_ws:
                parsed_conversation_for_ws: Optional[ConversationSearchResult] = (
                    parse_conversation_to_conversation_response(
                        reloaded_conversation_for_ws
                    )
                )
                if parsed_conversation_for_ws:
                    await publish_to_account_conversations_ws(
                        account_id=str(final_updated_conversation.account_id),
                        data={
                            "type": "conversation_updated",
                            "payload": jsonable_encoder(
                                parsed_conversation_for_ws.model_dump(exclude_none=True)
                            ),
                        },
                    )
                    logger.debug(
                        f"WebSocket: Published conversation_updated event for {final_updated_conversation.id}"
                    )
                else:
                    logger.warning(
                        f"WebSocket: Failed to parse reloaded conversation {final_updated_conversation.id} for update event."
                    )
            else:
                logger.warning(
                    f"WebSocket: Could not reload conversation {final_updated_conversation.id} for update event."
                )
        except Exception as e:
            logger.warning(
                f"WebSocket: Failed to publish conversation_updated for {final_updated_conversation.id}: {e}",
                exc_info=True,
            )

        # --- 6. Commit ---
        await db.commit()
        logger.info(
            f"Successfully processed and committed changes for DTO, source_id: {internal_message.external_message_id}, message_id: {db_message.id}"
        )

    except Exception as e:
        logger.exception(
            f"Core logic error processing DTO for source_id: {internal_message.external_message_id if internal_message else 'Unknown DTO'}"
        )
        await db.rollback()
        raise
