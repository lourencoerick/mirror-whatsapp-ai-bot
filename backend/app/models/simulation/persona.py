# backend/app/models/simulation/persona.py
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    JSON,  # Manter JSON para compatibilidade ou mudar para JSONB
    UniqueConstraint,
    Index,
    ARRAY,  # Importar ARRAY
    Text as DBText,  # Renomear Text para evitar conflito com typing.Text se usado
    text,  # Importar text para server_default
)

# Usar JSONB do dialeto PostgreSQL para melhor performance
from sqlalchemy.dialects.postgresql import UUID, JSONB

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Assuming your BaseModel provides the declarative base
from app.models.base import BaseModel

# Forward reference for relationship type hinting
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
    persona_id = Column(
        String, nullable=False, index=True, unique=True
    )  # Unique já definido abaixo, mas ok aqui também

    # Identificador do contato associado (para referência e unicidade)
    simulation_contact_identifier = Column(
        String, nullable=False, index=True, unique=True
    )  # Unique já definido abaixo

    description = Column(DBText, nullable=False)
    initial_message = Column(DBText, nullable=False)
    objective = Column(DBText, nullable=False)

    # Mantido, mas agora usado como contexto para o Persona LLM
    information_needed = Column(
        JSONB,  # Usar JSONB é geralmente melhor no Postgres
        nullable=False,
        server_default=text("'[]'::jsonb"),  # Default como lista JSON vazia
        comment="List of dicts: [{'entity': 'x', 'attribute': 'y'}] - Contextual info persona seeks.",
    )

    # info_attribute_to_question_template = Column(JSON, nullable=False) # <-- REMOVIDO

    # --- NOVOS CAMPOS ---
    potential_objections = Column(
        JSONB,  # Armazena a lista de objetos PotentialObjection
        nullable=False,
        server_default=text("'[]'::jsonb"),  # Default como lista JSON vazia
        comment="List of potential objections [{'trigger_keyword': 'x', 'objection_text': 'y'},...]",
    )
    off_topic_questions = Column(
        ARRAY(DBText),  # Array de strings
        nullable=False,
        server_default=text("'{}'::text[]"),  # Default como array vazio de texto
        comment="List of potential off-topic questions persona might ask.",
    )
    behavior_hints = Column(
        ARRAY(DBText),  # Array de strings
        nullable=False,
        server_default=text("'{}'::text[]"),  # Default como array vazio de texto
        comment="List of keywords describing persona behavior (e.g., 'impatient', 'detailed').",
    )
    # --- FIM NOVOS CAMPOS ---

    # Critérios simplificados
    success_criteria = Column(
        JSONB,  # Usar JSONB
        nullable=False,
        server_default=text("'[]'::jsonb"),  # Default como lista JSON vazia
        comment="List of strings defining success (often empty now).",
    )
    failure_criteria = Column(
        JSONB,  # Usar JSONB
        nullable=False,
        server_default=text(
            '\'["event:ai_fallback_detected", "turn_count > 10"]\'::jsonb'
        ),  # Default atualizado
        comment="List of strings defining failure.",
    )

    # Foreign Key e Relacionamento (Mantidos)
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "contacts.id", ondelete="CASCADE"
        ),  # Adicionado ondelete se fizer sentido
        unique=True,
        nullable=False,
        index=True,
    )
    contact = relationship("Contact", back_populates="persona")

    # Constraints (Mantidos)
    __table_args__ = (
        UniqueConstraint("persona_id", name="uq_persona_persona_id"),
        UniqueConstraint(
            "simulation_contact_identifier", name="uq_persona_contact_identifier"
        ),
        # UniqueConstraint('contact_id', name='uq_persona_contact_id'), # Já coberto por unique=True
        Index("ix_personas_persona_id", "persona_id"),  # Index explícito (boa prática)
        Index("ix_personas_contact_id", "contact_id"),  # Index explícito (boa prática)
    )

    def __repr__(self):
        return f"<Persona(id={self.id}, persona_id='{self.persona_id}')>"
