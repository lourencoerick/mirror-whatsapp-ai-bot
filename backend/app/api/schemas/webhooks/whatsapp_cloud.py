from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID


# --- Internal Schemas for Messages ---
class WhatsAppErrorDetail(BaseModel):
    code: int
    title: str
    message: Optional[str] = None
    error_data: Optional[Dict[str, Any]] = Field(None, alias="error_data")


class WhatsAppProfile(BaseModel):
    name: str


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str = Field(..., description="Sender's WhatsApp ID (phone number)")


class WhatsAppMessageText(BaseModel):
    body: str


class WhatsAppMessageContext(BaseModel):
    from_number: Optional[str] = Field(
        None,
        alias="from",
        description="Original sender of the message being replied to",
    )
    id: Optional[str] = Field(None, description="WAMID of the message being replied to")


class WhatsAppMessage(BaseModel):
    from_number: str = Field(..., alias="from", description="Sender's phone number")
    id: str = Field(..., description="WhatsApp Message ID (WAMID)")
    timestamp: str  # Usually a Unix timestamp string

    type: Literal[
        "text",
        "image",
        "audio",
        "video",
        "document",
        "sticker",
        "location",
        "contacts",
        "interactive",
        "button_reply",  # For when a quick reply button is clicked
        "order",
        "system",
        "unknown",
        "ephemeral",
    ]

    # Type-specific fields (add more as needed)
    text: Optional[WhatsAppMessageText] = None
    # image: Optional[WhatsAppMediaPayload] = None  # Define WhatsAppMediaPayload
    # audio: Optional[WhatsAppMediaPayload] = None
    # document: Optional[WhatsAppMediaPayload] = None
    # interactive: Optional[WhatsAppInteractivePayload] = None  # Define WhatsAppInteractivePayload
    # button: Optional[WhatsAppButtonReplyPayload] = None  # For template button replies

    context: Optional[WhatsAppMessageContext] = (
        None  # To identify if it's a reply message
    )


# --- Internal Schemas for Message Status (if you handle them in the same payload) ---
class WhatsAppMessageStatus(BaseModel):
    id: str = Field(
        ..., description="WAMID of the message whose status is being updated"
    )
    status: Literal[
        "sent", "delivered", "read", "failed", "deleted"
    ]  # Add other statuses if needed
    timestamp: str
    recipient_id: str = Field(
        ..., description="Recipient's phone number (who the message was sent to)"
    )
    # conversation: Optional[Dict[str, Any]] = None  # May include conversation details
    # pricing: Optional[Dict[str, Any]] = None  # May include pricing details
    errors: Optional[List[Dict[str, Any]]] = None  # If status is 'failed'


# --- Main Webhook Structure ---
class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str = Field(
        ..., description="Your WhatsApp Business Phone Number ID"
    )


class WhatsAppValue(BaseModel):
    messaging_product: Literal["whatsapp"]
    metadata: WhatsAppMetadata
    contacts: Optional[List[WhatsAppContact]] = None  # Present for received messages
    messages: Optional[List[WhatsAppMessage]] = None  # Present for received messages
    statuses: Optional[List[WhatsAppMessageStatus]] = (
        None  # Present for outbound message status updates
    )
    errors: Optional[List[WhatsAppErrorDetail]] = (
        None  # Define WhatsAppErrorPayload if needed
    )


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: Literal["messages"]  # Usually "messages" for new messages and status updates


class WhatsAppEntry(BaseModel):
    id: str = Field(..., description="Your WhatsApp Business Account (WABA) ID")
    changes: List[WhatsAppChange]


class WhatsAppCloudWebhookPayload(BaseModel):
    object: Literal["whatsapp_business_account"]
    entry: List[WhatsAppEntry]

    # Helper to extract the first message (if present)
    # Can be useful, but may also be handled in the processing service
    def get_first_message(self) -> Optional[WhatsAppMessage]:
        try:
            return self.entry[0].changes[0].value.messages[0]
        except (IndexError, TypeError, AttributeError):
            return None

    def get_first_status_update(self) -> Optional[WhatsAppMessageStatus]:
        try:
            return self.entry[0].changes[0].value.statuses[0]
        except (IndexError, TypeError, AttributeError):
            return None

    def get_phone_number_id(self) -> Optional[str]:
        try:
            return self.entry[0].changes[0].value.metadata.phone_number_id
        except (IndexError, TypeError, AttributeError):
            return None
