# src/schemas/evolution_instance.py

from uuid import UUID
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import datetime

from app.models.channels.evolution_instance import EvolutionInstanceStatus


# --- Models for API Responses ---
class EvolutionInstanceRead(BaseModel):
    """
    Schema for response when creating/retrieving basic Evolution Instance info.
    This is what our platform returns, containing OUR identifiers.
    """

    id: UUID = Field(
        ..., description="Platform's unique identifier for this logical instance."
    )
    instance_name: str = Field(
        ...,
        description="Unique name identifier used on the shared Evolution API server.",
    )
    shared_api_url: HttpUrl = Field(
        ..., description="Base URL of the shared Evolution API server."
    )
    logical_token_encrypted: str = Field(..., description="Encrypted API key")
    webhook_url: HttpUrl = Field(
        ..., description="Webhook URL configured to receive events for this instance."
    )
    status: EvolutionInstanceStatus = Field(
        ..., description="Current status tracked by the platform."
    )
    account_id: UUID = Field(..., description="Owning account ID within the platform.")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvolutionInstanceQRCodeResponse(BaseModel):
    """
    Schema for the response of the GET .../qrcode endpoint.
    Contains status and QR code data fetched from the shared Evolution server.
    """

    instance_id: UUID = Field(
        ..., description="Platform's unique identifier for context."
    )
    connection_status: Optional[str] = Field(
        None,
        description="Connection state reported by Evolution API (e.g., 'open', 'connecting', 'close').",
    )
    qrcode: Optional[str] = Field(
        None,
        description="QR code string, if available and not connected.",
    )
    qrcode_base64: Optional[str] = Field(
        None,
        description="Base64 encoded QR code string, if available and not connected.",
    )
    detail: Optional[str] = Field(
        None,
        description="Additional detail or context message (e.g., 'Already connected').",
    )


# --- Models for Inbox Creation Input ---
class EvolutionChannelDetailsInput(BaseModel):
    """
    Schema representing the channel-specific details needed when creating an Inbox
    of type 'whatsapp_evolution_api'. Contains OUR platform ID.
    """

    # This is the `id` from our EvolutionInstance table (UUID)
    platform_instance_id: UUID = Field(
        ...,
        description="The platform's unique ID for the configured Evolution instance.",
    )
