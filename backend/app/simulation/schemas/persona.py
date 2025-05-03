# -backend/app/simulation/schemas/persona.py

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    ValidationInfo,
)
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime
import re


class PersonaBase(BaseModel):
    """Base Pydantic schema for Persona data."""

    persona_id: str = Field(
        ...,
        description="Unique, human-readable snake_case identifier for the persona.",
        examples=["curioso_produto_x", "cliente_fidelidade"],
    )

    description: str = Field(
        ...,
        description="Concise description of the persona and their goal.",
        examples=["Cliente buscando informações sobre preço e entrega do Produto X"],
    )
    initial_message: str = Field(
        ...,
        description="The first message the persona sends.",
        examples=["Olá, gostaria de saber o preço do Produto X"],
    )
    objective: str = Field(
        ...,
        description="The specific goal the persona wants to achieve.",
        examples=["Descobrir o preço e o prazo de entrega do Produto X"],
    )
    information_needed: List[Dict[str, str]] = Field(
        ...,
        description="List of facts needed [{'entity': 'X', 'attribute': 'Y'},...]. Entity should match offerings or common topics.",
        examples=[
            [
                {"entity": "Produto X", "attribute": "price"},
                {"entity": "entrega", "attribute": "prazo"},
            ]
        ],
    )
    info_attribute_to_question_template: Dict[str, str] = Field(
        ...,
        description="Mapping of UNIQUE attributes from information_needed to question templates {'attr': 'template {entity}?'}.",
        examples=[
            {"price": "Qual o preço do {entity}?", "prazo": "Qual o prazo de {entity}?"}
        ],
    )
    success_criteria: List[str] = Field(
        default=["state:all_info_extracted"],
        description="List of criteria defining simulation success.",
        examples=[["state:all_info_extracted"]],
    )
    failure_criteria: List[str] = Field(
        default=["event:ai_fallback_detected", "turn_count > 8"],
        description="List of criteria defining simulation failure.",
        examples=[["event:ai_fallback_detected", "turn_count > 10"]],
    )

    # Validator for persona_id format (snake_case)
    @field_validator("persona_id")
    @classmethod
    def validate_persona_id_format(cls, v: str) -> str:
        """Validate persona_id is snake_case."""
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(
                "persona_id must be in snake_case (lowercase letters, numbers, underscores)."
            )
        return v

    # Basic validation for information_needed structure
    @field_validator("information_needed")
    @classmethod
    def validate_information_needed(
        cls, v: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Validate information_needed list structure."""
        if not isinstance(v, list):
            raise ValueError("information_needed must be a list.")
        if not v:
            raise ValueError("information_needed cannot be empty.")
        seen_pairs = set()
        for item in v:
            if (
                not isinstance(item, dict)
                or "entity" not in item
                or "attribute" not in item
            ):
                raise ValueError(
                    "Each item in information_needed must be a dict with 'entity' and 'attribute' keys."
                )
            if not isinstance(item["entity"], str) or not item["entity"].strip():
                raise ValueError("Entity value must be a non-empty string.")
            if not isinstance(item["attribute"], str) or not item["attribute"].strip():
                raise ValueError("Attribute value must be a non-empty string.")
            pair = (item["entity"], item["attribute"])
            if pair in seen_pairs:
                raise ValueError(f"Duplicate entity/attribute pair found: {pair}")
            seen_pairs.add(pair)
        return v

    # Validation for info_attribute_to_question_template
    # This validator now needs context to check against information_needed
    @field_validator("info_attribute_to_question_template")
    @classmethod
    def validate_question_templates(
        cls, v: Dict[str, str], info: ValidationInfo
    ) -> Dict[str, str]:
        """Validate question templates match attributes in information_needed."""
        if not isinstance(v, dict):
            raise ValueError(
                "info_attribute_to_question_template must be a dictionary."
            )

        # Check if 'information_needed' is available in the validation context
        if "information_needed" not in info.data:
            return v

        needed_attributes = {
            item["attribute"]
            for item in info.data.get("information_needed", [])
            if isinstance(item, dict) and "attribute" in item
        }

        template_attributes = set(v.keys())

        # Check if all template keys are valid attributes
        if not template_attributes.issubset(needed_attributes):
            missing_in_info = template_attributes - needed_attributes
            if missing_in_info:
                raise ValueError(
                    f"Attributes in templates not found in information_needed: {missing_in_info}"
                )

        # Check if all needed attributes have a template
        if not needed_attributes.issubset(template_attributes):
            missing_templates = needed_attributes - template_attributes
            if missing_templates:
                raise ValueError(
                    f"Missing question templates for attributes: {missing_templates}"
                )

        # Check template format (presence of {entity} placeholder might be optional depending on attribute)
        for attribute, template in v.items():
            if not isinstance(template, str) or not template.strip():
                raise ValueError(
                    f"Question template for attribute '{attribute}' must be a non-empty string."
                )
        return v


# Schema for creating a new Persona (used in POST requests)
class PersonaCreate(PersonaBase):
    """
    Schema for creating a new Persona. Requires the ID of an existing Contact.
    The 'simulation_contact_identifier' will be automatically set based on the
    linked Contact's identifier.
    """

    contact_id: UUID = Field(
        ...,
        description="The UUID of the existing Contact record to link this Persona to.",
    )

    class Config:
        # Add example for documentation generation (e.g., Swagger UI / Redoc)
        json_schema_extra = {
            "example": {
                "persona_id": "comprador_produto_y",
                "contact_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "description": "Cliente decidido a comprar o produto Y se o preço for bom.",
                "initial_message": "Quanto custa o produto Y?",
                "objective": "Confirmar o preço do produto Y e efetuar a compra.",
                "information_needed": [{"entity": "Produto Y", "attribute": "price"}],
                "info_attribute_to_question_template": {
                    "price": "Qual é o preço do {entity}?"
                },
                "success_criteria": [
                    "state:all_info_extracted",
                    "event:purchase_intent_confirmed",
                ],
                "failure_criteria": ["turn_count > 5"],
            }
        }


# Schema for reading Persona data (used in GET requests, responses)
class PersonaRead(PersonaBase):
    """Schema for reading Persona data, including database ID and timestamps."""

    id: UUID = Field(..., description="Unique identifier for the Persona record.")
    contact_id: UUID = Field(
        ..., description="The UUID of the associated Contact record."
    )
    simulation_contact_identifier: str = Field(
        ..., description="Contact identifier used in simulation (e.g., phone number)."
    )  # Added back for reading
    created_at: datetime = Field(..., description="Timestamp of creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")

    class Config:
        from_attributes = True
