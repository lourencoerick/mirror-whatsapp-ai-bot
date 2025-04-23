from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class InfoRequest(BaseModel):
    """Defines a specific piece of information the persona needs."""

    entity: str = Field(
        ..., description="The entity the information is about (e.g., 'Pão Francês')."
    )
    attribute: str = Field(
        ...,
        description="The attribute needed for the entity (e.g., 'price', 'size'). Must match keys in info_attribute_to_question_template.",
    )


class PersonaDefinition(BaseModel):
    """
    Defines the characteristics and behavior of a simulated customer persona
    using an LLM Extractor (trustcall) to populate a list of extracted facts.
    """

    persona_id: str = Field(..., description="Unique identifier/name for the persona.")

    simulation_contact_identifier: str = Field(
        ...,
        description="The unique identifier for the contact (e.g., '+5511...', 'sim_user@example.com'). Used in webhook payload 'from' field.",
    )

    description: str = Field(
        ..., description="Brief description of the persona's characteristics."
    )
    initial_message: str = Field(
        ..., description="The first message this persona sends."
    )
    objective: str = Field(
        ..., description="Clear description of what the persona wants to achieve."
    )

    information_needed: List[InfoRequest] = Field(
        default_factory=list,
        description="List of specific entity-attribute pairs the persona needs to find.",
    )
    info_attribute_to_question_template: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps an attribute name to a question template. Use '{entity}' for substitution.",
    )

    success_criteria: List[str] = Field(
        default=["state:all_info_extracted"],
        description="Conditions indicating the persona's objective was met (e.g., 'state:all_info_extracted').",
    )
    failure_criteria: List[str] = Field(
        default_factory=list,
        description="Conditions causing the persona to 'give up' (e.g., 'event:ai_fallback_detected', 'turn_count > 8').",
    )

    class Config:
        schema_extra = {
            "example": {
                "persona_id": "comparador_preco_v2_extractor",
                "description": "Cliente focado em obter preços de itens específicos.",
                "initial_message": "Oi, bom dia! Gostaria de saber os preços de alguns itens.",
                "objective": "Obter os preços do Pão Francês e do Bolo de Cenoura.",
                "information_needed": [
                    {"entity": "Pão Francês", "attribute": "price"},
                    {"entity": "Bolo de Cenoura", "attribute": "price"},
                ],
                "info_attribute_to_question_template": {
                    "price": "Poderia me informar o preço de {entity}, por favor?",
                    "size": "Qual o tamanho disponível para {entity}?",
                },
                "success_criteria": ["state:all_info_extracted"],
                "failure_criteria": ["event:AI_FALLBACK_DETECTED", "turn_count > 7"],
            }
        }
