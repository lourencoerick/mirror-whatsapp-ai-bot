# app/services/sales_agent/schemas.py
from typing import List
from pydantic import BaseModel, Field
from .agent_state import (
    SalesStageLiteral,
)


class StageAnalysisOutput(BaseModel):
    """
    Output schema for the stage analysis performed by the pre-model hook.
    It provides the determined sales stage, reasoning, and a suggested focus.
    """

    determined_sales_stage: SalesStageLiteral = Field(
        description="The sales stage determined by analyzing the recent conversation."
    )
    reasoning: str = Field(
        description="Brief reasoning for why this sales stage was determined."
    )
    suggested_next_focus: str = Field(
        description="A concise suggestion for the main sales agent on what to focus on next or a logical next step, given the current stage and conversation."
    )

    communication_rules_declaration: str = Field(
        description="A statement from you confirming that your suggestions follow communication rules described  'Diretrizes de Comunicação'. This is important and critical—it’s how you represent the company and respect its authority."
    )

    model_config = {"validate_assignment": True}


class ObjectionResponseStrategyOutput(BaseModel):
    """
    Structure for the suggested strategies to respond to customer objections.
    This model outlines different approaches and actionable items for the sales agent.
    """

    primary_approach: str = Field(
        description="The main approach or philosophy for handling this type of objection (e.g., 'Reframe value vs. cost', 'Deepen understanding of unmet need')."
    )
    suggested_questions_to_ask: List[str] = Field(
        default_factory=list,
        description="Specific questions the agent can ask the customer to better understand the objection or redirect the conversation.",
    )
    key_points_to_emphasize: List[str] = Field(
        default_factory=list,
        description="Specific benefits, features, or value points of the offering or company that should be reinforced.",
    )
    potential_reframes_or_analogies: List[str] = Field(
        default_factory=list,
        description="Ways to recontextualize the objection or analogies that can help the customer see it from a different perspective.",
    )
    next_step_options: List[str] = Field(
        default_factory=list,
        description="Suggestions for CONCRETE AND FEASIBLE next steps the virtual sales agent can take, considering the company's capabilities. Avoid suggesting actions the company does not offer (e.g., demos, if not available).",
    )
    model_config = {"validate_assignment": True}
