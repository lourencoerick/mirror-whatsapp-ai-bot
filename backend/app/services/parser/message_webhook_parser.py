# app/services/parser/message_webhook_parser.py

from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from loguru import logger
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import ValidationError

from app.api.schemas.webhooks.whatsapp_cloud import (
    WhatsAppMessage as WhatsAppCloudMessageSchema,
)

from app.api.schemas.webhooks.evolution import (
    EvolutionWebhookPayload,
    EvolutionWebhookMessageData,
)  # Used for parsing the data part
from app.api.schemas.webhooks.evolution_message import (
    EvolutionMessageObject,
    EvolutionContextInfo,
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

from app.services.helper.contact import normalize_phone_number


def _get_internal_content_type_from_evolution(
    message_type: Optional[str],  # e.g., "imageMessage", "conversation"
    message_object: Optional[EvolutionMessageObject],  # Parsed message object
) -> str:
    """Maps Evolution API messageType and content to our internal content_type."""
    if not message_type or not message_object:
        return "unknown"

    if message_type == "conversation":
        return "text"
    if message_type == "extendedTextMessage":
        return "text"
    if message_type == "imageMessage":
        return "image"
    if message_type == "videoMessage":
        return "video"
    if message_type == "audioMessage":
        return "audio"
    if (
        message_type == "documentMessage"
        or message_type == "documentWithCaptionMessage"
    ):
        return "document"
    if message_type == "stickerMessage":
        return "sticker"
    if message_type == "locationMessage":
        return "location"
    if message_type == "buttonsResponseMessage":
        return "interactive_button_reply"
    if message_type == "listResponseMessage":
        return "interactive_list_reply"
    if message_type == "templateButtonReplyMessage":
        return "interactive_template_reply"  # Or just "template_reply"
    if message_type == "reactionMessage":
        return "reaction"
    # Add other types like contactsArrayMessage, productMessage etc.
    # if message_type == "contactMessage" or message_type == "contactsArrayMessage":
    #     return "contact"

    logger.warning(
        f"Unknown Evolution messageType for internal mapping: {message_type}. Defaulting to 'unknown'."
    )
    return "unknown"


async def transform_evolution_api_to_internal_dto(
    db: AsyncSession,
    internal_evolution_instance_uuid: str,
    raw_evolution_webhook_payload_dict: Dict[str, Any],
) -> Optional[InternalIncomingMessageDTO]:
    """
    Transforms a raw Evolution API webhook payload (for messages) into a
    standardized InternalIncomingMessageDTO using detailed Pydantic models.

    Args:
        db: The asynchronous database session.
        internal_evolution_instance_uuid: The UUID of our internal EvolutionInstance record.
        raw_evolution_webhook_payload_dict: The raw dictionary of the Evolution API
                                            webhook payload.

    Returns:
        An InternalIncomingMessageDTO if successful, otherwise None.
    """
    log_prefix = f"Transformer (EvoAPI|Pydantic|EvoInstanceUUID: {internal_evolution_instance_uuid}):"
    logger.info(f"{log_prefix} Starting transformation.")

    try:
        # The raw_evolution_webhook_payload_dict is assumed to be generally valid
        # from the webhook endpoint's EvolutionWebhookPayload validation.
        # We now parse the 'data' field specifically.

        # Extract the 'data' part of the payload.
        # The webhook handler should have ensured this is EvolutionWebhookMessageData for message events.
        data_dict = raw_evolution_webhook_payload_dict.get("data")
        if not isinstance(data_dict, dict):  # Basic check
            logger.error(
                f"{log_prefix} 'data' field is not a dictionary or is missing. Payload: {raw_evolution_webhook_payload_dict}"
            )
            return None

        # Parse the 'data' field into EvolutionWebhookMessageData
        try:
            evo_message_data = EvolutionWebhookMessageData.model_validate(data_dict)
        except ValidationError as e:
            logger.error(
                f"{log_prefix} Pydantic validation error for EvolutionWebhookMessageData: {e.errors()}. Data: {data_dict}"
            )
            return None

        # --- 0. Pre-checks and Basic Info ---
        event_type = raw_evolution_webhook_payload_dict.get("event")
        evolution_instance_name_from_payload = raw_evolution_webhook_payload_dict.get(
            "instance"
        )

        if (
            event_type == "messages.update"
            and evo_message_data.message
            and evo_message_data.message.reaction_message
        ):
            logger.info(f"{log_prefix} Processing a reaction message.")
            # Reaction handling logic will go here.
        elif evo_message_data.messageStubType == "REVOKE":
            logger.info(
                f"{log_prefix} Message (ID: {evo_message_data.key.id}) was revoked. Skipping DTO creation for now."
            )
            # TODO: Decide if REVOKE events should generate a DTO (e.g., type 'deleted')
            # or trigger a direct DB update to mark the original message as deleted.
            return None

        if (
            not evo_message_data.message
            or not evo_message_data.messageType
            or not evo_message_data.messageTimestamp
        ):
            # This can happen for some non-message updates or if message is empty.
            # For example, a message deletion sync event might not have 'message' object.
            if evo_message_data.messageStubType:  # e.g. REVOKE already handled above
                logger.info(
                    f"{log_prefix} Event with messageStubType '{evo_message_data.messageStubType}' and no message object. Key ID: {evo_message_data.key.id}. Skipping DTO."
                )
                return None
            logger.warning(
                f"{log_prefix} Core message fields (message object, messageType, or timestamp) missing in evo_message_data. Key ID: {evo_message_data.key.id}. Data: {evo_message_data.model_dump_json(exclude_none=True)}"
            )
            return None

        external_message_id = evo_message_data.key.id
        remote_jid = evo_message_data.key.remoteJid
        is_from_me = evo_message_data.key.fromMe
        message_timestamp_unix = evo_message_data.messageTimestamp
        raw_message_type = evo_message_data.messageType  # e.g. "imageMessage"

        # The actual sender in a group, if present. Otherwise, it's a direct message.
        participant_jid = evo_message_data.key.participant

        direction = "out" if is_from_me else "in"

        if direction == "out":
            logger.info(
                f"{log_prefix} Parsed message is outbound (ID: {external_message_id}). Skipping DTO creation for incoming pipeline."
            )
            return None  # Or handle outbound differently if needed.

        # --- 1. Find associated Account and Inbox ---
        inbox_details = (
            await inbox_repo.find_inbox_and_account_by_evolution_instance_id(
                db, evolution_instance_id=UUID(internal_evolution_instance_uuid)
            )
        )

        if not inbox_details:
            logger.error(
                f"No active inbox/account for Instance ID: {internal_evolution_instance_uuid}"
            )
            return None

        inbox: Inbox = inbox_details.inbox
        account: Account = inbox_details.account
        account_id: UUID = account.id
        inbox_id: UUID = inbox.id
        logger.info(f"Transformer: Using Inbox ID {inbox.id}, Account ID {account_id}")

        # --- 2. Determine Actual Sender and Normalize ---
        # If participant_jid is present, it's a group message, and participant_jid is the sender.
        # Otherwise (direct message), remote_jid is the sender.
        actual_sender_jid = participant_jid if participant_jid else remote_jid

        # remote_jid is the chat JID (user JID in 1:1, group JID in group chat)
        # actual_sender_jid is the user who sent the message.

        sender_phone_raw = (
            actual_sender_jid.split("@")[0]
            if "@" in actual_sender_jid
            else actual_sender_jid
        )
        normalized_sender_phone = normalize_phone_number(sender_phone_raw)
        sender_profile_name = (
            evo_message_data.pushName
        )  # Usually the pushName of the actual_sender_jid

        logger.debug(
            f"{log_prefix} Chat JID (remoteJid): {remote_jid}, Actual Sender JID: {actual_sender_jid}, Normalized Phone: {normalized_sender_phone}, Profile Name: {sender_profile_name}"
        )

        # --- 3. Get or Create Contact (for the actual sender) ---
        contact = await contact_repo.find_contact_by_identifier(
            db=db, identifier=normalized_sender_phone, account_id=account_id
        )
        if not contact:
            contact_create_data = ContactCreateSchema(
                phone_number=normalized_sender_phone, name=sender_profile_name
            )
            contact = await contact_repo.create_contact(
                db=db, contact_data=contact_create_data, account_id=account_id
            )
            logger.info(
                f"{log_prefix} Created new Contact ID {contact.id} for {normalized_sender_phone}"
            )
        elif sender_profile_name and (
            not contact.name or contact.name != sender_profile_name
        ):
            contact.name = sender_profile_name
            db.add(contact)
            logger.info(
                f"{log_prefix} Updated Contact ID {contact.id} with name '{sender_profile_name}'"
            )
        logger.info(
            f"{log_prefix} Using Contact ID {contact.id} for sender {actual_sender_jid}"
        )

        # --- 4. Get or Create ContactInbox ---
        # The source_id for ContactInbox should be unique for this contact on this inbox.
        # Using actual_sender_jid is a good candidate.
        contact_inbox = await contact_repo.get_or_create_contact_inbox(
            db=db,
            account_id=account_id,
            contact_id=contact.id,
            inbox_id=inbox_id,
            source_id=actual_sender_jid,
        )
        logger.info(f"{log_prefix} Using ContactInbox ID {contact_inbox.id}")

        # --- 5. Get or Create Conversation ---
        # Conversation is usually between the bot (inbox) and the chat_jid (remote_jid).
        # If it's a group, the conversation is with the group. The contact above is the participant.
        initial_conv_status = (
            inbox.initial_conversation_status or ConversationStatusEnum.PENDING
        )

        # For conversations, we typically use an identifier for the chat itself (remote_jid)
        # The contact_inbox links the specific sender (participant) to this inbox.
        # A conversation can have multiple participants if you model it that way, or be simpler.
        # For now, let's assume get_or_create_conversation uses contact_inbox_id which is tied to the *sender*.
        # This means a "conversation" is with a specific user, even in a group context from this perspective.
        # Alternative: conversation could be based on remote_jid (groupJID) directly. This needs careful thought.
        # Let's stick to contact_inbox_id for now, implies conversation is with the message author.
        conversation = await conversation_repo.get_or_create_conversation(
            db=db,
            account_id=account_id,
            inbox_id=inbox_id,
            contact_inbox_id=contact_inbox.id,
            status=initial_conv_status,
        )
        if conversation.status == ConversationStatusEnum.CLOSED:
            conversation.status = initial_conv_status
            conversation.unread_agent_count = 0
            db.add(conversation)
        logger.info(
            f"{log_prefix} Using Conversation ID {conversation.id} (Status: {conversation.status.value})"
        )

        # --- 6. Extract Content and Attributes from Parsed Message Object ---
        evo_msg_obj: EvolutionMessageObject = (
            evo_message_data.message
        )  # This is already parsed by Pydantic

        message_content_for_dto: Optional[str] = None
        internal_ct = _get_internal_content_type_from_evolution(
            raw_message_type, evo_msg_obj
        )

        content_attributes: Dict[str, Any] = {
            "provider": "evolution",
            "evolution_instance_name": evolution_instance_name_from_payload,
            "internal_evolution_instance_uuid": internal_evolution_instance_uuid,
            "raw_message_type": raw_message_type,  # Original type from Evolution
            "push_name": sender_profile_name,  # Push name of the sender
            "is_group_message": bool(participant_jid),
            "group_jid": (
                remote_jid if participant_jid else None
            ),  # Store group JID if it's a group msg
            "participant_jid": participant_jid,  # Actual sender in group, or None
            # Other common fields
            "message_id_on_provider": external_message_id,
        }

        context_info_payload: Optional[EvolutionContextInfo] = None

        if internal_ct == "text":
            if evo_msg_obj.extended_text_message:
                message_content_for_dto = evo_msg_obj.extended_text_message.text
                context_info_payload = evo_msg_obj.extended_text_message.context_info
            elif evo_msg_obj.conversation:  # Simple text
                message_content_for_dto = evo_msg_obj.conversation
        elif internal_ct == "image" and evo_msg_obj.image_message:
            message_content_for_dto = evo_msg_obj.image_message.caption
            content_attributes.update(
                evo_msg_obj.image_message.model_dump(exclude_none=True, by_alias=True)
            )
            context_info_payload = evo_msg_obj.image_message.context_info
        elif internal_ct == "video" and evo_msg_obj.video_message:
            message_content_for_dto = evo_msg_obj.video_message.caption
            content_attributes.update(
                evo_msg_obj.video_message.model_dump(exclude_none=True, by_alias=True)
            )
            context_info_payload = evo_msg_obj.video_message.context_info
        elif internal_ct == "audio" and evo_msg_obj.audio_message:
            # Audio typically doesn't have a caption in Evolution payload structure
            content_attributes.update(
                evo_msg_obj.audio_message.model_dump(exclude_none=True, by_alias=True)
            )
            context_info_payload = evo_msg_obj.audio_message.context_info
        elif internal_ct == "document":
            doc_msg = (
                evo_msg_obj.document_message
                or evo_msg_obj.document_with_caption_message
            )
            if doc_msg:
                message_content_for_dto = doc_msg.caption  # May be None
                content_attributes.update(
                    doc_msg.model_dump(exclude_none=True, by_alias=True)
                )
                context_info_payload = doc_msg.context_info
        elif internal_ct == "sticker" and evo_msg_obj.sticker_message:
            content_attributes.update(
                evo_msg_obj.sticker_message.model_dump(exclude_none=True, by_alias=True)
            )
            context_info_payload = evo_msg_obj.sticker_message.context_info
        elif internal_ct == "location" and evo_msg_obj.location_message:
            loc = evo_msg_obj.location_message
            message_content_for_dto = (
                loc.name
                or loc.address
                or f"Lat: {loc.degrees_latitude}, Lon: {loc.degrees_longitude}"
            )
            content_attributes.update(loc.model_dump(exclude_none=True, by_alias=True))
            context_info_payload = evo_msg_obj.location_message.context_info
        elif (
            internal_ct == "interactive_button_reply"
            and evo_msg_obj.buttons_response_message
        ):
            resp = evo_msg_obj.buttons_response_message
            message_content_for_dto = resp.selected_display_text
            content_attributes["selected_button_id"] = resp.selected_button_id
            content_attributes["response_type"] = resp.type
            context_info_payload = resp.context_info
        elif (
            internal_ct == "interactive_list_reply"
            and evo_msg_obj.list_response_message
        ):
            resp = evo_msg_obj.list_response_message
            message_content_for_dto = resp.title
            content_attributes["selected_row_id"] = (
                resp.single_select_reply.selected_row_id
            )
            content_attributes["description"] = resp.description
            context_info_payload = resp.context_info
        elif (
            internal_ct == "interactive_template_reply"
            and evo_msg_obj.template_button_reply_message
        ):
            resp = evo_msg_obj.template_button_reply_message
            message_content_for_dto = resp.selected_display_text
            content_attributes["selected_id"] = (
                resp.selected_id
            )  # This is the button's payload
            content_attributes["selected_index"] = resp.selected_index
            context_info_payload = resp.context_info
        elif internal_ct == "reaction" and evo_msg_obj.reaction_message:
            react = evo_msg_obj.reaction_message
            message_content_for_dto = react.text  # The emoji or empty string
            content_attributes["reacted_message_key"] = (
                react.key
            )  # Key of the message being reacted to
            content_attributes["is_removing_reaction"] = react.text == ""
            # Reactions don't typically have their own context_info in the same way other messages do

        if context_info_payload:
            content_attributes["reply_context"] = context_info_payload.model_dump(
                exclude_none=True, by_alias=True
            )
            # If it's a reply, the 'quoted_message_id' and 'participant' (original sender) are useful.
            if context_info_payload.quoted_message_id:
                content_attributes["in_reply_to_message_id"] = (
                    context_info_payload.quoted_message_id
                )

        # --- 7. Construct InternalIncomingMessageDTO ---
        message_timestamp_dt = datetime.fromtimestamp(
            message_timestamp_unix, tz=timezone.utc
        )

        internal_dto = InternalIncomingMessageDTO(
            account_id=account_id,
            inbox_id=inbox_id,
            contact_id=contact.id,  # Contact of the actual sender
            conversation_id=conversation.id,
            external_message_id=external_message_id,
            sender_identifier=normalized_sender_phone,  # Normalized phone of the actual sender
            message_content=message_content_for_dto,
            internal_content_type=internal_ct,
            message_timestamp=message_timestamp_dt,
            raw_message_attributes=content_attributes,
            source_api="whatsapp_evolution",
        )

        logger.info(
            f"{log_prefix} Successfully transformed Evolution message (ExtID: {external_message_id}) to DTO."
        )
        logger.debug(
            f"{log_prefix} DTO: {internal_dto.model_dump_json(indent=2, exclude_none=True)}"
        )
        return internal_dto

    except (
        ValidationError
    ) as e_val:  # Catch Pydantic validation errors during specific parsing
        logger.error(
            f"{log_prefix} Pydantic validation error during detailed parsing: {e_val.errors()}. Payload: {raw_evolution_webhook_payload_dict}"
        )
        return None
    except Exception as e:
        logger.exception(
            f"{log_prefix} Error during Evolution API message transformation: {e}"
        )
        return None


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
