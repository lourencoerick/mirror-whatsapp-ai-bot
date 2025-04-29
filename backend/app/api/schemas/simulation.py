# src/api/schemas/simulation.py

import uuid
from pydantic import BaseModel, Field
from app.config import get_settings  # Assuming settings has MAX_MESSAGE_LENGTH

settings = get_settings()


class SimulationDetailsResponse(BaseModel):
    """
    Schema for returning the UUIDs of the primary simulation entities
    associated with a user's account.
    """

    inbox_id: uuid.UUID = Field(
        ...,  # Ellipsis indicates the field is required
        description="The UUID of the primary simulation inbox.",
        examples=["f47ac10b-58cc-4372-a567-0e02b2c3d479"],  # Example UUID
    )
    contact_id: uuid.UUID = Field(
        ...,
        description="The UUID of the primary simulation contact ('Simulador').",
        examples=["a1b2c3d4-e5f6-7890-1234-567890abcdef"],
    )
    conversation_id: uuid.UUID = Field(
        ...,
        description="The UUID of the primary simulation conversation between the inbox and the contact.",
        examples=["abcdef12-3456-7890-abcd-ef1234567890"],
    )

    class Config:
        from_attributes = True


class SimulationMessageCreate(BaseModel):
    """Schema for creating a message sent *by* the simulated contact."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=getattr(settings, "MAX_MESSAGE_LENGTH", 4096),
        description="The text content of the message being simulated.",
    )


class SimulationMessageEnqueueResponse(BaseModel):
    """Schema for the response after successfully enqueueing a simulation message."""

    status: str = Field(..., example="message enqueued")
    source_id: str = Field(
        ...,
        description="A unique identifier generated for this simulated message attempt.",
        example="sim_ui_...",
    )
    conversation_id: str = Field(
        ..., description="The string representation of the target conversation UUID."
    )
