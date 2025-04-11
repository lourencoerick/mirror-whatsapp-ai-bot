from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from .contact import ContactBase


class MessageSnippet(BaseModel):
    id: UUID
    content: str
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConversationSearchResult(BaseModel):
    id: UUID = Field(..., description="Unique identifier for the conversation")

    contact: Optional[ContactBase] = Field(..., description="Contact's information")

    last_message_at: Optional[datetime] = Field(
        None, description="Timestamp of the last message in the conversation"
    )
    last_message: Optional[MessageSnippet] = Field(
        None, description="Snippet of the actual latest message in the conversation"
    )

    matching_message: Optional[MessageSnippet] = Field(
        None,
        description="Snippet of the most recent message content that matched the search query (if the match was in a message)",
    )

    updated_at: datetime = Field(
        ..., description="Timestamp of the last relevant activity"
    )


class StartConversationRequest(BaseModel):
    phone_number: str = Field(..., example="5511988880000")


class StartConversationResponse(BaseModel):
    conversation_id: UUID
