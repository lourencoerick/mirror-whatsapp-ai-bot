from typing import Optional, Dict, Any, get_args
from loguru import logger
from typing_extensions import Annotated

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.services.sales_agent.agent_state import AgentState, SalesStageLiteral


@tool
async def update_sales_stage(
    new_stage: SalesStageLiteral,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    reason: Optional[str] = None,
) -> Command:
    """
    Updates the current sales stage of the conversation.
    Use this tool when the conversation has clearly progressed to a new phase
    (e.g., from 'qualification' to 'offering_presentation', or to 'checkout_initiated').
    The new stage must be one of the predefined valid sales stages.

    Args:
        new_stage: The new sales stage to transition to. Must be a valid SalesStageLiteral.
        reason: (Optional) A brief reason or context for this stage change, for logging.
        state: The current agent state (not strictly needed if only updating via Command).
        tool_call_id: The ID of this tool call.

    Returns:
        A Command object to update 'current_sales_stage' and add a ToolMessage.
    """
    tool_name = "update_sales_stage"
    logger.info(f"--- Executing Tool: {tool_name} (Call ID: {tool_call_id}) ---")
    logger.info(
        f"[{tool_name}] Requested new stage: '{new_stage}'. Reason: {reason if reason else 'N/A'}"
    )

    state_updates: Dict[str, Any] = {}
    tool_message_content: str

    valid_stages = get_args(SalesStageLiteral)
    if new_stage not in valid_stages:
        logger.warning(f"[{tool_name}] Invalid sales stage '{new_stage}' provided.")
        tool_message_content = f"Error: '{new_stage}' is not a recognized sales stage."
        state_updates["messages"] = [
            ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
        ]
        return Command(update=state_updates)

    state_updates["current_sales_stage"] = new_stage
    tool_message_content = f"Sales stage successfully updated to: '{new_stage}'."

    if state and state.current_sales_stage == new_stage:
        tool_message_content = f"Sales stage is already '{new_stage}'. No change made."
        # No need to add current_sales_stage to state_updates if no change
        if "current_sales_stage" in state_updates:
            del state_updates["current_sales_stage"]

    logger.info(f"[{tool_name}] {tool_message_content}")
    state_updates["messages"] = [
        ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
    ]

    return Command(update=state_updates)
