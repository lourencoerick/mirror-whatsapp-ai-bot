from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LastMessage(BaseModel):
    content: str


class ConversationResponse(BaseModel):
    id: int
    phone_number: str
    profile_picture_url: Optional[str]
    contact_name: Optional[str]
    last_message_at: Optional[datetime]
    last_message: Optional[LastMessage]
