# backend/app/services/ai_reply/new_agent/schemas/proactive_step_output.py

from typing import Optional
from pydantic import BaseModel, Field

# Importar tipos do state_definition para consistência
# Usar caminhos relativos corretos se este arquivo estiver em 'schemas'
try:
    from ..state_definition import AgentActionType, AgentActionDetails
except ImportError:  # Fallback para o caso de execução de testes ou estrutura diferente
    AgentActionType = str  # type: ignore
    AgentActionDetails = dict  # type: ignore


class ProactiveStepDecision(BaseModel):
    """
    Defines the structured output expected from the LLM when it's deciding
    a proactive next step for the agent.
    """

    proactive_action_command: Optional[AgentActionType] = Field(
        None,
        description="The specific proactive action command the agent should execute. Null if no proactive action is deemed appropriate.",
    )
    proactive_action_parameters: Optional[AgentActionDetails] = Field(
        default_factory=dict,
        description="Parameters required for the proactive_action_command. Empty if no parameters or no action.",
    )
    justification: Optional[str] = Field(
        None,
        description="A brief justification from the LLM explaining why this proactive step was chosen (optional, for debugging/logging).",
    )

    class Config:
        """Pydantic model configuration."""

        extra = "forbid"  # Disallow extra fields not defined in the model
        use_enum_values = (
            True  # Ensure enum values are used if AgentActionType becomes a true Enum
        )
