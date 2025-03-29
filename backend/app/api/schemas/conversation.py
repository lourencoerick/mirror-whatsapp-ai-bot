from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LastMessage(BaseModel):
    content: str


class ConversationResponse(BaseModel):
    id: UUID
    phone_number: str
    updated_at: datetime
    profile_picture_url: Optional[str]
    contact_name: Optional[str]
    last_message_at: Optional[datetime]
    last_message: Optional[LastMessage]

    class Config:
        from_attributes = True


class StartConversationRequest(BaseModel):
    phone_number: str = Field(..., example="5511988880000")


class StartConversationResponse(BaseModel):
    conversation_id: UUID
