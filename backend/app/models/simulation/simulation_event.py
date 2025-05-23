import uuid
import enum
from sqlalchemy import Column, DateTime, ForeignKey, JSON, Enum as SAEnum, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class SimulationEventTypeEnum(str, enum.Enum):
    SIMULATION_START = "simulation_start"
    TURN_START = "turn_start"
    USER_MESSAGE_SENT = "user_message_sent"
    AI_RESPONSE_RECEIVED = "ai_response_received"
    AI_FALLBACK_DETECTED = "ai_fallback_detected"
    PERSONA_OBJECTIVE_MET = "persona_objective_met"
    PERSONA_GAVE_UP = "persona_gave_up"
    RULE_VIOLATION_DETECTED = "rule_violation_detected"
    LLM_EVALUATION_TRIGGERED = "llm_evaluation_triggered"
    AI_PROCESSING_ERROR = "ai_processing_error"
    SIMULATION_ENGINE_ERROR = "simulation_engine_error"
    TURN_LIMIT_WARNING = "turn_limit_warning"
    SIMULATION_END = "simulation_end"


class SimulationEvent(BaseModel):
    """
    SQLAlchemy model for storing significant events occurring during a simulation run.
    """

    __tablename__ = "simulation_events"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the simulation event.",
    )
    simulation_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="FK to the Simulation this event belongs to.",
    )
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the event occurred.",
    )
    event_type = Column(
        SAEnum(SimulationEventTypeEnum),
        nullable=False,
        index=True,
        doc="The type of event that occurred.",
    )
    turn_number = Column(
        Integer,
        nullable=True,
        doc="The conversation turn number when the event occurred, if applicable.",
    )
    details = Column(
        JSON,
        nullable=True,
        doc="Optional JSON field for additional details about the event (e.g., error message, rule violated).",
    )

    # --- Relationships ---

    simulation = relationship("Simulation", back_populates="events")

    def __repr__(self):
        return f"<SimulationEvent(id={self.id}, simulation_id={self.simulation_id}, type='{self.event_type}')>"
