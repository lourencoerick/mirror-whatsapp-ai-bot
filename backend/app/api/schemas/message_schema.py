from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal


class MessageCreate(BaseModel):
    content: str
    direction: Literal["in", "out"]
    account_id: int
    inbox_id: int
    conversation_id: int
    contact_id: Optional[int] = None
    user_id: Optional[int] = None
    source_id: Optional[str] = None
    status: Optional[int] = None
    content_attributes: Optional[Dict] = None
    content_type: Optional[int] = None
    private: Optional[bool] = False
