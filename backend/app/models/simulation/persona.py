# backend/app/models/simulation/persona.py
import uuid
from datetime import datetime  # Import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    DateTime,
    JSON,
    UniqueConstraint,
    Index,  # Added Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Assuming your BaseModel provides the declarative base
from app.models.base import BaseModel  # Make sure this path is correct

# Forward reference for relationship type hinting
from typing import TYPE_CHECKING, List, Dict, Any  # Add List, Dict, Any

if TYPE_CHECKING:
    from app.models.contact import Contact


class Persona(BaseModel):
    """
    SQLAlchemy model representing a simulated persona profile (Classic Style).

    Stores the definition and characteristics of a persona used in simulations,
    linked one-to-one with a Contact record.
    """

    __tablename__ = "personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Keep the human-readable ID, ensure it's unique via constraint
    persona_id = Column(String, nullable=False, index=True)

    # Use the contact identifier from the linked contact, ensure unique via constraint
    simulation_contact_identifier = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    initial_message = Column(Text, nullable=False)
    objective = Column(Text, nullable=False)

    # Use JSON type for complex structures
    information_needed = Column(
        JSON,
        nullable=False,
        comment="List of dicts: [{'entity': 'x', 'attribute': 'y'}]",
    )
    info_attribute_to_question_template = Column(
        JSON, nullable=False, comment="Dict: {'attribute': 'template {entity} ?'}"
    )
    success_criteria = Column(
        JSON,
        nullable=False,
        comment="List of strings, e.g. ['state:all_info_extracted']",
    )
    failure_criteria = Column(
        JSON,
        nullable=False,
        comment="List of strings, e.g. ['event:ai_fallback_detected']",
    )

    # Foreign Key to Contact - Ensure unique=True for 1:1
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Define the 1:1 relationship TO Contact
    contact = relationship(
        "Contact", back_populates="persona"  # Link to the attribute in Contact
    )

    # Add unique constraints explicitly
    __table_args__ = (
        UniqueConstraint(
            "simulation_contact_identifier", name="uq_persona_contact_identifier"
        ),
        UniqueConstraint("persona_id", name="uq_persona_persona_id"),
        # The unique=True on contact_id already creates a constraint/index,
        # but you could define it here explicitly if preferred:
        # UniqueConstraint('contact_id', name='uq_persona_contact_id'),
    )

    def __repr__(self):
        return f"<Persona(id={self.id}, persona_id='{self.persona_id}')>"
