# app/api/schemas/internal_messaging.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class InternalIncomingMessageDTO(BaseModel):
    """
    Standardized DTO representing an incoming message after transformation,
    ready to be processed by the main business logic.
    """

    # Identifiers from our platform (filled in by the transformation function)
    account_id: UUID
    inbox_id: UUID
    contact_id: UUID
    conversation_id: UUID

    # Original message data
    external_message_id: str = Field(
        ...,
        description="Message ID on the source platform (e.g., WAMID, Evolution ID).",
    )
    sender_identifier: str = Field(
        ...,
        description="Sender identifier on the source platform (e.g., phone number, remoteJid).",
    )

    message_content: Optional[str] = Field(
        None, description="Main content of the message (text, media caption, etc.)."
    )

    internal_content_type: str = Field(
        ...,
        description="Normalized internal message type (e.g., text, image, audio).",
    )

    message_timestamp: datetime = Field(
        ..., description="Timestamp of the original message (UTC)."
    )

    # Raw or platform-specific attributes that may be useful for further processing
    # or for storing complete metadata.
    # E.g.: media ID for download, reply context, clicked buttons, etc.
    raw_message_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw or platform-specific attributes from the original message.",
    )

    source_api: Literal[
        "whatsapp_cloud", "whatsapp_evolution", "simulation", "integration_trigger"
    ] = Field(..., description="Source API of the message, for reference.")

    is_private: bool = Field(
        default=False,
        description="If true, this message is a system-generated note or event, not a real message from the contact.",
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "account_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "inbox_id": "b1c2d3e4-f5g6-7890-1234-567890abcdef",
                "contact_id": "c1d2e3f4-g5h6-7890-1234-567890abcdef",
                "conversation_id": "d1e2f3g4-h5i6-7890-1234-567890abcdef",
                "external_message_id": "wamid.XYZ",
                "sender_identifier": "16505551234",
                "message_content": "Hello, I’d like more information.",
                "internal_content_type": "text",
                "message_timestamp": "2023-10-27T10:30:00Z",
                "raw_message_attributes": {
                    "whatsapp_context": {"from": "16505550000", "id": "wamid.PREVIOUS"}
                },
                "source_api": "whatsapp_cloud",
                "is_private": "False",
            }
        }
