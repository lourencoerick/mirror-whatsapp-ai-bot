import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import BaseModel


class SimulationMessageRoleEnum(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SimulationMessage(BaseModel):
    """
    SQLAlchemy model for storing individual messages within a simulation run.
    """

    __tablename__ = "simulation_messages"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the simulation message.",
    )
    simulation_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="FK to the Simulation this message belongs to.",
    )
    turn_number = Column(
        Integer,
        nullable=False,
        doc="Sequential number of the turn in the conversation (starting from 1).",
    )
    role = Column(
        SAEnum(SimulationMessageRoleEnum),
        nullable=False,
        doc="The role of the sender (user persona or AI assistant).",
    )
    content = Column(Text, nullable=False, doc="The text content of the message.")

    original_message_id = Column(PG_UUID(as_uuid=True), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when this message was recorded in the simulation.",
    )

    # --- Relationships ---
    simulation = relationship("Simulation", back_populates="messages")

    def __repr__(self):
        return f"<SimulationMessage(id={self.id}, simulation_id={self.simulation_id}, turn={self.turn_number}, role='{self.role}')>"
