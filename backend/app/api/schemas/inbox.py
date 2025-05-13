# app/api/schemas/inbox.py

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.api.schemas.evolution_instance import (
    EvolutionChannelDetailsInput,
    EvolutionInstanceRead,
)
from app.api.schemas.whatsapp_cloud_config import (
    WhatsAppCloudConfigCreateInput,
    WhatsAppCloudConfigRead,
)
from app.models.channels.channel_types import ChannelTypeEnum
from app.models.conversation import ConversationStatusEnum


class InboxBase(BaseModel):
    """Base schema for an Inbox, containing common fields."""

    id: Optional[UUID] = Field(
        None, description="Unique identifier for the inbox (UUID)."
    )
    name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the inbox."
    )
    channel_type: ChannelTypeEnum = Field(
        ..., description="Type of the communication channel."
    )
    channel_details: Optional[Dict[str, Any]] = Field(
        None, description="Legacy or UI-specific channel configuration details (JSON)."
    )
    initial_conversation_status: Optional[ConversationStatusEnum] = Field(
        None,
        description="Default status for new conversations (e.g., OPEN, PENDING, BOT).",
    )
    enable_auto_assignment: Optional[bool] = Field(
        True, description="Enable automatic assignment of conversations for this inbox."
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "Sales WhatsApp",
                "channel_type": "whatsapp_cloud",
                "channel_details": {"ui_hint": "Use blue theme"},
                "initial_conversation_status": "OPEN",
                "enable_auto_assignment": True,
            }
        }


class InboxCreate(InboxBase):
    """
    Schema for creating a new Inbox.
    Includes common inbox fields and specific configurations for the chosen channel type.
    """

    evolution_instance_to_link: Optional[EvolutionChannelDetailsInput] = Field(
        None,
        description="Configuration for linking an existing Evolution API instance.",
    )
    whatsapp_cloud_config_to_create: Optional[WhatsAppCloudConfigCreateInput] = Field(
        None, description="Configuration for creating a new WhatsApp Cloud API setup."
    )

    @model_validator(mode="after")
    def check_channel_specific_config(cls, data: "InboxCreate") -> "InboxCreate":
        """Ensures correct channel-specific configuration is provided based on channel_type."""
        if data.channel_type == ChannelTypeEnum.WHATSAPP_EVOLUTION:
            if not data.evolution_instance_to_link:
                raise ValueError(
                    "evolution_instance_to_link must be provided for channel_type WHATSAPP_EVOLUTION."
                )
            if data.whatsapp_cloud_config_to_create:
                raise ValueError(
                    "whatsapp_cloud_config_to_create must not be provided for WHATSAPP_EVOLUTION."
                )
        elif data.channel_type == ChannelTypeEnum.WHATSAPP_CLOUD:
            if not data.whatsapp_cloud_config_to_create:
                raise ValueError(
                    "whatsapp_cloud_config_to_create must be provided for channel_type WHATSAPP_CLOUD."
                )
            if data.evolution_instance_to_link:
                raise ValueError(
                    "evolution_instance_to_link must not be provided for WHATSAPP_CLOUD."
                )
        elif data.channel_type == ChannelTypeEnum.SIMULATION:
            if data.evolution_instance_to_link or data.whatsapp_cloud_config_to_create:
                raise ValueError(
                    "No specific channel configuration should be provided for SIMULATION type."
                )
        else:  # Handles unknown or future channel types not yet explicitly configured
            if data.evolution_instance_to_link or data.whatsapp_cloud_config_to_create:
                raise ValueError(
                    f"No specific channel configuration should be provided for channel_type {data.channel_type}."
                )
        return data


class InboxUpdate(BaseModel):
    """
    Schema for updating an existing Inbox.
    Allows partial updates to common inbox fields.
    """

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="New name for the inbox."
    )
    channel_details: Optional[Dict[str, Any]] = Field(
        None, description="Updated legacy or UI-specific channel configuration."
    )
    initial_conversation_status: Optional[ConversationStatusEnum] = Field(
        None, description="New default status for new conversations."
    )
    enable_auto_assignment: Optional[bool] = Field(
        None, description="Update auto assignment setting for this inbox."
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "Support WhatsApp Renamed",
                "enable_auto_assignment": False,
                "initial_conversation_status": "PENDING",
            }
        }


class InboxRead(InboxBase):
    """
    Schema for representing an Inbox in API responses.
    Includes common fields and populated channel-specific configuration.
    """

    id: UUID  # Overridden from InboxBase to be non-optional
    account_id: UUID = Field(
        ..., description="Identifier of the account this inbox belongs to."
    )
    channel_id: Optional[str] = Field(
        None,
        description="Identifier used by the channel provider (e.g., Evolution instance_name, WhatsApp phone_number_id).",
    )
    associated_bot_agent_id: Optional[UUID] = Field(
        None,
        description="ID of the BotAgent currently associated with this inbox, if any.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the inbox was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the inbox was last updated."
    )

    evolution_instance: Optional[EvolutionInstanceRead] = Field(
        None, description="Details of the linked Evolution API instance, if applicable."
    )
    whatsapp_cloud_config: Optional[WhatsAppCloudConfigRead] = Field(
        None,
        description="Details of the linked WhatsApp Cloud API configuration, if applicable.",
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "e8a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9f",
                "account_id": "f0a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9a",
                "name": "Sales WhatsApp Cloud",
                "channel_type": "whatsapp_cloud",
                "channel_id": "15551234567",
                "channel_details": {"ui_hint": "Use blue theme"},
                "initial_conversation_status": "OPEN",
                "enable_auto_assignment": True,
                "associated_bot_agent_id": None,
                "created_at": "2023-10-27T10:00:00Z",
                "updated_at": "2023-10-27T11:00:00Z",
                "evolution_instance": None,
                "whatsapp_cloud_config": {
                    "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                    "account_id": "f0a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9a",
                    "phone_number_id": "15551234567",
                    "waba_id": "waba_id_example",
                    "app_id": "app_id_example",
                    "webhook_verify_token": "your_verify_token_here",  # This should be optional in read
                },
            }
        }
