from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MessageSnippet(BaseModel):
    id: UUID
    content: str
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: UUID
    phone_number: str
    updated_at: datetime
    profile_picture_url: Optional[str]
    contact_name: Optional[str]
    last_message_at: Optional[datetime]
    last_message: Optional[MessageSnippet]

    class Config:
        from_attributes = True


class ConversationSearchResult(BaseModel):
    id: UUID = Field(..., description="Unique identifier for the conversation")
    phone_number: str = Field(..., description="Contact's phone number (extracted)")
    updated_at: datetime = Field(
        ..., description="Timestamp of the last relevant activity"
    )
    profile_picture_url: Optional[str] = Field(
        None, description="URL of contact's profile picture (extracted)"
    )
    contact_name: Optional[str] = Field(
        None, description="Name of the contact (extracted)"
    )
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


class StartConversationRequest(BaseModel):
    phone_number: str = Field(..., example="5511988880000")


class StartConversationResponse(BaseModel):
    conversation_id: UUID
