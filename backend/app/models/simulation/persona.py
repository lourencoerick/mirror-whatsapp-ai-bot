# backend/app/models/simulation/persona.py
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
    ARRAY,
    Text as DBText,
    text,
)


from sqlalchemy.dialects.postgresql import UUID, JSONB

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


from app.models.base import BaseModel


from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from app.models.contact import Contact


class Persona(BaseModel):
    """
    SQLAlchemy model representing a simulated persona profile.

    Stores the definition, characteristics, and dynamic behavior elements
    of a persona used in simulations, linked one-to-one with a Contact record.
    """

    __tablename__ = "personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id = Column(String, nullable=False, index=True, unique=True)

    simulation_contact_identifier = Column(
        String, nullable=False, index=True, unique=True
    )

    description = Column(DBText, nullable=False)
    initial_message = Column(DBText, nullable=False)
    objective = Column(DBText, nullable=False)

    information_needed = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="List of dicts: [{'entity': 'x', 'attribute': 'y'}] - Contextual info persona seeks.",
    )

    potential_objections = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="List of potential objections [{'trigger_keyword': 'x', 'objection_text': 'y'},...]",
    )
    off_topic_questions = Column(
        ARRAY(DBText),
        nullable=False,
        server_default=text("'{}'::text[]"),
        comment="List of potential off-topic questions persona might ask.",
    )
    behavior_hints = Column(
        ARRAY(DBText),
        nullable=False,
        server_default=text("'{}'::text[]"),
        comment="List of keywords describing persona behavior (e.g., 'impatient', 'detailed').",
    )

    success_criteria = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="List of strings defining success (often empty now).",
    )
    failure_criteria = Column(
        JSONB,
        nullable=False,
        server_default=text(
            '\'["event:ai_fallback_detected", "turn_count > 10"]\'::jsonb'
        ),
        comment="List of strings defining failure.",
    )

    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    contact = relationship("Contact", back_populates="persona")

    __table_args__ = (
        UniqueConstraint("persona_id", name="uq_persona_persona_id"),
        UniqueConstraint(
            "simulation_contact_identifier", name="uq_persona_contact_identifier"
        ),
    )

    def __repr__(self):
        return f"<Persona(id={self.id}, persona_id='{self.persona_id}')>"
