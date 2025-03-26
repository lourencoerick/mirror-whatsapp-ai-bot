from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class MessageCreatePayload(BaseModel):
    """
    Payload enviado pelo frontend para criar uma nova mensagem de saída.
    """

    content: str = Field(..., example="Olá, tudo bem?")


class MessageCreate(BaseModel):
    account_id: int
    inbox_id: int
    contact_id: int
    conversation_id: int
    source_id: str  # external ID of the message
    user_id: Optional[int] = None

    direction: Literal["in", "out"]
    status: Literal["received", "sent", "pending", "processing", "failed"] = "received"
    message_timestamp: datetime  # the moment when the user sent the message
    private: Optional[bool] = False
    content: Optional[str] = None
    content_type: Literal["text", "image", "audio", "file", "video", "conversation"] = (
        "text"
    )
    content_attributes: Optional[dict] = {}


class MessageRead(BaseModel):
    id: int
    content: Optional[str]
    direction: str
    message_type: str
    content_type: Optional[str]
    sent_at: Optional[datetime]
