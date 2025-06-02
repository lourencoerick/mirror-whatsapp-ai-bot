import time  # For current timestamp
from typing import Optional, List, Literal, Dict, Any
from uuid import UUID
from loguru import logger
from langchain_core.tools import tool, InjectedToolCallId
from typing_extensions import Annotated
from langchain_core.messages import ToolMessage

from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from app.services.sales_agent.agent_state import AgentState, SalesStageLiteral

from app.services.sales_agent.agent_state import (
    AgentState,
    ShoppingCartItem,
    PendingFollowUpTrigger,
    FollowUpTypeLiteral,
)
from app.api.schemas.company_profile import OfferingInfo


# --- Tool: Schedule Follow-up ---
@tool
async def schedule_follow_up(
    delay_seconds: int,
    follow_up_reason: str,  # Using a simple string reason for now
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Schedules a follow-up reminder for the user.
    Use this if the user asks to be contacted later or if a follow-up seems
    appropriate (e.g., after sending a quote, or if they abandon a cart).

    Args:
        delay_seconds: The number of seconds from now when the follow-up should occur.
                       Example: 86400 for one day, 3600 for one hour.
        follow_up_reason: A brief context or reason for the follow-up. This will be
                          used to help formulate the follow-up message later.
                          E.g., "User considering Product X", "Cart abandonment check".
        state: Agent's current state.
        tool_call_id: The ID of the tool call.

    Returns:
        A Command object with updates for 'pending_follow_up_trigger',
        'current_sales_stage', and a ToolMessage.
    """
    pass
    tool_name = "schedule_follow_up"
    logger.info(f"--- Executing Tool: {tool_name} (Call ID: {tool_call_id}) ---")
    logger.info(f"[{tool_name}] Delay: {delay_seconds}s, Reason: '{follow_up_reason}'")

    state_updates: Dict[str, Any] = {}
    tool_message_content: str

    if not isinstance(delay_seconds, int) or delay_seconds <= 0:
        logger.warning(f"[{tool_name}] Invalid delay_seconds: {delay_seconds}")
        tool_message_content = (
            "Please provide a valid positive number of seconds for the follow-up delay."
        )
    else:
        current_timestamp = time.time()
        due_timestamp = current_timestamp + delay_seconds

        # Determine FollowUpTypeLiteral based on reason - can be more sophisticated
        # For now, let's use a generic one or try to infer.
        # This part can be enhanced by the LLM or more structured input.
        follow_up_type: FollowUpTypeLiteral = "custom_reminder"  # Default
        if "cart" in follow_up_reason.lower() and "abandon" in follow_up_reason.lower():
            follow_up_type = "cart_abandonment"
        elif "offer" in follow_up_reason.lower() or "quote" in follow_up_reason.lower():
            follow_up_type = "no_response_to_offer"

        # Create the PendingFollowUpTrigger object
        # Note: Pydantic models in state_updates will be handled by the serializer
        # if they are part of the Command's update dictionary.
        # The serializer should convert them to dicts if they are wrapped with __pydantic_model__.
        # Or, if they are directly assigned, Pydantic validation on AgentState will handle them.
        pending_trigger = PendingFollowUpTrigger(
            follow_up_type=follow_up_type,
            due_timestamp=due_timestamp,
            target_conversation_id=state.conversation_id,  # Assuming this is the right ID
            context={
                "reason": follow_up_reason,
                "current_cart_items_count": len(state.shopping_cart or []),
            },
        )

        # state.pending_follow_up_trigger = pending_trigger # Direct modification
        # state.current_sales_stage = "follow_up_scheduled" # Direct modification
        # Instead, put them in state_updates for the Command
        state_updates["pending_follow_up_trigger"] = pending_trigger.model_dump(
            mode="json"
        )  # Serialize to dict
        state_updates["current_sales_stage"] = (
            "follow_up_scheduled"  # This is a simple string
        )

        # Convert delay_seconds to human-readable format for the message
        if delay_seconds >= 86400:
            delay_str = f"{delay_seconds // 86400} day(s)"
        elif delay_seconds >= 3600:
            delay_str = f"{delay_seconds // 3600} hour(s)"
        else:
            delay_str = f"{delay_seconds // 60} minute(s)"

        tool_message_content = f"Okay, I've scheduled a follow-up for you in approximately {delay_str} regarding: '{follow_up_reason}'."
        logger.info(
            f"[{tool_name}] Follow-up scheduled. Due: {due_timestamp}. Trigger: {pending_trigger.model_dump_json(indent=2)}"
        )

    state_updates["messages"] = [
        ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
    ]
    return Command(update=state_updates)


# Assuming AgentState and SalesStageLiteral are accessible


@tool
async def update_sales_stage(
    new_stage: SalesStageLiteral,
    state: Annotated[
        AgentState, InjectedState
    ],  # InjectedState might not be needed if only returning Command
    tool_call_id: Annotated[str, InjectedToolCallId],
    reason: Optional[str] = None,  # Optional reason for logging/tracing
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

    # Basic validation (SalesStageLiteral itself provides type validation if Pydantic is used for args)
    # We can add more checks here if needed, e.g., valid transitions.
    # For now, we assume the LLM provides a valid SalesStageLiteral.

    # If you wanted to validate against the literal values explicitly:
    # valid_stages = get_args(SalesStageLiteral) # Needs from typing import get_args
    # if new_stage not in valid_stages:
    #     logger.warning(f"[{tool_name}] Invalid sales stage '{new_stage}' provided.")
    #     tool_message_content = f"Error: '{new_stage}' is not a recognized sales stage."
    #     state_updates["messages"] = [ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)]
    #     return Command(update=state_updates)

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
