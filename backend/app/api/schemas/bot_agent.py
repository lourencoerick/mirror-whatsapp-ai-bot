from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List


class BotAgentBase(BaseModel):
    """Base schema with common BotAgent fields."""

    name: Optional[str] = Field(
        default="Assistente Principal",
        description="Descriptive name for the AI agent.",
        max_length=255,
    )
    first_message: Optional[str] = Field(
        None,
        description="Initial message the bot sends to start the conversation (if empty, waits for the user).",
    )

    use_rag: Optional[bool] = Field(
        default=True,
        description="Indicates if the agent should use the Knowledge Base (RAG) to generate responses.",
    )

    model_config = {"from_attributes": True}


class BotAgentCreate(BotAgentBase):
    """
    Schema for updating an existing BotAgent.
    All fields are optional on update.
    """

    # Inherits all fields from BotAgentBase, making them optional by default
    # No additional fields needed here for basic update
    pass

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Primary Sales Assistant",
                "first_message": "Hello! I'm the virtual assistant for [Company Name]. How can I help you today?",
                "use_rag": False,
            }
        }
    }


class BotAgentUpdate(BotAgentBase):
    """
    Schema for updating an existing BotAgent.
    All fields are optional on update.
    """

    # Inherits all fields from BotAgentBase, making them optional by default
    # No additional fields needed here for basic update
    pass

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Primary Sales Assistant",
                "first_message": "Hello! I'm the virtual assistant for [Company Name]. How can I help you today?",
                "use_rag": False,
            }
        }
    }


class BotAgentRead(BotAgentBase):
    """Schema for returning BotAgent data, including its ID."""

    id: UUID = Field(..., description="Unique identifier for the BotAgent.")
    account_id: UUID = Field(..., description="ID of the account the agent belongs to.")
    # We could include associated inboxes here, but a separate endpoint is often better
    # associated_inboxes: Optional[List[InboxRead]] = []

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "account_id": "f0e9d8c7-b6a5-4321-fedc-ba9876543210",
                "name": "Primary Assistant",
                "first_message": "Hi! How can I help?",
                "is_active": True,
                "use_rag": False,
            }
        },
    }


# --- Schemas for Inbox Association ---


class AgentInboxAssociationUpdate(BaseModel):
    """Schema for defining the list of Inboxes associated with an Agent."""

    inbox_ids: List[UUID] = Field(
        default_factory=list,
        description="Complete list of Inbox IDs that should be associated with this agent.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "inbox_ids": [
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                ]
            }
        }
    }
