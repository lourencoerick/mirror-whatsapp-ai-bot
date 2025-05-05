import uuid
from sqlalchemy import (
    Column,
    Boolean,
    Text,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class SimulationStatusEnum(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SimulationOutcomeEnum(str, enum.Enum):
    SALE_COMPLETED = "sale_completed"
    LEAD_QUALIFIED = "lead_qualified"
    INFO_OBTAINED = "info_obtained"
    USER_GAVE_UP = "user_gave_up"
    AI_USED_FALLBACK = "ai_used_fallback"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    AI_ERROR = "ai_error"
    SIMULATION_ERROR = "simulation_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unkown"
    SETUP_ERROR = "setup_error"


class Simulation(BaseModel):
    """
    SQLAlchemy model for storing simulation run metadata and results.
    """

    __tablename__ = "simulations"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the simulation run.",
    )

    company_profile_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("company_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="FK to the CompanyProfile used in this simulation.",
    )

    persona_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="FK to the Persona used in this simulation.",
    )

    status = Column(
        SAEnum(SimulationStatusEnum),
        nullable=False,
        default=SimulationStatusEnum.RUNNING,
        index=True,
        doc="Current status of the simulation run.",
    )
    outcome = Column(
        SAEnum(SimulationOutcomeEnum),
        nullable=True,
        index=True,
        doc="Final result/outcome of the simulation.",
    )

    turn_count = Column(
        Integer,
        nullable=True,
        doc="Number of turns (user + assistant messages) in the conversation.",
    )
    simulation_duration_seconds = Column(
        Integer,
        nullable=True,
        doc="Total duration of the simulation run in seconds.",
    )
    fallback_used = Column(
        Boolean,
        nullable=True,
        doc="Indicates if the AI used its fallback message during the simulation.",
    )

    evaluation_metrics = Column(
        JSON,
        nullable=True,
        doc="JSON field to store detailed evaluation metrics or LLM-as-judge results.",
    )
    error_message = Column(
        Text, nullable=True, doc="Stores any error message if the simulation failed."
    )

    # --- Relationships ---

    messages = relationship(
        "SimulationMessage",
        back_populates="simulation",
        order_by="SimulationMessage.turn_number",
        cascade="all, delete-orphan",
    )

    events = relationship(
        "SimulationEvent",
        back_populates="simulation",
        order_by="SimulationEvent.timestamp",
        cascade="all, delete-orphan",
    )

    company_profile = relationship("CompanyProfile")
    persona = relationship("Persona")

    def __repr__(self):
        return f"<Simulation(id={self.id}, status='{self.status}', outcome='{self.outcome}')>"
