from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from .contact import ContactBase
from app.models.conversation import ConversationStatusEnum


class MessageSnippet(BaseModel):
    id: UUID
    content: str
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class ConversationRead(BaseModel):
    id: UUID
    account_id: UUID
    inbox_id: UUID
    contact_id: UUID

    status: ConversationStatusEnum = Field(
        ...,
        description="Current status of the conversation regarding human interaction",
    )
    unread_agent_count: int = Field(
        ..., ge=0, description="Number of unread messages for the agent"
    )
    is_bot_active: bool = Field(..., description="Flag indicating if the bot is active")

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Or orm_mode = True for older Pydantic
        json_schema_extra = {
            "example": {
                "id": "e8a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9f",
                "account_id": "f0a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9a",
                "inbox_id": "...",
                "contact_id": "...",
                "created_at": "2023-11-10T10:00:00Z",
                "updated_at": "2023-11-15T11:30:00Z",
                "status": "human_active",  # Example value
                "unread_agent_count": 3,  # Example value
                # "assignee_id": "...",
            }
        }


class ConversationUpdateStatus(BaseModel):
    status: ConversationStatusEnum = Field(
        ..., description="The new status to set for the conversation."
    )

    class Config:
        json_schema_extra = {"example": {"status": "closed"}}


class ConversationSearchResult(BaseModel):
    id: UUID = Field(..., description="Unique identifier for the conversation")

    status: Optional[ConversationStatusEnum] = Field(
        None,
        description="Current status of the conversation regarding human interaction",
    )
    unread_agent_count: Optional[int] = Field(
        None, ge=0, description="Number of unread messages for the agent"
    )
    is_bot_active: Optional[bool] = Field(
        None, description="Flag indicating if the bot is active"
    )

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

    class Config:
        from_attributes = True  # Or orm_mode = True for older Pydantic
        json_schema_extra = {
            "example": {
                "id": "e8a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9f",
                "account_id": "f0a4f7a0-1b3c-4a8e-8d0a-3f1e9b6c2e9a",
                "inbox_id": "...",
                "contact_id": "...",
                "created_at": "2023-11-10T10:00:00Z",
                "updated_at": "2023-11-15T11:30:00Z",
                "status": "HUMAN_ACTIVE",
                "unread_agent_count": 3,
            }
        }


class StartConversationRequest(BaseModel):
    phone_number: str = Field(..., example="5511988880000")


class StartConversationResponse(BaseModel):
    conversation_id: UUID
