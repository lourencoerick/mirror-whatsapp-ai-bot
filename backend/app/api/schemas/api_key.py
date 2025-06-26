# backend/app/api/schemas/api_key.py

from pydantic import BaseModel, Field
from typing import List
from uuid import UUID
from datetime import datetime


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(
        ...,
        description="A user-friendly name for the key.",
        examples=["Planilha de Vendas Q1"],
    )
    scopes: List[str] = Field(
        ...,
        description="A list of permission scopes for the key.",
        examples=[["sheets:trigger"]],
    )


class ApiKeyRead(BaseModel):
    """Schema for displaying an API key safely (without the secret)."""

    id: UUID
    name: str
    prefix: str
    last_four: str = Field(
        description="The last four characters of the key for identification."
    )
    scopes: List[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyReadWithSecret(ApiKeyRead):
    """
    Schema for returning the full, raw API key upon creation.
    This should only be used ONCE, immediately after generating the key.
    """

    raw_key: str = Field(
        description="The full, secret API key. Display this only once."
    )
