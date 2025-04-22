# backend/app/schemas/persona_definition.py (Revisado)

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ResponseTrigger(BaseModel):
    """Defines a semantic trigger and the corresponding persona response."""

    semantic_trigger_phrase: str = Field(
        ...,
        description="An example phrase capturing the meaning to detect in the AI's response.",
    )
    similarity_threshold: float = Field(
        default=0.75,
        description="Cosine similarity threshold (0.0 to 1.0) required to activate this trigger.",
    )
    persona_response: str = Field(
        ..., description="The persona's response message if this trigger is activated."
    )
    # Opcional: Poderíamos adicionar campos para mudar estado interno da persona ou marcar objetivo


class PersonaDefinition(BaseModel):
    """
    Defines the characteristics and behavior of a simulated customer persona
    using semantic similarity for response logic.
    """

    persona_id: str = Field(...)
    description: str = Field(...)
    initial_message: str = Field(...)
    objective: str = Field(...)
    success_criteria: List[str] = Field(
        ...
    )  # Condições para sucesso (podem usar análise de estado/eventos)
    failure_criteria: List[str] = Field(...)  # Condições para falha/desistência

    # MODIFICADO: Usando lista de gatilhos semânticos em vez de regras exatas
    response_triggers: List[ResponseTrigger] = Field(
        default_factory=list,
        description="List of semantic triggers and corresponding persona responses.",
    )

    default_response: str = Field(
        default="Entendi. Pode me falar mais?",
        description="Default message if no trigger meets its similarity threshold.",
    )

    class Config:
        schema_extra = {
            "example": {
                "persona_id": "pao_frances_buyer_v2",
                "description": "Cliente decidido que quer comprar pão francês fresco.",
                "initial_message": "Oi! Tem pão francês quentinho saindo agora?",
                "objective": "Confirmar que tem pão francês fresco e o preço, e indicar que vai querer comprar.",
                "success_criteria": [
                    "state: purchase_intent_declared"
                ],  # Exemplo de critério baseado em estado
                "failure_criteria": [
                    "event: AI_USED_FALLBACK",
                    "turn_count > 8",
                ],  # Exemplo
                "response_triggers": [
                    {
                        "semantic_trigger_phrase": "O preço do pão francês é oitenta centavos.",
                        "similarity_threshold": 0.8,
                        "persona_response": "Ótimo! Vou querer 5, por favor.",
                        # Poderia adicionar "next_state": "purchase_intent_declared"
                    },
                    {
                        "semantic_trigger_phrase": "Sim, temos pão francês fresco que acabou de sair do forno.",
                        "similarity_threshold": 0.8,
                        "persona_response": "Perfeito! Qual o preço?",
                    },
                    {
                        "semantic_trigger_phrase": "Não temos pão francês no momento.",
                        "similarity_threshold": 0.75,
                        "persona_response": "Ah, que pena. Obrigado.",
                        # Poderia adicionar "next_state": "abandoned"
                    },
                ],
                "default_response": "Entendi. E sobre o pão francês?",
            }
        }
