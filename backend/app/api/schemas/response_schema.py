from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
import time
import re


class ResponseMessage(BaseModel):
    to: str = Field(..., description="Destination WhatsApp number, e.g., 5511999999999")
    original_message_id: str = Field(
        ..., description="ID of the original incoming message"
    )
    response_text: str = Field(
        ..., min_length=1, max_length=1000, description="Text to be sent in response"
    )
    provider: Literal["evolution", "whatsapp"] = Field(
        default="evolution", description="Message provider"
    )
    timestamp: float = Field(
        default_factory=lambda: time.time(),
        description="Unix timestamp of the response",
    )

    @validator("to")
    def validate_phone_number(cls, v):
        if not re.match(r"^\d{10,15}$", v):
            raise ValueError(
                "Invalid phone number format. Expected digits only (10-15 digits)."
            )
        return v

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "to": "5511999999999",
                "original_message_id": "MSG123",
                "response_text": "🤖 Auto-reply: 'Olá mundo'",
                "provider": "evolution",
                "timestamp": 1711234567.0,
            }
        }
