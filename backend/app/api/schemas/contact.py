import uuid
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator, ValidationInfo
from datetime import datetime

# Basic regex for phone numbers (allows digits, +, -, spaces, parentheses) - refine as needed
PHONE_REGEX = re.compile(r"^[0-9\+\-\s\(\)]+$")


class ContactBase(BaseModel):
    """Base schema for contact attributes."""

    id: Optional[uuid.UUID] = Field(
        None, description="Unique identifier for the contact (UUID)"
    )
    name: Optional[str] = Field(None, max_length=255, description="Contact's full name")
    email: Optional[EmailStr] = Field(
        None, description="Contact's email address (must be unique within the account)"
    )
    phone_number: str = Field(
        ..., max_length=255, description="Contact's primary phone number (required)"
    )
    identifier: Optional[str] = Field(
        None,
        max_length=255,
        description="Internal identifier (e.g., normalized phone or WhatsApp ID)",
    )
    profile_picture_url: Optional[str] = Field(
        None, max_length=255, description="URL of the contact's profile picture"
    )
    additional_attributes: Optional[Dict[str, Any]] = Field(
        None, description="Additional custom key-value attributes"
    )

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate that phone number contains mainly digits and possibly +,-,(),space."""
        if not v:
            raise ValueError("Phone number cannot be empty")
        if not PHONE_REGEX.match(v):
            raise ValueError("Phone number contains invalid characters")
        normalized_v = re.sub(r"[()\-\s]", "", v)
        return normalized_v

    class Config:
        from_attributes = True


class ContactCreate(ContactBase):
    """Schema used for creating a new contact via the API."""

    pass


class ContactUpdate(BaseModel):
    """Schema used for updating an existing contact via the API. All fields are optional."""

    name: Optional[str] = Field(None, max_length=255, description="Contact's full name")
    email: Optional[EmailStr] = Field(
        None, description="Contact's email address (must be unique within the account)"
    )
    phone_number: Optional[str] = Field(
        None, max_length=255, description="Contact's primary phone number"
    )
    profile_picture_url: Optional[str] = Field(
        None, max_length=255, description="URL of the contact's profile picture"
    )
    additional_attributes: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional custom key-value attributes (will merge with existing)",
    )

    # Pydantic V2 style validator for optional phone_number
    @field_validator("phone_number")
    @classmethod
    def validate_phone_number_optional(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number if provided."""
        if v is not None:
            if not v:
                # This case might be redundant if '' is caught by regex, but good for clarity
                raise ValueError("Phone number cannot be empty if provided")
            if not PHONE_REGEX.match(v):
                raise ValueError("Phone number contains invalid characters")
            normalized_v = re.sub(r"[()\-\s]", "", v)
            return normalized_v
        return v

    class Config:
        from_attributes = True


class ContactRead(ContactBase):
    """Schema used for returning contact data via the API."""

    id: uuid.UUID = Field(..., description="Unique identifier for the contact")
    account_id: uuid.UUID = Field(
        ..., description="Identifier of the account this contact belongs to"
    )
    identifier: Optional[str] = Field(
        None,
        max_length=255,
        description="Internal identifier (e.g., normalized phone or WhatsApp ID)",
    )
    source_id: Optional[str] = Field(
        None,
        max_length=255,
        description="Identifier for the source system where the contact originated",
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the contact was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the contact was last updated"
    )

    class Config:
        from_attributes = True


class PaginatedContactRead(BaseModel):
    """Schema for returning a paginated list of contacts."""

    total: int = Field(..., description="Total number of contacts matching the query")
    items: list[ContactRead] = Field(
        ..., description="List of contacts for the current page"
    )

    class Config:
        from_attributes = True
