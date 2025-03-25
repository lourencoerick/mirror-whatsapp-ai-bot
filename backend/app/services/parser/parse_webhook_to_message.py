from typing import Dict, Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.services.parser.evolution_parser import parse_evolution_message
from app.services.repository.inbox import find_by_channel_id
from app.services.repository.contact import upsert_contact, get_or_create_contact_inbox
from app.services.repository.conversation import get_or_create_conversation
from app.api.schemas.message import MessageCreate


def parse_webhook_to_message(
    db: Session, account_id: int, payload: Dict
) -> Optional[MessageCreate]:
    """
    Process a raw webhook payload and return a complete MessageCreate DTO.
    Resolves inbox, contact, conversation and enriches the message object.
    """
    logger.info("[parser] Starting webhook parsing process")

    # Step 1 - Parse raw payload
    parsed = parse_evolution_message(payload)
    if not parsed:
        logger.warning("[parser] Failed to parse base message")
        return None

    source_id = parsed["source_id"]
    channel_id = parsed["content_attributes"].get("instance_id")
    logger.info(f"[parser] channel_id {channel_id}")
    remote_jid = parsed["remote_jid"]
    contact_phone = remote_jid.split("@")[0] if remote_jid else None
    contact_name = payload.get("data", {}).get("pushName")

    if not all([channel_id, contact_phone]):
        logger.error("[parser] Missing channel_id or contact_phone in parsed content")
        return None

    # Step 2 - Inbox
    inbox = find_by_channel_id(db, account_id, channel_id)
    if not inbox:
        logger.error(f"[parser] Inbox not found for channel_id {channel_id}")
        return None

    # Step 3 - Contact (upsert) & ContactInbox
    contact = upsert_contact(
        db=db,
        account_id=account_id,
        phone_number=contact_phone,
        name=contact_name,
    )

    contact_inbox = get_or_create_contact_inbox(
        db=db, contact_id=contact.id, inbox_id=inbox.id, source_id=source_id
    )

    # Step 4 - Conversation (get or create)
    conversation = get_or_create_conversation(
        db=db,
        account_id=account_id,
        inbox_id=inbox.id,
        contact_inbox_id=contact_inbox.id,
    )

    # Step 5 - Finalize message DTO
    message_create = MessageCreate(
        account_id=account_id,
        content=parsed["content"],
        direction=parsed["direction"],
        source_id=parsed["source_id"],
        content_type=parsed["content_type"],
        status="received",
        message_timestamp=parsed["message_timestamp"],
        content_attributes=parsed.get("content_attributes", {}),
        private=False,
        inbox_id=inbox.id,
        contact_id=contact.id,
        conversation_id=conversation.id,
    )

    logger.debug(f"[parser] Message DTO ready for enqueue: {message_create}")
    return message_create.model_dump()
