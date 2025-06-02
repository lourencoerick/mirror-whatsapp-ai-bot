# app/services/sales_agent/pydantic_models.py
from pydantic import BaseModel, Field
from typing import List
from .agent_state import (
    SalesStageLiteral,
)  # Assuming SalesStageLiteral is in agent_state.py


class StageAnalysisOutput(BaseModel):
    determined_sales_stage: SalesStageLiteral = Field(
        description="O estágio de vendas determinado pela análise da conversa recente."
    )
    reasoning: str = Field(
        description="Breve justificativa para a determinação deste estágio."
    )
    suggested_next_focus: str = Field(
        description="Uma breve sugestão para o agente de vendas principal sobre o que focar em seguida ou um próximo passo lógico, dada a fase atual e a conversa."
    )
    model_config = {"validate_assignment": True}


class ObjectionResponseStrategyOutput(BaseModel):
    """
    Estrutura para as sugestões de estratégia de resposta a objeções.
    """

    primary_approach: str = Field(
        description="A abordagem principal ou filosofia para lidar com este tipo de objeção (ex: 'Reenquadrar valor vs. custo', 'Aprofundar na necessidade não percebida')."
    )
    suggested_questions_to_ask: List[str] = Field(
        default_factory=list,
        description="Perguntas específicas que o agente pode fazer ao cliente para entender melhor a objeção ou redirecionar a conversa.",
    )
    key_points_to_emphasize: List[str] = Field(
        default_factory=list,
        description="Benefícios, características ou pontos de valor específicos da oferta ou da empresa que devem ser reforçados.",
    )
    potential_reframes_or_analogies: List[str] = Field(
        default_factory=list,
        description="Maneiras de recontextualizar a objeção ou analogias que podem ajudar o cliente a ver de outra perspectiva.",
    )
    next_step_options: List[str] = Field(
        default_factory=list,
        description="Sugestões de próximos passos CONCRETOS E REALIZÁVEIS pelo agente de vendas virtual, considerando as capacidades da empresa. Evite sugerir ações que a empresa não oferece (ex: demonstrações, se não disponíveis).",
    )
    model_config = {"validate_assignment": True}
