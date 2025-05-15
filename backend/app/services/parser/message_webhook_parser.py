# app/services/parser/message_webhook_parser.py

from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from loguru import logger
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.api.schemas.webhooks.whatsapp_cloud import (
    WhatsAppMessage as WhatsAppCloudMessageSchema,
)
from app.api.schemas.internal_messaging import InternalIncomingMessageDTO
from app.api.schemas.contact import ContactCreate as ContactCreateSchema

from app.services.repository import (
    inbox as inbox_repo,
)
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo

from app.models.inbox import Inbox
from app.models.account import Account
from app.models.conversation import ConversationStatusEnum


async def transform_evolution_api_to_internal_dto(
    db: AsyncSession,
    instance_name: str,
    raw_evolution_message_dict: Dict[str, Any],
) -> Optional[InternalIncomingMessageDTO]:
    pass


async def transform_whatsapp_cloud_to_internal_dto(
    db: AsyncSession,
    business_phone_number_id: str,
    single_meta_message_dict: Dict[str, Any],
    meta_contacts_list_dicts: Optional[List[Dict[str, Any]]],
) -> Optional[InternalIncomingMessageDTO]:

    log_prefix = f"Transformer (WPP Cloud, BusinessPhID: {business_phone_number_id}):"
    logger.debug(f"{log_prefix} Starting transformation for single message.")
    logger.trace(f"{log_prefix} Single message dict: {single_meta_message_dict}")
    logger.trace(f"{log_prefix} Meta contacts list: {meta_contacts_list_dicts}")

    try:
        parsed_meta_message = WhatsAppCloudMessageSchema.model_validate(
            single_meta_message_dict
        )

        # --- 1. Find associated Inbox and Account ---
        inbox_details = await inbox_repo.find_inbox_and_account_by_wpp_cloud_phone_id(
            db, wpp_phone_number_id=business_phone_number_id
        )
        if not inbox_details:
            logger.error(
                f"No active inbox/account for WPP business_phone_id: {business_phone_number_id}"
            )
            return None
        inbox: Inbox = inbox_details.inbox
        account: Account = inbox_details.account
        account_id: UUID = account.id
        logger.info(f"Transformer: Using Inbox ID {inbox.id}, Account ID {account_id}")

        # --- 2. Extract sender information ---
        sender_wa_id = parsed_meta_message.from_number
        sender_profile_name: Optional[str] = None
        if meta_contacts_list_dicts:
            # O wa_id no objeto de contato da Meta é o mesmo que o 'from_number' da mensagem
            contact_profile_info = next(
                (c for c in meta_contacts_list_dicts if c.get("wa_id") == sender_wa_id),
                None,
            )
            if contact_profile_info and contact_profile_info.get("profile"):
                sender_profile_name = contact_profile_info["profile"].get("name")
        logger.debug(
            f"{log_prefix} Sender WA ID: {sender_wa_id}, Profile Name: {sender_profile_name}"
        )

        # --- 3. Get or Create Contact ---
        contact = await contact_repo.find_contact_by_identifier(
            db=db, identifier=sender_wa_id, account_id=account_id
        )

        if not contact:
            contact_create_data = ContactCreateSchema(
                phone_number=sender_wa_id, name=sender_profile_name
            )
            contact = await contact_repo.create_contact(
                db=db, contact_data=contact_create_data, account_id=account_id
            )
        elif sender_profile_name and contact.name != sender_profile_name:
            contact.name = sender_profile_name
            db.add(contact)
        logger.info(f"Transformer: Using Contact ID {contact.id}")

        # --- 4. Get or Create ContactInbox ---
        contact_inbox = await contact_repo.get_or_create_contact_inbox(
            db=db,
            account_id=account_id,
            contact_id=contact.id,
            inbox_id=inbox.id,
            source_id=f"wpp_cloud_{business_phone_number_id}",
        )
        logger.info(f"Transformer: Using ContactInbox ID {contact_inbox.id}")

        # --- 5. Get or Create Conversation ---
        initial_conv_status = (
            inbox.initial_conversation_status or ConversationStatusEnum.PENDING
        )
        conversation = await conversation_repo.get_or_create_conversation(
            db=db,
            account_id=account_id,
            inbox_id=inbox.id,
            contact_inbox_id=contact_inbox.id,
            status=initial_conv_status,
        )
        if conversation.status == ConversationStatusEnum.CLOSED:
            conversation.status = initial_conv_status
            conversation.unread_agent_count = 0
            db.add(conversation)
        logger.info(f"Transformer: Using Conversation ID {conversation.id}")

        # --- 6. Map Meta message to InternalIncomingMessageDTO fields ---
        external_message_id = parsed_meta_message.id
        message_timestamp = datetime.fromtimestamp(
            int(parsed_meta_message.timestamp), tz=timezone.utc
        )

        meta_message_type = (
            parsed_meta_message.type
        )  # Tipo da Meta (text, image, interactive, etc.)
        internal_ct: str = "unknown"  # Nosso content_type interno
        message_content_for_dto: Optional[str] = None
        raw_attributes: Dict[str, Any] = {"original_meta_type": meta_message_type}

        if meta_message_type == "text":
            internal_ct = "text"
            message_content_for_dto = (
                parsed_meta_message.text.body if parsed_meta_message.text else None
            )
        elif meta_message_type == "image":
            internal_ct = "image"
            message_content_for_dto = (
                parsed_meta_message.image.caption if parsed_meta_message.image else None
            )
            if parsed_meta_message.image:
                raw_attributes["media_id"] = parsed_meta_message.image.id
                raw_attributes["mime_type"] = parsed_meta_message.image.mime_type
        elif meta_message_type == "audio":
            internal_ct = "audio"

            if parsed_meta_message.audio:
                raw_attributes["media_id"] = parsed_meta_message.audio.id
                raw_attributes["mime_type"] = parsed_meta_message.audio.mime_type
        elif meta_message_type == "document":
            internal_ct = "document"
            message_content_for_dto = (
                parsed_meta_message.document.caption
                if parsed_meta_message.document
                else None
            )
            if parsed_meta_message.document:
                raw_attributes["media_id"] = parsed_meta_message.document.id
                raw_attributes["mime_type"] = parsed_meta_message.document.mime_type
                raw_attributes["filename"] = parsed_meta_message.document.filename
        elif meta_message_type == "video":
            internal_ct = "video"
            message_content_for_dto = (
                parsed_meta_message.video.caption if parsed_meta_message.video else None
            )
            if parsed_meta_message.video:
                raw_attributes["media_id"] = parsed_meta_message.video.id
                raw_attributes["mime_type"] = parsed_meta_message.video.mime_type
        elif meta_message_type == "sticker":
            internal_ct = "sticker"
            if parsed_meta_message.sticker:
                raw_attributes["media_id"] = parsed_meta_message.sticker.id
                raw_attributes["mime_type"] = parsed_meta_message.sticker.mime_type
        elif meta_message_type == "location":
            internal_ct = "location"
            if parsed_meta_message.location:
                message_content_for_dto = (
                    f"{parsed_meta_message.location.name} ({parsed_meta_message.location.address})"
                    if parsed_meta_message.location.name
                    and parsed_meta_message.location.address
                    else parsed_meta_message.location.name
                    or parsed_meta_message.location.address
                    or f"Lat: {parsed_meta_message.location.latitude}, Lon: {parsed_meta_message.location.longitude}"
                )
                raw_attributes["latitude"] = parsed_meta_message.location.latitude
                raw_attributes["longitude"] = parsed_meta_message.location.longitude
                raw_attributes["name"] = parsed_meta_message.location.name
                raw_attributes["address"] = parsed_meta_message.location.address
        elif meta_message_type == "contacts":
            internal_ct = "contacts"
            # Você pode querer serializar os detalhes dos contatos para message_content_for_dto ou raw_attributes
            # message_content_for_dto = f"{len(parsed_meta_message.contacts_payload)} contatos compartilhados" # Exemplo
            # raw_attributes["contacts_payload"] = [c.model_dump() for c in parsed_meta_message.contacts_payload] # Se tiver contacts_payload
        elif meta_message_type == "interactive":
            # Resposta a List Message ou Reply Button
            if parsed_meta_message.interactive:
                if parsed_meta_message.interactive.type == "list_reply":
                    internal_ct = "interactive_list_reply"
                    message_content_for_dto = (
                        parsed_meta_message.interactive.list_reply.title
                    )
                    raw_attributes["interactive_payload"] = (
                        parsed_meta_message.interactive.model_dump()
                    )
                elif parsed_meta_message.interactive.type == "button_reply":
                    internal_ct = "interactive_button_reply"
                    message_content_for_dto = (
                        parsed_meta_message.interactive.button_reply.title
                    )
                    raw_attributes["interactive_payload"] = (
                        parsed_meta_message.interactive.model_dump()
                    )
                else:
                    internal_ct = f"interactive_{parsed_meta_message.interactive.type}"
                    raw_attributes["interactive_payload"] = (
                        parsed_meta_message.interactive.model_dump()
                    )

        elif meta_message_type == "button":  # Resposta a um Quick Reply de um template
            internal_ct = "button_template_reply"
            message_content_for_dto = (
                parsed_meta_message.button.text if parsed_meta_message.button else None
            )
            if parsed_meta_message.button:
                raw_attributes["button_payload"] = (
                    parsed_meta_message.button.payload
                )  # O payload do botão
        elif meta_message_type == "system":
            internal_ct = "system"
            message_content_for_dto = (
                parsed_meta_message.system.body
                if parsed_meta_message.system
                else "Mensagem do sistema"
            )
            if parsed_meta_message.system:
                raw_attributes["system_payload"] = (
                    parsed_meta_message.system.model_dump()
                )
        else:
            logger.warning(
                f"Transformer: Unhandled Meta message type for content: '{meta_message_type}'. Defaulting to 'unknown'."
            )
            internal_ct = "unknown"

        if parsed_meta_message.context:
            raw_attributes["context"] = parsed_meta_message.context.model_dump(
                exclude_none=True
            )

        internal_dto = InternalIncomingMessageDTO(
            account_id=account_id,
            inbox_id=inbox.id,
            contact_id=contact.id,
            conversation_id=conversation.id,
            external_message_id=external_message_id,
            sender_identifier=sender_wa_id,
            message_content=message_content_for_dto,
            internal_content_type=internal_ct,
            message_timestamp=message_timestamp,
            raw_message_attributes=raw_attributes,
            source_api="whatsapp_cloud",
        )

        await db.flush()
        logger.info(
            f"Successfully transformed Meta message {external_message_id} to InternalIncomingMessageDTO"
        )
        return internal_dto

    except Exception as e:
        logger.exception(f"Error during WhatsApp Cloud message transformation: {e}")
        return None
