# backend/app/simulation/schemas/persona.py
from pydantic import (
    BaseModel,
    Field,
    field_validator,
)
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime
import re


class PotentialObjection(BaseModel):
    """Defines a potential objection and its trigger."""

    trigger_keyword: Optional[str] = Field(
        None,
        description="A keyword in the AI's response that might trigger this objection (lowercase).",
    )
    trigger_stage: Optional[str] = Field(
        None,
        description="A sales stage where this objection is likely to occur (e.g., 'Presentation', 'Closing').",
    )
    objection_text: str = Field(
        ..., description="The text of the objection the persona would raise."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "trigger_keyword": "preço",
                "trigger_stage": "Presentation",
                "objection_text": "Esse preço está um pouco acima do que eu esperava.",
            }
        }


class PersonaBase(BaseModel):
    """Base Pydantic schema for Persona data, including dynamic behaviors."""

    persona_id: str = Field(
        ..., description="Unique, human-readable snake_case identifier."
    )
    description: str = Field(..., description="Concise description of the persona.")
    initial_message: str = Field(
        ..., description="The first message this persona sends."
    )
    objective: str = Field(
        ..., description="The specific goal the persona wants to achieve."
    )
    information_needed: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of facts the persona is interested in (used as context) [{'entity': 'X', 'attribute': 'Y'},...].",
    )

    potential_objections: List[PotentialObjection] = Field(
        default_factory=list,
        description="List of potential objections the persona might raise based on triggers.",
    )
    off_topic_questions: List[str] = Field(
        default_factory=list,
        description="List of potential off-topic questions the persona might ask to interrupt.",
    )
    behavior_hints: List[str] = Field(
        default_factory=list,
        description="List of keywords describing persona behavior (e.g., 'impatient', 'detailed', 'friendly', 'skeptical').",
    )

    success_criteria: List[str] = Field(
        default_factory=list,
        description="List of criteria defining simulation success (e.g., ['objective_met_via_llm', 'reached_stage:Closing']). Default is empty.",
        examples=[["event:purchase_intent_confirmed"], []],
    )
    failure_criteria: List[str] = Field(
        default=[
            "event:ai_fallback_detected",
            "turn_count > 10",
        ],
        description="List of criteria defining simulation failure.",
        examples=[["event:ai_fallback_detected", "turn_count > 10"]],
    )

    @field_validator("persona_id")
    @classmethod
    def validate_persona_id_format(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError("persona_id must be snake_case.")
        return v

    @field_validator("information_needed")
    @classmethod
    def validate_information_needed(
        cls, v: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:

        if not isinstance(v, list):
            raise ValueError("information_needed must be a list.")

        seen_pairs = set()
        for item in v:
            if (
                not isinstance(item, dict)
                or "entity" not in item
                or "attribute" not in item
            ):
                raise ValueError(
                    "Each item must be a dict with 'entity' and 'attribute'."
                )
            if not isinstance(item["entity"], str) or not item["entity"].strip():
                raise ValueError("Entity must be non-empty string.")
            if not isinstance(item["attribute"], str) or not item["attribute"].strip():
                raise ValueError("Attribute must be non-empty string.")
            pair = (item["entity"], item["attribute"])
            if pair in seen_pairs:
                raise ValueError(f"Duplicate entity/attribute pair: {pair}")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "persona_id": "cliente_dinamico_v2",
                "description": "Cliente interessado no Vendedor IA, mas sensível a preço e um pouco impaciente.",
                "initial_message": "Olá, esse Vendedor IA parece interessante. Como funciona?",
                "objective": "Entender os benefícios principais do Vendedor IA, ter uma ideia de preço e decidir se vale a pena.",
                "information_needed": [
                    {"entity": "Vendedor IA", "attribute": "pricing_model"},
                    {"entity": "Vendedor IA", "attribute": "main_benefit"},
                ],
                "potential_objections": [
                    {
                        "trigger_keyword": "preço",
                        "objection_text": "Entendi, mas qual o valor exato? Preciso ver se cabe no orçamento.",
                    },
                    {
                        "trigger_stage": "Closing",
                        "objection_text": "Ok, mas ainda preciso de um tempo para analisar internamente.",
                    },
                ],
                "off_topic_questions": [
                    "Isso integra com meu sistema de CRM atual?",
                    "Vocês oferecem algum outro serviço de automação?",
                ],
                "behavior_hints": ["price_sensitive", "impatient", "results_oriented"],
                "success_criteria": [],
                "failure_criteria": ["event:ai_fallback_detected", "turn_count > 8"],
            }
        }


class PersonaCreate(PersonaBase):
    """Schema for creating a new Persona."""

    contact_id: UUID = Field(...)

    class Config:
        json_schema_extra = {
            "example": {
                "persona_id": "lead_qualificado_objecao",
                "contact_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "description": "Lead que entende o valor, mas tem objeção sobre tempo de implementação.",
                "initial_message": "Gostei da ideia da qualificação automática.",
                "objective": "Superar a objeção sobre implementação e avançar para teste.",
                "information_needed": [
                    {"entity": "Vendedor IA", "attribute": "implementation_time"}
                ],
                "potential_objections": [
                    {
                        "trigger_keyword": "implementação",
                        "objection_text": "Parece bom, mas quanto tempo leva pra implementar tudo isso?",
                    }
                ],
                "off_topic_questions": [],
                "behavior_hints": ["busy", "interested", "implementation_focused"],
                "success_criteria": [],
                "failure_criteria": ["turn_count > 6"],
            }
        }


class PersonaRead(PersonaBase):
    """Schema for reading Persona data."""

    id: UUID = Field(...)
    contact_id: UUID = Field(...)
    simulation_contact_identifier: str = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)

    class Config:
        from_attributes = True
