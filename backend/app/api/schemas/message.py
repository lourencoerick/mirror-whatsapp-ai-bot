from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class MessageCreate(BaseModel):
    account_id: int
    inbox_id: int
    contact_id: int
    conversation_id: int

    source_id: str  # external ID of the message
    content: Optional[str] = None
    direction: Literal["in", "out"]
    content_type: Literal["text", "image", "audio", "file", "video", "conversation"] = (
        "text"
    )
    status: Literal["received", "processed", "failed"] = "received"

    message_timestamp: datetime  # the moment when the user sent the message
    content_attributes: Optional[dict] = {}


class MessageRead(BaseModel):
    id: int
    content: Optional[str]
    direction: str
    message_type: str
    content_type: Optional[str]
    sent_at: Optional[datetime]
