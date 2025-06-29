# app/services/sales_agent/agent_graph.py

from typing import List, Callable, Any, Literal, Union
from pydantic import BaseModel

# Langchain & LangGraph
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    AnyMessage,
    AIMessage,
    ToolMessage,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, END
from langgraph.utils.runnable import RunnableCallable
from langgraph.prebuilt import ToolNode


from app.api.schemas.company_profile import CompanyProfileSchema
from app.api.schemas.bot_agent import BotAgentRead

# Agent components
from .agent_state import AgentState, TriggerEventType
from .system_prompts import generate_system_message

# hooks
from .agent_hooks import (
    intelligent_stage_analyzer_hook,
    auto_follow_up_scheduler_hook,
    validation_compliance_check_hook,
)

# Tools
from .tools.knowledge import query_knowledge_base
from .tools.offering import (
    get_offering_details_by_id,
    update_shopping_cart,
    generate_checkout_link_for_cart,
    list_available_offerings,
)
from .tools.strategy import (
    suggest_objection_response_strategy,
)
from .tools.utility import (
    update_sales_stage,
    validate_response_and_references,
)

from .tools.scheduling import (
    get_available_slots,
    create_appointment,
    find_next_available_day,
    get_current_datetime,
    update_appointment,
    cancel_appointment,
    find_customer_appointments,
    check_scheduling_status,
)


# List of all tools for the agent
ESSENTIAL_TOOLS: List[Callable] = [
    list_available_offerings,
    get_offering_details_by_id,
    update_shopping_cart,
    generate_checkout_link_for_cart,
    query_knowledge_base,
    suggest_objection_response_strategy,
    update_sales_stage,
    validate_response_and_references,
    check_scheduling_status,
    get_current_datetime,
]

SCHEDULING_TOOLS: List[Callable] = [
    # scheduling tools
    get_available_slots,
    create_appointment,
    find_next_available_day,
    update_appointment,
    cancel_appointment,
    find_customer_appointments,
]


def _get_state_value(state: AgentState, key: str, default: Any = None) -> Any:
    return (
        state.get(key, default)
        if isinstance(state, dict)
        else getattr(state, key, default)
    )


def tools_condition_router(
    state: Union[list[AnyMessage], dict[str, Any], BaseModel],
    messages_key: str = "messages",
) -> Literal["tools", "validation_compliance_check", "auto_follow_up_scheduler"]:

    trigger_event: TriggerEventType = state.trigger_event
    if isinstance(state, list):
        ai_message = state[-1]
    elif isinstance(state, dict) and (messages := state.get(messages_key, [])):
        ai_message = messages[-1]
    elif messages := getattr(state, messages_key, []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")

    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    elif trigger_event == "user_message":
        return "validation_compliance_check"
    else:
        return "auto_follow_up_scheduler"


def tools_outuput_condition_router(
    state: Union[list[AnyMessage], dict[str, Any], BaseModel],
    messages_key: str = "messages",
) -> Literal["chatbot", "validation_compliance_check"]:

    last_message: BaseMessage
    message_before_last: BaseMessage

    if isinstance(state, list):
        last_message = state[-1]
        if len(state) > 1:
            message_before_last = state[-2]
    elif isinstance(state, dict) and (messages := state.get(messages_key, [])):
        last_message = messages[-1]
        if len(messages) > 1:
            message_before_last = messages[-2]
    elif messages := getattr(state, messages_key, []):
        if len(messages) > 1:
            message_before_last = messages[-2]
        last_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")

    if (
        isinstance(last_message, AIMessage)
        and isinstance(message_before_last, ToolMessage)
        and (message_before_last.name == "validate_response_and_references")
    ):
        return "validation_compliance_check"
    else:
        return "chatbot"


def create_react_sales_agent_graph(
    company_profile: CompanyProfileSchema,
    model: BaseChatModel,
    bot_agent: BotAgentRead,
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
    bot_agent = BotAgentRead.model_validate(bot_agent)

    all_tools: List[str] = []
    all_tools.extend(ESSENTIAL_TOOLS)

    if company_profile.is_scheduling_enabled:
        all_tools.extend(SCHEDULING_TOOLS)

    static_system_prompt_str = generate_system_message(
        profile=company_profile, bot_agent_name=bot_agent.name
    )
    _system_message: BaseMessage = SystemMessage(content=static_system_prompt_str)
    prompt_runnable = RunnableCallable(
        lambda state: [_system_message] + _get_state_value(state, "messages"),
        name="prompt",
    )

    model_runnable = prompt_runnable | model.bind_tools(
        all_tools, parallel_tool_calls=False
    )

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node(
        "intelligent_stage_analyzer", intelligent_stage_analyzer_hook
    )
    graph_builder.add_node("auto_follow_up_scheduler", auto_follow_up_scheduler_hook)
    graph_builder.add_node(
        "validation_compliance_check", validation_compliance_check_hook
    )
    graph_builder.add_node("tools", ToolNode(all_tools))
    graph_builder.add_node(
        "chatbot",
        lambda state: {"messages": model_runnable.invoke(state)},
    )

    graph_builder.set_entry_point("intelligent_stage_analyzer")
    graph_builder.add_edge("intelligent_stage_analyzer", "chatbot")

    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition_router,
        {
            "tools": "tools",
            "validation_compliance_check": "validation_compliance_check",
            "auto_follow_up_scheduler": "auto_follow_up_scheduler",
        },
    )

    # graph_builder.add_edge("tools", "chatbot")

    graph_builder.add_conditional_edges(
        "tools",
        tools_outuput_condition_router,
        {
            "chatbot": "chatbot",
            "validation_compliance_check": "validation_compliance_check",
        },
    )

    graph_builder.add_edge("auto_follow_up_scheduler", END)

    graph = graph_builder.compile(checkpointer=checkpointer)

    return graph
