# backend/app/models/simulation.py

import uuid
from sqlalchemy import (
    Column,
    Boolean,
    Text,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import BaseModel  # Import Base from your database setup


# Define Enum for Simulation Status
class SimulationStatusEnum(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# Define Enum for Simulation Outcome (customize as needed)
class SimulationOutcomeEnum(str, enum.Enum):
    # Success Outcomes
    SALE_COMPLETED = "sale_completed"  # Persona decided to buy
    LEAD_QUALIFIED = "lead_qualified"  # Persona reached qualification criteria
    INFO_OBTAINED = "info_obtained"  # Persona got the info it needed
    # Failure/Neutral Outcomes
    USER_GAVE_UP = "user_gave_up"  # Persona logic decided to end conversation
    AI_USED_FALLBACK = "ai_used_fallback"  # AI used its fallback message
    TURN_LIMIT_REACHED = "turn_limit_reached"
    AI_ERROR = "ai_error"  # Error during AI processing detected
    SIMULATION_ERROR = "simulation_error"  # Error in the simulation script itself
    # Add more specific outcomes as needed


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
    # Foreign key to the profile used in this simulation
    company_profile_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "company_profiles.id", ondelete="SET NULL"
        ),  # Keep simulation record even if profile deleted
        nullable=True,  # Or False if profile must exist
        index=True,
        doc="FK to the CompanyProfile used in this simulation.",
    )
    # Store persona details (name or definition snapshot)
    # Using JSON allows flexibility if personas are complex or LLM-generated
    persona_definition = Column(
        JSON, nullable=False, doc="JSON representation of the PersonaDefinition used."
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
        nullable=True,  # Null while running or if failed before outcome
        index=True,
        doc="Final result/outcome of the simulation.",
    )
    # Store basic metrics directly or in JSON
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
    # JSON field for additional or complex metrics/evaluation results
    evaluation_metrics = Column(
        JSON,
        nullable=True,
        doc="JSON field to store detailed evaluation metrics or LLM-as-judge results.",
    )
    error_message = Column(
        Text, nullable=True, doc="Stores any error message if the simulation failed."
    )

    # --- Relationships ---
    # Relationship to the messages of this simulation
    messages = relationship(
        "SimulationMessage",
        back_populates="simulation",
        order_by="SimulationMessage.turn_number",  # Order messages by turn
        cascade="all, delete-orphan",  # Delete messages if simulation is deleted
    )

    events = relationship(
        "SimulationEvent",
        back_populates="simulation",
        order_by="SimulationEvent.timestamp",
        cascade="all, delete-orphan",
    )

    company_profile = relationship("CompanyProfile")

    def __repr__(self):
        return f"<Simulation(id={self.id}, status='{self.status}', outcome='{self.outcome}')>"
