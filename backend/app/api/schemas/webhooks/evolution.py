from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


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


class EvolutionWebhookMessage(BaseModel):
    conversation: str


class EvolutionWebhookData(BaseModel):
    """Represents the 'data' data often nested in webhook payloads."""

    key: EvolutionWebhookKey
    pushName: str
    message: EvolutionWebhookMessage | Dict[str, Any]
    messageType: str
    messageTimestamp: int
    instanceId: str
    source: str


class EvolutionWebhookPayload(BaseModel):
    event: str
    instance: str
    data: ConnectionUpdateData | EvolutionWebhookData | Dict[str, Any]
    destination: str
    date_time: datetime
    server_url: str
    apikey: str
