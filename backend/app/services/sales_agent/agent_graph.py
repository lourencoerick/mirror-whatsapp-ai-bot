# app/services/sales_agent/agent_graph.py

from typing import List, Callable

# Langchain & LangGraph
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver


from app.api.schemas.company_profile import CompanyProfileSchema

# Agent components
from .agent_state import AgentState
from .system_prompts import generate_system_message

# hooks
from .agent_hooks import (
    intelligent_stage_analyzer_hook,
    auto_follow_up_scheduler_hook,
)

# Tools
from .tools.knowledge import query_knowledge_base
from .tools.offering import (
    get_offering_details_by_id,
    update_shopping_cart,
    generate_checkout_link_for_cart,
)
from .tools.strategy import (
    suggest_objection_response_strategy,
)
from .tools.utility import (
    update_sales_stage,
)


# List of all tools for the agent
ALL_TOOLS: List[Callable] = [
    query_knowledge_base,
    get_offering_details_by_id,
    update_shopping_cart,
    generate_checkout_link_for_cart,
    suggest_objection_response_strategy,
    update_sales_stage,
]


def create_react_sales_agent_graph(
    company_profile: CompanyProfileSchema,
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
) -> Callable:
    """
    Creates and compiles the LangGraph sales agent with specific configurations.

    Args:
        company_profile: The company profile schema to generate the system prompt.
        llm_model: The primary language model instance to be used by the agent.
        checkpointer: The checkpoint saver instance for persisting agent state.

    Returns:
        A compiled LangGraph agent (Callable).
    """
    company_profile = CompanyProfileSchema.model_validate(company_profile)
    static_system_prompt_str = generate_system_message(profile=company_profile)

    return create_react_agent(
        model=model,
        tools=ALL_TOOLS,
        state_schema=AgentState,
        prompt=static_system_prompt_str,
        checkpointer=checkpointer,
        pre_model_hook=intelligent_stage_analyzer_hook,
        post_model_hook=auto_follow_up_scheduler_hook,
        version="v2",
    )
