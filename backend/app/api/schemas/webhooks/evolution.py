from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from .evolution_message import EvolutionMessageObject, EvolutionReactionMessage


# --- Models for Webhook Payloads (Input Validation) ---
class EvolutionWebhookInstanceData(BaseModel):
    """Represents the 'instance' data often nested in webhook payloads."""

    instance: Optional[str] = None
    state: Optional[str] = None
    statusReason: Optional[int] = None


class EvolutionWebhookConnectionData(BaseModel):
    """Data specific to 'connection.update' events."""

    state: str  # e.g., "open", "connecting", "close"


class EvolutionWebhookQRCodeData(BaseModel):
    """Data specific to 'qrcode.updated' events."""

    base64: str  # The new QR code data


class ConnectionUpdateData(BaseModel):
    instance: str
    state: str
    statusReason: Optional[int] = None
    wuid: Optional[str] = None
    profilePictureUrl: Optional[str] = None


class EvolutionWebhookKey(BaseModel):
    """Represents the 'key' data often nested in webhook payloads."""

    remoteJid: str
    fromMe: bool
    id: str
    participant: Optional[str] = None


class EvolutionWebhookMessage(BaseModel):
    conversation: str


class EvolutionWebhookMessageData(
    BaseModel
):  # Renamed from EvolutionWebhookData for clarity
    """
    Represents the 'data' field for message events like 'messages.upsert' or 'messages.update'.
    """

    key: EvolutionWebhookKey
    pushName: Optional[str] = None
    message: Optional[EvolutionMessageObject] = (
        None  # Use the detailed message object wrapper. Can be None for REVOKE.
    )
    messageType: Optional[str] = (
        None  # e.g., "imageMessage", "conversation", "reactionMessage". Can be None for REVOKE.
    )
    messageTimestamp: Optional[int] = None  # Unix timestamp. Can be None for REVOKE.
    instanceId: str
    source: str
    # For messages.update (e.g. reactions, edits).
    # Evolution sometimes sends a limited structure for updates.
    # The 'message' field might contain 'reactionMessage' directly.
    # Or, for message edits, it might send a new 'message' object with the edited content.
    # This structure should also accommodate 'messageStubType' for REVOKE events.
    messageStubType: Optional[str] = None  # e.g., "REVOKE"
    messageStubParameters: Optional[List[str]] = None

    class Config:
        extra = "ignore"  # Be flexible with extra fields from Evolution


class EvolutionWebhookPayload(BaseModel):
    event: str
    instance: str
    data: ConnectionUpdateData | EvolutionWebhookMessageData | Dict[str, Any]
    destination: str
    date_time: datetime
    server_url: str
    apikey: str
