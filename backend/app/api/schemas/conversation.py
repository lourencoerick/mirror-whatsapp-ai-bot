from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LastMessage(BaseModel):
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    contact_name: Optional[str]
    last_message_at: Optional[datetime]
    last_message: Optional[LastMessage]
