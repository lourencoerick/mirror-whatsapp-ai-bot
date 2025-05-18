# backend/app/services/ai_reply/new_agent/schemas/proactive_step_output.py

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

# Importar tipos do state_definition para consistência
# Usar caminhos relativos corretos se este arquivo estiver em 'schemas'
try:
    from ..state_definition import AgentActionType, AgentActionDetails, AgentGoalType
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
        description="The specific proactive action command the agent should execute. Fill this OR suggested_next_goal_type. Examples: SEND_FOLLOW_UP_MESSAGE, GENERATE_FAREWELL.",
    )
    proactive_action_parameters: Optional[AgentActionDetails] = Field(
        default_factory=dict,
        description="Parameters required for the proactive_action_command. Used if proactive_action_command is set.",
    )

    suggested_next_goal_type: Optional[AgentGoalType] = Field(
        None,
        description="If a complex initiative is needed (e.g., restarting SPIN, presenting a solution), suggest the next high-level goal for the Planner. Fill this OR proactive_action_command.",
    )
    suggested_next_goal_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Details for the suggested_next_goal_type (e.g., {'spin_type': 'Situation'} if suggesting INVESTIGATING_NEEDS). Used if suggested_next_goal_type is set.",
    )

    justification: str = Field(
        ...,
        description="A brief justification from the LLM explaining its choice (direct action or goal suggestion).",
    )

    class Config:
        """Pydantic model configuration."""

        extra = "forbid"  # Disallow extra fields not defined in the model
        use_enum_values = (
            True  # Ensure enum values are used if AgentActionType becomes a true Enum
        )
