# backend/app/schemas/integrations.py

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Dict, Any, Optional


class InitialContextSchema(BaseModel):
    """
    Defines the structure for the initial context data provided by an integration.
    """

    source: str = Field(
        ..., description="The source of the lead (e.g., 'Google Sheet: Vendas Q4')."
    )
    product_of_interest: str = Field(
        ..., description="The product or service the contact is interested in."
    )
    notes: str = Field("", description="Any additional notes about the lead.")


class SheetsTriggerPayload(BaseModel):
    """
    Pydantic schema for validating the payload from the Google Sheets trigger.
    This is the contract our API expects from the Apps Script.
    """

    contact_phone: str = Field(
        ...,
        description="The contact's phone number, including country code.",
        examples=["+5511987654321"],
    )
    contact_name: str = Field(
        ..., description="The name of the contact.", examples=["Ana Souza"]
    )

    contact_email: Optional[EmailStr] = Field(
        default=None,
        description="The email of the contact.",
        examples=["ana@exempl.com"],
    )
    initial_context: InitialContextSchema = Field(
        ..., description="Contextual information about the lead."
    )

    @field_validator("contact_email", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Optional[Any]:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value
