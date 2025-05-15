from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime


class MessageCreatePayload(BaseModel):
    content: str = Field(..., example="Olá, tudo bem?")


class MessageCreate(BaseModel):
    account_id: UUID
    inbox_id: UUID
    contact_id: UUID
    conversation_id: UUID
    source_id: str  # external ID of the message
    user_id: Optional[UUID] = None

    direction: Literal["in", "out"]
    status: Literal[
        "received", "sent", "pending", "processing", "failed", "delivered"
    ] = "received"
    message_timestamp: datetime  # the moment when the user sent the message
    private: Optional[bool] = False
    content: Optional[str] = None
    content_type: Literal["text", "image", "audio", "file", "video", "conversation"] = (
        "text"
    )
    content_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)
    triggering_message_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: UUID
    content: Optional[str]
    direction: str
    message_type: str
    content_type: Optional[str]
    sent_at: Optional[datetime]
