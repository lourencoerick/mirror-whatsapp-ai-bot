from typing import Optional, Dict, Any, get_args, List
from loguru import logger
from typing_extensions import Annotated

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage, BaseMessage, AIMessage
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


@tool
async def validate_response_and_references(
    reasoning_steps: List[str],
    information_sources: List[str],
    compliance_declaration: str,
    correct_format_output_declaration: str,
    used_sales_principles_declaration: str,
    proposed_response_to_user: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    IMPORTANT INTERNAL CHECK: Before you send any direct answer to the user,
    you MUST call this tool. This is your final quality check.

    To use this tool, first prepare these SIX things:
    1. `reasoning_steps`: Detail step-by-step how you arrived at your planned response.
    2. `information_sources`: List exactly where each piece of factual information in
       your planned response came from (e.g., "Company Profile field X",
       "Output from 'get_offering_details_by_id' tool", "Knowledge Base document Y").
       If using general knowledge, state "General knowledge". Be specific.
    3. `compliance_declaration`: A statement from you confirming that any 'next steps'
       or specific offers you are proposing in your `proposed_response_to_user` have
       been checked against available company information (from the Company Profile
       or tool outputs) and are feasible for the company to offer or for you (AI) to execute.
       If you used the `suggest_objection_response_strategy`, it is not a source of truth, it is just a advisor for you, you have to base your response on the company profile, offering tools, and knowledge base.
       Example: "I have verified that the proposed next steps (e.g., discussing payment plans)
       are consistent with the company's offerings as per the 'get_offering_details_by_id' tool output."
    4. `correct_format_output_declaration`: A statement confirming that you formatted the output—using appropriate line spacing, clear organization, and bullet points where applicable—to ensure the conversation flows naturally and is easy to understand, and that you used the tool’s information to SUPPORT your final messages and not copied and paste the text, i.e., rewrote everything as needed to maintain a smooth dialogue.
    5. `used_sales_principles_declaration`: A statement from you confirming that you are using the communication rules and the sales principles provided in the instructions, and that you are being proactive and engaging the customer toward the next step of the sale without sharing princing and checkout information before qualifying the lead, unless that the customer insists.
    6. `proposed_response_to_user`: The complete, final message text you intend to
       send to the user.

    This tool will review your preparation.
    - If approved, the `ToolMessage` content you receive back WILL BE your
      `proposed_response_to_user`. You should then use this content as your
      final AIMessage to the user.
    - If issues are found (in future versions), the `ToolMessage` content will
      contain "VALIDATION FEEDBACK" with instructions to revise your response.

    This step is mandatory to ensure accuracy and quality before communicating with the user.

    Args:
        reasoning_steps: Your step-by-step thought process.
        information_sources: Specific sources for all factual claims.
        compliance_declaration: Your statement confirming proposed next steps
                                are aligned with company capabilities and available information.
        correct_format_output_declaration: Your statement confirming that you formatted the message correctly
        used_sales_principles_declaration: Your statement confirming that you used the sales principles and followed the communication guidelines
        proposed_response_to_user: The exact response you plan to send.
        state: (Injected by system) Current conversation state.
        tool_call_id: (Injected by system) ID for this tool invocation.

    Returns:
        A Command object with a ToolMessage. If 'approved', ToolMessage content
        is your `proposed_response_to_user`. Otherwise, it contains feedback.
    """
    tool_name = "validate_response_and_references"
    logger.info(f"--- Executing Tool: {tool_name} (Call ID: {tool_call_id}) ---")
    logger.info(f"[{tool_name}] Validating proposed response.")
    logger.debug(f"[{tool_name}] Reasoning Steps: {reasoning_steps}")
    logger.debug(f"[{tool_name}] Information Sources: {information_sources}")
    logger.debug(f"[{tool_name}] Proposed Response: {proposed_response_to_user}")

    # --- "Fake" Validation Logic (Initial Version) ---
    validation_passed = True  # Always passes for now
    feedback_to_agent_llm = ""

    if not proposed_response_to_user:
        validation_passed = False
        feedback_to_agent_llm = (
            "Validation Error: Proposed response is empty. Please provide a response."
        )
    elif not reasoning_steps:
        validation_passed = False  # Or just a warning
        feedback_to_agent_llm = "Validation Warning: Reasoning steps were not provided. Please ensure to outline reasoning for future responses."
    elif not information_sources:
        validation_passed = False  # Or just a warning
        feedback_to_agent_llm = "Validation Warning: Information sources were not provided. Please cite sources for factual claims."
    elif not compliance_declaration:  # Check for the new field
        validation_passed = False  # For now, just a warning if missing
        feedback_to_agent_llm = "Validation Warning: Compliance declaration was not provided. Please verify it."
    elif not correct_format_output_declaration:  # Check for the new field
        validation_passed = False  # For now, just a warning if missing
        feedback_to_agent_llm = "Validation Warning: Format the output accordingly."

    elif not used_sales_principles_declaration:  # Check for the new field
        validation_passed = False  # For now, just a warning if missing
        feedback_to_agent_llm = (
            "Validation Warning: Use the sales principles and communications rules."
        )

    # In a real validator, you'd have more complex checks here.
    # For example, checking if sources are plausible, if reasoning aligns with response, etc.

    tool_message_content: str

    if validation_passed:
        # If validation passes, the content of the ToolMessage IS the response to be sent to the user.
        # The main agent LLM will see this ToolMessage and should then use its content as the final AIMessage.
        tool_message_content = proposed_response_to_user
        logger.info(f"[{tool_name}] Validation 'passed'. Approved response for user.")
    else:
        # If validation fails, the ToolMessage contains feedback for the LLM to revise.
        tool_message_content = f"VALIDATION FEEDBACK: {feedback_to_agent_llm} Please revise your previous response and reasoning, then try again. Do NOT send the previous response to the user."
        logger.warning(
            f"[{tool_name}] Validation 'failed'. Feedback: {feedback_to_agent_llm}"
        )

    messages_to_add: List[BaseMessage] = [
        ToolMessage(
            content=tool_message_content, name=tool_name, tool_call_id=tool_call_id
        )
    ]

    state_updates: Dict[str, Any] = {"messages": messages_to_add}

    return Command(update=state_updates)
