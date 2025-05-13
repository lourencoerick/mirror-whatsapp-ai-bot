# app/schemas/whatsapp_cloud_config.py
import uuid
from typing import Optional
from pydantic import BaseModel, Field


# --- Base Schema ---
class WhatsAppCloudConfigBase(BaseModel):
    """Base Pydantic schema for WhatsApp Cloud API Configuration."""

    phone_number_id: str = Field(..., description="WhatsApp Cloud API Phone Number ID.")
    waba_id: str = Field(..., description="WhatsApp Business Account ID.")
    webhook_verify_token: str = Field(
        ..., description="Verify token for Meta webhook setup."
    )
    app_id: Optional[str] = Field(None, description="Meta App ID, if applicable.")


class WhatsAppCloudConfigCreateInput(WhatsAppCloudConfigBase):
    """Schema for providing data to create a WhatsApp Cloud API Configuration."""

    access_token: str = Field(
        ...,
        min_length=1,
        description="Raw System User Access Token for WhatsApp Cloud API.",
    )


# --- Schema for Storing/Internal Use (includes account_id, used by service to create DB record) ---
class WhatsAppCloudConfigCreateInternal(WhatsAppCloudConfigCreateInput):
    """Internal schema for creating WhatsAppCloudConfig, includes account_id."""

    account_id: uuid.UUID


# --- Schema for Reading/Returning a Configuration ---
class WhatsAppCloudConfigRead(WhatsAppCloudConfigBase):
    """Schema for reading/returning a WhatsApp Cloud API Configuration."""

    id: uuid.UUID
    account_id: uuid.UUID

    class Config:
        from_attributes = True
