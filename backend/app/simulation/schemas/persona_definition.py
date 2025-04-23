# backend/app/simulation/schemas/persona_definition.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PersonaDefinition(BaseModel):
    """
    Defines the characteristics and behavior of a simulated customer persona
    using an LLM Extractor approach via trustcall for conversation logic.
    """

    persona_id: str = Field(..., description="Unique identifier/name for the persona.")
    description: str = Field(
        ..., description="Brief description of the persona's characteristics."
    )
    initial_message: str = Field(
        ..., description="The first message this persona sends."
    )
    objective: str = Field(
        ..., description="Clear description of what the persona wants to achieve."
    )

    # --- Informações Necessárias e Perguntas ---
    information_needed: List[str] = Field(
        default_factory=list,
        description="List of specific information keys (MUST match fields in PersonaState) the persona needs to obtain.",
    )
    info_to_question_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps an information key (from information_needed) to the question the persona asks to get it.",
    )
    # -------------------------------------------

    # Critérios de sucesso/falha
    success_criteria: List[str] = Field(
        default=["state:info_needed_empty"],
        description="Conditions indicating the persona's objective was met (e.g., 'state:info_needed_empty').",
    )
    failure_criteria: List[str] = Field(
        default_factory=list,
        description="Conditions causing the persona to 'give up' (e.g., 'event:AI_FALLBACK_DETECTED', 'turn_count > 8').",
    )

    # REMOVIDO: response_triggers: List[ResponseTrigger] = Field(...)
    # REMOVIDO: default_response: str = Field(...)

    class Config:
        schema_extra = {
            "example": {
                "persona_id": "buscador_info_bolo_v3_trustcall",
                "description": "Cliente interessado no bolo de cenoura, usa trustcall.",
                "initial_message": "Olá! Gostaria de saber mais sobre o bolo de cenoura.",
                "objective": "Obter informações sobre tamanho/porções, preço e opções de entrega para o bolo de cenoura.",
                "information_needed": [
                    "size",
                    "price",
                    "delivery_options",
                ],  # Chaves devem bater com PersonaState
                "info_to_question_map": {
                    "size": "Qual o tamanho desse bolo? Serve quantas pessoas?",
                    "price": "E qual o valor do bolo?",
                    "delivery_options": "Como funciona a entrega ou retirada?",
                },
                "success_criteria": ["state:info_needed_empty"],
                "failure_criteria": ["event:AI_FALLBACK_DETECTED", "turn_count > 8"],
            }
        }
