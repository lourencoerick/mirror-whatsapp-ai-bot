from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from app.models.conversation import ConversationStatusEnum


class InboxBase(BaseModel):
    id: Optional[UUID] = Field(
        None, description="Unique identifier for the inbox (UUID)"
    )
    name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the inbox"
    )
    channel_type: str = Field(..., description="Type of the channel (e.g., 'whatsapp')")
    channel_details: Optional[Dict[str, Any]] = Field(
        None, description="Channel specific configuration details (JSON)"
    )

    initial_conversation_status: Optional[ConversationStatusEnum] = Field(
        None,
        description="New default status for new conversations (OPEN or PENDING)",
    )
    enable_auto_assignment: Optional[bool] = Field(
        True, description="Enable automatic assignment for this inbox"
    )  # Default to True?

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "Sales WhatsApp",
                "channel_type": "whatsapp",
                "channel_details": {
                    "phone_number": "+15551234567",
                    "provider": "cloud",
                },
                "enable_auto_assignment": True,
            }
        }


# --- Schema for Creation ---
class InboxCreate(InboxBase):
    pass


# --- Schema for Update ---
class InboxUpdate(BaseModel):
    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="New name for the inbox"
    )
    channel_type: Optional[str] = Field(None, description="New type of the channel")
    channel_details: Optional[Dict[str, Any]] = Field(
        None, description="Updated channel specific configuration"
    )
    enable_auto_assignment: Optional[bool] = Field(
        None, description="Update auto assignment setting"
    )

    initial_conversation_status: Optional[ConversationStatusEnum] = Field(
        None,
        description="New default status for new conversations (OPEN or PENDING)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Support WhatsApp",
                "enable_auto_assignment": False,
            }
        }


# --- Schema for API Response ---
class InboxRead(InboxBase):
    id: UUID = Field(..., description="Unique identifier for the inbox")
    account_id: UUID = Field(
        ..., description="Identifier of the account this inbox belongs to"
    )
    initial_conversation_status: Optional[ConversationStatusEnum] = Field(
        None,
        description="New default status for new conversations (OPEN or PENDING)",
    )
    channel_id: Optional[str] = Field(
        None,
        description="Identifier used by the channel provider (e.g., instanceId, phone_number_id)",
    )

    associated_bot_agent_id: Optional[UUID] = Field(
        None,
        description="ID of the BotAgent currently associated with this inbox, if any.",
    )

    created_at: datetime = Field(
        ..., description="Timestamp when the inbox was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the inbox was last updated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "e8a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9f",
                "account_id": "f0a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9a",
                "name": "Sales WhatsApp",
                "initial_conversation_status": "OPEN",
                "channel_type": "whatsapp",
                "channel_id": "instance_xyz",
                "channel_details": {
                    "phone_number": "15551234567",
                    "provider": "cloud",
                },
                "associated_bot_agent_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "enable_auto_assignment": True,
                "created_at": "2023-10-27T10:00:00Z",
                "updated_at": "2023-10-27T11:00:00Z",
            }
        }
