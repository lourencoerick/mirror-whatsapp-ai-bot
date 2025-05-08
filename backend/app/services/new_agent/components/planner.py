# backend/app/services/ai_reply/new_agent/components/planner.py

from typing import Dict, List, Optional, Any, Tuple, cast
from loguru import logger
import copy

# Importar definições de estado e schemas
from ..state_definition import (
    RichConversationState,
    UserInterruption,
    AgentGoal,
    AgentGoalType,
    AgentActionType,
    AgentActionDetails,
    SpinQuestionType,
    PendingAgentAction,
    IdentifiedNeedEntry,
    IdentifiedObjectionEntry,
    IdentifiedPainPointEntry,
    DynamicCustomerProfile,
    ProposedSolution,
)

INTERRUPTION_TO_ACTION_MAP: Dict[str, AgentActionType] = {
    "direct_question": "ANSWER_DIRECT_QUESTION",
    "objection": "GENERATE_REBUTTAL",
    "vague_statement": "ASK_CLARIFYING_QUESTION",
    "off_topic_comment": "ACKNOWLEDGE_AND_TRANSITION",
}
MAX_SPIN_QUESTIONS_PER_CYCLE = 5
MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION = 2


# --- Helper Functions ---


def _find_priority_interruption(
    queue: List[UserInterruption],
) -> Optional[UserInterruption]:
    """
    Finds the highest priority pending interruption in the queue.

    Current priority order (highest to lowest):
    Objection > Direct Question > Vague Statement > Off-Topic Comment.

    Args:
        queue: The list of user interruption dictionaries from the state.

    Returns:
        The highest priority pending interruption dictionary, or None if no
        pending interruptions are found.
    """
    # Priority: Objection > Question > Vague > OffTopic
    for type_to_check in [
        "objection",
        "direct_question",
        "vague_statement",
        "off_topic_comment",
    ]:
        for interruption in queue:
            if (
                interruption.get("status") == "pending_resolution"
                and interruption.get("type") == type_to_check
            ):
                return interruption
    return None


def _get_goal_for_interruption(
    interruption: UserInterruption,
) -> Tuple[AgentGoalType, Dict[str, Any]]:
    """
    Determines the temporary goal type and details based on an interruption.

    Maps an interruption type to a corresponding temporary agent goal
    (e.g., HANDLING_OBJECTION, CLARIFYING_USER_INPUT) and extracts relevant
    details from the interruption object.

    Args:
        interruption: The user interruption dictionary.

    Returns:
        A tuple containing the determined AgentGoalType and a dictionary
        with goal-specific details (like the objection text or question text).
    """
    interruption_type = interruption.get("type")
    interruption_text = interruption.get("text", "")
    goal_type: AgentGoalType = "IDLE"  # Default, should be overwritten
    goal_details: Dict[str, Any] = {}

    if interruption_type == "objection":
        goal_type = "HANDLING_OBJECTION"
        goal_details = {"original_objection_text": interruption_text}
    elif interruption_type == "direct_question":
        goal_type = (
            "CLARIFYING_USER_INPUT"  # Should be ANSWER_DIRECT_QUESTION or similar
        )
        goal_details = {"text": interruption_text, "clarification_type": "question"}
    elif interruption_type == "vague_statement":
        goal_type = "CLARIFYING_USER_INPUT"
        goal_details = {"text": interruption_text, "clarification_type": "vague"}
    elif interruption_type == "off_topic_comment":
        goal_type = "ACKNOWLEDGE_AND_TRANSITION"
        goal_details = {"reason": "Handling off-topic", "text": interruption_text}
    else:
        logger.warning(f"Unknown interruption type '{interruption_type}' encountered.")
        goal_type = "CLARIFYING_USER_INPUT"  # Fallback
        goal_details = {"text": interruption_text, "clarification_type": "unknown"}

    return goal_type, goal_details


def _get_previous_goal_to_store(
    current_goal: AgentGoal, goal_type_for_interruption: AgentGoalType
) -> Optional[AgentGoal]:
    """
    Determines which goal to store as the 'previous_goal_if_interrupted'.

    This prevents nesting temporary goals (like handling an objection while
    already handling a question). If the current goal is already a temporary
    one, its own 'previous_goal' is stored instead.

    Args:
        current_goal: The goal active before the interruption was detected.
        goal_type_for_interruption: The type of the new temporary goal being set.

    Returns:
        The goal object (as a dictionary) to be stored in the
        'previous_goal_if_interrupted' field of the new temporary goal,
        or None if no previous goal should be stored.
    """
    # If the interruption goal is the same as the current one, keep the existing previous goal
    if current_goal.get("goal_type") == goal_type_for_interruption:
        return current_goal.get("previous_goal_if_interrupted")
    # Otherwise, store the current goal only if it wasn't already a temporary/interrupt goal
    elif current_goal.get("goal_type") not in [
        "HANDLING_OBJECTION",
        "CLARIFYING_USER_INPUT",
        "ACKNOWLEDGE_AND_TRANSITION",
    ]:
        return current_goal
    else:  # If current goal was already temporary, store its previous goal instead
        return current_goal.get("previous_goal_if_interrupted")


def _check_goal_resumption(
    current_goal: AgentGoal,
    customer_profile: DynamicCustomerProfile,
    interruptions_queue: List[UserInterruption],  # Added to check if queue is clear
) -> Tuple[bool, Optional[AgentGoal]]:
    """
    Checks if the agent should resume a previously interrupted goal.

    Resumption occurs if the current goal is a temporary one and the condition
    for its completion is met (e.g., no more pending interruptions of that type,
    or the handled objection is marked as 'resolved').

    Args:
        current_goal: The current goal object from the state.
        customer_profile: The dynamic customer profile dictionary.
        interruptions_queue: The current user interruptions queue.

    Returns:
        A tuple containing:
            - bool: True if a previous goal should be resumed, False otherwise.
            - Optional[AgentGoal]: The goal object to be resumed, or None.
    """
    previous_goal_to_resume = current_goal.get("previous_goal_if_interrupted")
    if not previous_goal_to_resume:
        return False, None

    current_goal_type = current_goal.get("goal_type")

    # Check if there are any PENDING interruptions. If so, don't resume yet.
    # This is a general guard unless the specific goal logic below overrides it.
    has_pending_interruptions = any(
        interruption.get("status") == "pending_resolution"
        for interruption in interruptions_queue
    )

    if current_goal_type in ["CLARIFYING_USER_INPUT", "ACKNOWLEDGE_AND_TRANSITION"]:
        # These goals are considered "done" after one action.
        # Resume if no *other* higher priority interruptions are pending.
        # We need to be careful not to get stuck if the interruption queue isn't cleared properly.
        # For now, let's assume if we are in these states, the interruption that caused them
        # is being handled by the current action.
        # The _find_priority_interruption will be checked again at the start of the next planner cycle.
        if not has_pending_interruptions:  # Only resume if queue is clear
            logger.info(
                f"Temporary goal {current_goal_type} completed and no other pending interruptions. Attempting to resume."
            )
            return True, previous_goal_to_resume
        else:
            logger.debug(
                f"Temporary goal {current_goal_type} completed, but other interruptions are pending. Not resuming yet."
            )
            return False, None

    elif current_goal_type == "HANDLING_OBJECTION":
        original_objection_text = current_goal.get("goal_details", {}).get(
            "original_objection_text"
        )
        if original_objection_text:
            obj_entry = _find_objection_in_profile(
                customer_profile, original_objection_text
            )
            if obj_entry and obj_entry.get("status") == "resolved":
                # Also ensure no *other* higher-priority objections are now active
                if not _find_priority_interruption(
                    interruptions_queue
                ):  # Check if queue is clear of other issues
                    logger.info(
                        f"Objection '{original_objection_text}' resolved and no other interruptions. Attempting to resume."
                    )
                    return True, previous_goal_to_resume
                else:
                    logger.debug(
                        f"Objection '{original_objection_text}' resolved, but other interruptions pending. Not resuming yet."
                    )
                    return False, None
            logger.debug(
                f"HANDLING_OBJECTION resumption check failed: Objection '{original_objection_text}' status is '{obj_entry.get('status') if obj_entry else 'Not Found'}'."
            )
            return False, None
        else:
            logger.warning(
                "HANDLING_OBJECTION goal lacks original_objection_text detail. Cannot check for resumption."
            )
            return False, None

    return False, None


def _find_objection_in_profile(
    customer_profile: DynamicCustomerProfile, objection_text: str
) -> Optional[IdentifiedObjectionEntry]:
    """
    Finds a specific objection entry in the profile by its text.

    Args:
        customer_profile: The dynamic customer profile dictionary.
        objection_text: The exact text of the objection to find.

    Returns:
        The found objection entry dictionary (TypedDict) or None if not found.
    """
    if objection_text is None:
        return None
    for obj_entry in customer_profile.get("identified_objections", []):
        if obj_entry.get("text") == objection_text:
            return obj_entry  # type: ignore
    return None


def _get_next_spin_type(last_spin_type: Optional[SpinQuestionType]) -> SpinQuestionType:
    """
    Determines the next SPIN question type in the standard S->P->I->N sequence.
    Loops back to 'Problem' after 'NeedPayoff'.

    Args:
        last_spin_type: The type of the last SPIN question asked, or None if starting.

    Returns:
        The next SpinQuestionType in the sequence.
    """
    if last_spin_type == "Situation":
        return "Problem"
    elif last_spin_type == "Problem":
        return "Implication"
    elif last_spin_type == "Implication":
        return "NeedPayoff"
    elif last_spin_type == "NeedPayoff":
        return "Problem"  # Loop back
    else:
        return "Situation"  # Default/start


def _select_product_and_benefit_for_presentation(
    customer_profile: DynamicCustomerProfile,
    company_profile_offerings: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Selects a product and key benefit to highlight based on identified needs.

    Prioritizes confirmed needs over active needs, sorting by priority and then
    turn number. Performs simple keyword matching between the highest priority
    need and the company's offerings. Defaults to the first offering if no
    match is found or if needs are unclear.

    Args:
        customer_profile: The dynamic customer profile dictionary.
        company_profile_offerings: A list of offering dictionaries from the
                                   company profile, expected to have 'name' and
                                   'short_description' keys.

    Returns:
        A tuple containing:
            - str: The name of the product selected for presentation.
            - str: A string describing the key benefit linked to the need.
    """
    product_to_present = "Nossa Solução Principal"
    key_benefit = "atender às suas necessidades gerais"
    identified_needs: List[IdentifiedNeedEntry] = customer_profile.get(
        "identified_needs", []
    )
    target_need: Optional[IdentifiedNeedEntry] = None

    needs_to_consider = sorted(
        [
            n for n in identified_needs if n.get("status") != "addressed_by_agent"
        ],  # Consider active or confirmed
        key=lambda x: (
            x.get("status") == "confirmed_by_user",  # True (1) before False (0)
            x.get("priority", 0),
            x.get("source_turn", 0),
        ),
        reverse=True,  # Highest priority first
    )

    if needs_to_consider:
        target_need = needs_to_consider[0]  # type: ignore

    if target_need:
        target_need_text = target_need.get("text", "sua necessidade principal")
        key_benefit = f"o seu desafio em relação a '{target_need_text}'"

        if company_profile_offerings:
            best_match_score = -1
            # Default to first offering if no better match
            best_match_product = (
                company_profile_offerings[0].get("name", product_to_present)
                if company_profile_offerings
                else product_to_present
            )

            try:
                need_keywords = {
                    kw for kw in target_need_text.lower().split() if len(kw) > 3
                }
                for offering in company_profile_offerings:
                    offering_name = offering.get("name", "").lower()
                    offering_desc = offering.get("short_description", "").lower()
                    offering_keywords = {
                        kw
                        for kw in (offering_name + " " + offering_desc).split()
                        if len(kw) > 3
                    }
                    match_score = len(need_keywords.intersection(offering_keywords))

                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_product = offering.get("name", best_match_product)
            except Exception as e:
                logger.warning(
                    f"Error during keyword matching for product selection: {e}"
                )

            product_to_present = best_match_product
            if best_match_score > 0:
                logger.debug(
                    f"Planner: Matched need '{target_need_text}' to product '{product_to_present}' (Score: {best_match_score})."
                )
            else:
                logger.debug(
                    f"Planner: No specific keyword match for need '{target_need_text}', defaulting to '{product_to_present}'."
                )
        else:
            logger.warning("Planner: No company offerings found to match needs.")

    return product_to_present, key_benefit


# --- Main Planner Node ---
async def goal_and_action_planner_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determines the agent's next goal and action based on the current state.

    This node acts as the central decision-making unit for the agent. It follows
    a prioritized flow:
    1. Check for high-priority goal transitions (e.g., buying signal detected).
    2. Check for and handle pending user interruptions (objections, questions, etc.).
    3. Check if a previous goal should be resumed (after handling an interruption).
    4. If none of the above apply, determine the next action based on the
       current effective goal's logic (e.g., continue SPIN, handle objection
       attempts, initiate closing steps).

    Args:
        state: The current conversation state dictionary.
        config: The graph configuration dictionary.

    Returns:
        A dictionary containing the state updates decided by the planner, including:
            - `current_agent_goal`: The determined goal for the next step.
            - `next_agent_action_command`: The specific action the agent should perform.
            - `action_parameters`: A dictionary of parameters needed for the action.
            - `user_interruptions_queue`: Updated queue if an interruption was handled.
            - `last_processing_error`: Cleared if planner runs successfully.
    """
    node_name = "goal_and_action_planner_node"
    current_turn = state.get("current_turn_number", 0)
    logger.info(f"--- Starting Node: {node_name} (Turn: {current_turn}) ---")

    current_goal_from_state = copy.deepcopy(
        state.get(
            "current_agent_goal",
            AgentGoal(
                goal_type="IDLE", previous_goal_if_interrupted=None, goal_details={}
            ),
        )
    )
    if current_goal_from_state.get("goal_details") is None:
        current_goal_from_state["goal_details"] = {}

    interruptions_queue = list(
        state.get("user_interruptions_queue", [])
    )  # Use list() for a mutable copy
    customer_profile = cast(
        DynamicCustomerProfile, copy.deepcopy(state.get("customer_profile_dynamic", {}))
    )
    last_agent_action = copy.deepcopy(state.get("last_agent_action"))
    company_profile = state.get("company_profile", {})

    effective_goal: AgentGoal = current_goal_from_state
    goal_determined_by_high_priority_transition = False
    goal_determined_by_interruption = False
    # resumed_goal_this_turn = False # We will check this later
    interruption_to_handle: Optional[UserInterruption] = None

    # 1. High-Priority Goal Transitions
    current_goal_type = effective_goal.get("goal_type")
    if current_goal_type == "PRESENTING_SOLUTION":
        last_intent = customer_profile.get("last_discerned_intent")
        active_objections = any(
            obj.get("status") == "active"
            for obj in customer_profile.get("identified_objections", [])
        )
        strong_buying_signal = (
            last_intent
            in ["RequestForNextStepInPurchase", "PositiveFeedbackToProposal"]
            and not active_objections
        )
        if strong_buying_signal:
            logger.info(
                f"[{node_name}] High-Priority Transition: Strong buying signal detected (Intent: {last_intent}). Transitioning to ATTEMPTING_CLOSE."
            )
            effective_goal = AgentGoal(
                goal_type="ATTEMPTING_CLOSE",
                goal_details={"closing_step": "initial_attempt"},
                previous_goal_if_interrupted=None,
            )
            goal_determined_by_high_priority_transition = True

    # 2. Handle Interruptions (if no high-priority transition)
    if not goal_determined_by_high_priority_transition:
        interruption_to_handle = _find_priority_interruption(interruptions_queue)
        if interruption_to_handle:
            logger.info(
                f"[{node_name}] Prioritizing interruption: Type='{interruption_to_handle.get('type')}', Text='{interruption_to_handle.get('text', '')[:50]}...'"
            )
            goal_type_for_interruption, goal_details_for_interruption = (
                _get_goal_for_interruption(interruption_to_handle)
            )
            previous_goal_to_store = _get_previous_goal_to_store(
                current_goal_from_state, goal_type_for_interruption
            )
            effective_goal = AgentGoal(
                goal_type=goal_type_for_interruption,
                previous_goal_if_interrupted=previous_goal_to_store,
                goal_details=goal_details_for_interruption,
            )
            goal_determined_by_interruption = True
        else:
            # 3. Goal Resumption (if no interruption)
            should_resume, goal_to_resume = _check_goal_resumption(
                current_goal_from_state, customer_profile, interruptions_queue
            )
            if should_resume and goal_to_resume:
                logger.info(
                    f"[{node_name}] Resuming previous goal: {goal_to_resume.get('goal_type')}"
                )
                effective_goal = copy.deepcopy(goal_to_resume)
                effective_goal["previous_goal_if_interrupted"] = (
                    None  # Clear it as we are resuming
                )
                # Reset goal-specific details upon resumption for certain goals
                # if effective_goal.get("goal_type") == "INVESTIGATING_NEEDS":
                #     effective_goal["goal_details"] = {
                #         "spin_questions_asked_this_cycle": 0,
                #         "last_spin_type_asked": None,
                #     }
                if effective_goal.get("goal_type") == "ATTEMPTING_CLOSE":
                    # When resuming ATTEMPTING_CLOSE, we might need to re-evaluate the step
                    # For now, let's assume it resumes to 'initial_attempt' or the planner logic will pick the right step.
                    # If it had specific sub-steps, those might need to be reset or re-evaluated.
                    # The current logic for ATTEMPTING_CLOSE re-evaluates based on `closing_process_status`.
                    if effective_goal.get("goal_details") is None:
                        effective_goal["goal_details"] = {}  # Ensure it exists
                    effective_goal["goal_details"]["closing_step"] = effective_goal.get(
                        "goal_details", {}
                    ).get("closing_step", "initial_attempt")

                elif effective_goal.get("goal_details") is None:  # General fallback
                    effective_goal["goal_details"] = {}

    if effective_goal.get("goal_details") is None:
        effective_goal["goal_details"] = {}

    logger.info(
        f"[{node_name}] Effective goal for planning: {effective_goal.get('goal_type')}"
    )
    if effective_goal.get("goal_details"):
        logger.debug(
            f"[{node_name}] Effective goal details: {effective_goal.get('goal_details')}"
        )

    # --- Plan Action Based on Effective Goal and State ---
    planned_action_command: Optional[AgentActionType] = None
    planned_action_parameters: AgentActionDetails = {}
    effective_goal_type = effective_goal.get("goal_type", "IDLE")

    # --- Action Planning Logic per Goal ---
    if effective_goal_type == "HANDLING_OBJECTION":
        original_objection_text = effective_goal.get("goal_details", {}).get(
            "original_objection_text"
        )
        if original_objection_text:
            obj_entry = _find_objection_in_profile(
                customer_profile, original_objection_text
            )
            if obj_entry and obj_entry.get("status") == "active":
                attempts = obj_entry.get("rebuttal_attempts", 0)
                if attempts < MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION:
                    logger.info(
                        f"[{node_name}] Objection '{original_objection_text[:30]}' active (attempt {attempts+1} needed). Planning rebuttal."
                    )
                    planned_action_command = "GENERATE_REBUTTAL"
                    planned_action_parameters["objection_text_to_address"] = (
                        original_objection_text
                    )
                else:  # Max attempts reached
                    logger.warning(
                        f"[{node_name}] Max rebuttal attempts ({attempts}) reached for objection '{original_objection_text[:30]}'. Transitioning to ENDING_CONVERSATION."
                    )
                    effective_goal["goal_type"] = "ENDING_CONVERSATION"
                    effective_goal["goal_details"] = {
                        "reason": f"Impasse on objection: {original_objection_text}"
                    }
                    effective_goal["previous_goal_if_interrupted"] = (
                        None  # Clear, this is a terminal state for the objection
                    )
                    planned_action_command = (
                        "GENERATE_FAREWELL"  # Or a specific impasse handling message
                    )
                    planned_action_parameters = {
                        "reason": f"Impasse sobre a objeção: {original_objection_text[:50]}..."
                    }

            elif obj_entry and obj_entry.get("status") == "addressing":
                logger.info(
                    f"[{node_name}] Objection '{original_objection_text[:30]}' is 'addressing'. Waiting for user response."
                )
                planned_action_command = None  # Wait for user
            else:  # Objection resolved or ignored
                logger.info(
                    f"[{node_name}] In HANDLING_OBJECTION goal, but objection '{original_objection_text[:30]}' is not 'active' or 'addressing' (Status: {obj_entry.get('status') if obj_entry else 'Not Found'}). No action planned for this goal now."
                )
                # This state should ideally lead to goal resumption if the objection is resolved.
                # If it's not resolved and not active/addressing, it's an odd state.
                planned_action_command = None
        else:
            logger.warning(
                f"[{node_name}] In HANDLING_OBJECTION goal, but no original_objection_text found. Waiting."
            )
            planned_action_command = None

    elif effective_goal_type == "CLARIFYING_USER_INPUT":
        clarification_type = effective_goal.get("goal_details", {}).get(
            "clarification_type"
        )
        text_to_clarify = effective_goal.get("goal_details", {}).get("text")

        if clarification_type == "question" and text_to_clarify:
            planned_action_command = "ANSWER_DIRECT_QUESTION"
            planned_action_parameters["question_to_answer_text"] = text_to_clarify
        elif clarification_type == "vague" and text_to_clarify:
            planned_action_command = "ASK_CLARIFYING_QUESTION"
            # No specific params needed beyond what ResponseGenerator picks from goal_details
        else:
            logger.warning(
                f"Unknown or incomplete clarification type: {clarification_type} for text '{text_to_clarify}'. Defaulting to ASK_CLARIFYING_QUESTION."
            )
            planned_action_command = "ASK_CLARIFYING_QUESTION"

    elif effective_goal_type == "ACKNOWLEDGE_AND_TRANSITION":
        planned_action_command = "ACKNOWLEDGE_AND_TRANSITION"
        planned_action_parameters["off_topic_text"] = effective_goal.get(
            "goal_details", {}
        ).get("text", "[comentário anterior]")
        prev_goal_topic = "o assunto anterior"
        prev_goal_obj = effective_goal.get("previous_goal_if_interrupted")
        if prev_goal_obj and isinstance(prev_goal_obj, dict):  # Check if it's a dict
            prev_goal_type_stored = prev_goal_obj.get("goal_type")
            if prev_goal_type_stored == "INVESTIGATING_NEEDS":
                prev_goal_topic = "suas necessidades"
            elif prev_goal_type_stored == "PRESENTING_SOLUTION":
                prev_goal_topic = "nossa solução"
            elif prev_goal_type_stored == "ATTEMPTING_CLOSE":
                prev_goal_topic = "os próximos passos para o pedido"
        planned_action_parameters["previous_goal_topic"] = prev_goal_topic

    elif effective_goal_type == "INVESTIGATING_NEEDS":
        spin_details = effective_goal.get("goal_details", {})
        spin_questions_asked = spin_details.get("spin_questions_asked_this_cycle", 0)
        last_spin_type_asked = spin_details.get("last_spin_type_asked")
        should_exit_spin, exit_reason = False, ""
        confirmed_needs = [
            n
            for n in customer_profile.get("identified_needs", [])
            if n.get("status") == "confirmed_by_user"
        ]
        if confirmed_needs and last_spin_type_asked == "NeedPayoff":
            should_exit_spin, exit_reason = (
                True,
                f"Confirmed need(s) after NeedPayoff: {[n.get('text','N/A') for n in confirmed_needs]}",
            )
        elif spin_questions_asked >= MAX_SPIN_QUESTIONS_PER_CYCLE:
            should_exit_spin, exit_reason = (
                True,
                f"Max SPIN questions ({MAX_SPIN_QUESTIONS_PER_CYCLE}) reached.",
            )

        if should_exit_spin:
            logger.info(f"[{node_name}] Transitioning from SPIN. Reason: {exit_reason}")
            effective_goal["goal_type"] = "PRESENTING_SOLUTION"
            product_to_present, key_benefit = (
                _select_product_and_benefit_for_presentation(
                    customer_profile, company_profile.get("offering_overview", [])
                )
            )
            planned_action_command = "PRESENT_SOLUTION_OFFER"
            planned_action_parameters = {
                "product_name_to_present": product_to_present,
                "key_benefit_to_highlight": key_benefit,
            }
            effective_goal["goal_details"] = {  # Reset details for new goal
                "presenting_product": product_to_present,
                "main_benefit_focus": key_benefit,
            }
        else:
            next_spin_type = _get_next_spin_type(last_spin_type_asked)
            planned_action_command = "ASK_SPIN_QUESTION"
            planned_action_parameters["spin_type"] = next_spin_type
            # Update goal_details for the current goal
            effective_goal["goal_details"]["spin_questions_asked_this_cycle"] = (
                spin_questions_asked + 1
            )
            effective_goal["goal_details"]["last_spin_type_asked"] = next_spin_type

    elif effective_goal_type == "PRESENTING_SOLUTION":
        if (
            last_agent_action
            and last_agent_action.get("action_type") == "PRESENT_SOLUTION_OFFER"
        ):
            logger.info(
                f"[{node_name}] Agent just presented solution. Waiting for user response."
            )
            planned_action_command = None  # Wait for user
        else:
            # This case implies we entered PRESENTING_SOLUTION goal but haven't acted yet.
            # This could happen if transitioned from SPIN but didn't immediately present.
            logger.info(
                f"[{node_name}] In PRESENTING_SOLUTION goal, action not yet taken or user responded to something else. Re-evaluating presentation."
            )
            product_to_present, key_benefit = (
                _select_product_and_benefit_for_presentation(
                    customer_profile, company_profile.get("offering_overview", [])
                )
            )
            planned_action_command = "PRESENT_SOLUTION_OFFER"
            planned_action_parameters = {
                "product_name_to_present": product_to_present,
                "key_benefit_to_highlight": key_benefit,
            }
            effective_goal["goal_details"] = {
                "presenting_product": product_to_present,
                "main_benefit_focus": key_benefit,
            }

    elif effective_goal_type == "ATTEMPTING_CLOSE":
        closing_status = state.get("closing_process_status", "not_started")
        active_proposal = state.get("active_proposal")
        active_proposal_dict = (
            active_proposal if isinstance(active_proposal, dict) else {}
        )
        last_intent = customer_profile.get("last_discerned_intent")

        # --- Verificação de Retomada Primeiro ---
        # was_resumed_after_interrupt: Checa se o goal ANTES da lógica de retomada NÃO era ATTEMPTING_CLOSE,
        # mas o goal EFETIVO AGORA É ATTEMPTING_CLOSE.
        was_resumed_this_cycle = (
            current_goal_from_state.get("goal_type") != "ATTEMPTING_CLOSE"
            and effective_goal_type == "ATTEMPTING_CLOSE"
        )
        positive_intent_to_proceed = last_intent in [
            "RequestForNextStepInPurchase",
            "ConfirmingCloseAttempt",
            "PositiveFeedbackToProposal",
            "FinalOrderConfirmation",
        ]

        if (
            was_resumed_this_cycle
            and positive_intent_to_proceed
            and closing_status == "attempt_made"
        ):
            # Caso especial: Retomamos o fechamento após interrupção resolvida E o usuário quer prosseguir.
            logger.info(
                f"[{node_name}] Resumed ATTEMPTING_CLOSE after resolved interruption with positive intent. Planning CONFIRM_ORDER_DETAILS."
            )
            planned_action_command = "CONFIRM_ORDER_DETAILS"
            if active_proposal_dict:
                planned_action_parameters["product_name"] = active_proposal_dict.get(
                    "product_name"
                )
                planned_action_parameters["price"] = active_proposal_dict.get("price")
                planned_action_parameters["price_info"] = active_proposal_dict.get(
                    "price_info"
                )
            effective_goal["goal_details"]["closing_step"] = "confirming_details"
            # O StateUpdater deve mudar o status para awaiting_confirmation no próximo ciclo baseado neste intent.

        # --- Lógica Normal Baseada no Status ---
        elif closing_status == "awaiting_confirmation":
            logger.info(
                f"[{node_name}] Closing status 'awaiting_confirmation'. Planning CONFIRM_ORDER_DETAILS."
            )
            planned_action_command = "CONFIRM_ORDER_DETAILS"
            if active_proposal_dict:
                planned_action_parameters["product_name"] = active_proposal_dict.get(
                    "product_name"
                )
                planned_action_parameters["price"] = active_proposal_dict.get("price")
                planned_action_parameters["price_info"] = active_proposal_dict.get(
                    "price_info"
                )
            effective_goal["goal_details"]["closing_step"] = "confirming_details"

        elif closing_status == "confirmed_success":
            logger.info(
                f"[{node_name}] Closing status 'confirmed_success'. Planning PROCESS_ORDER_CONFIRMATION."
            )
            planned_action_command = "PROCESS_ORDER_CONFIRMATION"
            if active_proposal_dict:
                planned_action_parameters["product_name"] = active_proposal_dict.get(
                    "product_name"
                )
            effective_goal["goal_details"]["closing_step"] = "processing"

        elif closing_status == "needs_correction":
            logger.info(
                f"[{node_name}] Closing status 'needs_correction'. Planning HANDLE_CLOSING_CORRECTION."
            )
            planned_action_command = "HANDLE_CLOSING_CORRECTION"
            context_for_correction = "Estávamos finalizando seu pedido."
            if (
                last_agent_action
                and last_agent_action.get("action_type") == "CONFIRM_ORDER_DETAILS"
            ):
                context_for_correction = "Estávamos confirmando os detalhes do pedido."
            planned_action_parameters["context"] = context_for_correction
            effective_goal["goal_details"]["closing_step"] = "handling_correction"

        elif closing_status == "confirmation_rejected":
            logger.info(
                f"[{node_name}] Closing status 'confirmation_rejected'. Transitioning to ENDING_CONVERSATION."
            )
            effective_goal["goal_type"] = "ENDING_CONVERSATION"
            effective_goal["goal_details"] = {"reason": "Closing attempt rejected"}
            effective_goal["previous_goal_if_interrupted"] = None
            planned_action_command = "GENERATE_FAREWELL"
            planned_action_parameters["reason"] = "Closing attempt rejected"

        # --- Caso de Iniciar o Fechamento (ou esperar se acabou de iniciar) ---
        elif closing_status in [
            "not_started",
            "attempt_made",
        ]:  # Se não caiu no caso de retomada acima
            if (
                last_agent_action
                and last_agent_action.get("action_type") == "INITIATE_CLOSING"
            ):
                logger.info(
                    f"[{node_name}] Agent just initiated closing (status={closing_status}). Waiting for user response."
                )
                planned_action_command = None
            else:
                # Se o status é 'attempt_made' mas não estamos retomando com intent positivo,
                # significa que o usuário ainda não respondeu claramente ao INITIATE_CLOSING. Esperar.
                if closing_status == "attempt_made":
                    logger.info(
                        f"[{node_name}] Closing status is 'attempt_made', but no clear positive intent or not resuming. Waiting."
                    )
                    planned_action_command = None
                else:  # Status é 'not_started'
                    logger.info(
                        f"[{node_name}] Initiating closing process (status={closing_status}). Planning INITIATE_CLOSING."
                    )
                    planned_action_command = "INITIATE_CLOSING"
                    effective_goal["goal_details"]["closing_step"] = "initial_attempt"
                    if active_proposal_dict:
                        planned_action_parameters["product_name"] = (
                            active_proposal_dict.get("product_name")
                        )
                        planned_action_parameters["price"] = active_proposal_dict.get(
                            "price"
                        )

        else:  # Status desconhecido
            logger.warning(
                f"[{node_name}] Unhandled closing_status '{closing_status}' in ATTEMPTING_CLOSE goal. Waiting."
            )
            planned_action_command = None
    elif effective_goal_type == "ENDING_CONVERSATION":
        # Ensure we don't repeatedly send farewell if already done.
        if not (
            last_agent_action
            and last_agent_action.get("action_type") == "GENERATE_FAREWELL"
        ):
            logger.info(
                f"[{node_name}] In ENDING_CONVERSATION goal. Planning farewell."
            )
            planned_action_command = "GENERATE_FAREWELL"
            planned_action_parameters = {
                "reason": effective_goal.get("goal_details", {}).get(
                    "reason", "concluding"
                )
            }
        else:
            logger.info(f"[{node_name}] Farewell already sent. No further action.")
            planned_action_command = None

    elif effective_goal_type == "IDLE" or effective_goal_type == "GREETING":
        # Assuming GREETING goal leads to INVESTIGATING_NEEDS after the initial greeting message.
        if (
            last_agent_action
            and last_agent_action.get("action_type") == "GENERATE_GREETING"
        ):
            logger.info(
                f"[{node_name}] Greeting sent. Transitioning to INVESTIGATING_NEEDS."
            )
            effective_goal["goal_type"] = "INVESTIGATING_NEEDS"
            planned_action_command = "ASK_SPIN_QUESTION"  # Start SPIN
            planned_action_parameters["spin_type"] = "Situation"
            effective_goal["goal_details"] = {
                "spin_questions_asked_this_cycle": 0,
                "last_spin_type_asked": None,
            }
        elif not last_agent_action:  # True IDLE or start of conversation
            logger.info(
                f"[{node_name}] Goal is IDLE or GREETING (initial). Planning GREETING."
            )
            planned_action_command = "GENERATE_GREETING"
            effective_goal["goal_type"] = "GREETING"  # Ensure goal is GREETING
            effective_goal["goal_details"] = {}
        else:  # Already greeted, but not yet transitioned (should be rare)
            logger.info(
                f"[{node_name}] Goal is {effective_goal_type}, already acted. Waiting or re-evaluating."
            )
            planned_action_command = None

    # --- Update Interrupt Queue ---
    updated_interruptions_queue = list(interruptions_queue)  # Work with a copy
    if (
        goal_determined_by_interruption  # An interruption was chosen to be handled
        and planned_action_command  # And an action was planned for it
        and interruption_to_handle  # And we know which interruption it was
    ):
        # Attempt to remove the specific interruption that was handled.
        # This is tricky if multiple interruptions of the same type/text exist.
        # A more robust way would be to give interruptions unique IDs.
        # For now, remove the first match.
        try:
            # Find the index of the interruption_to_handle in the original queue
            idx_to_remove = -1
            for i, item in enumerate(updated_interruptions_queue):
                # Simple comparison, might need to be more robust if interruptions can be identical
                if item == interruption_to_handle:
                    idx_to_remove = i
                    break

            if idx_to_remove != -1:
                updated_interruptions_queue.pop(idx_to_remove)
                logger.debug(
                    f"[{node_name}] Removed handled interruption from queue: {interruption_to_handle.get('type')}"
                )
            else:
                logger.warning(
                    f"[{node_name}] Could not find exact interruption to remove from queue: {interruption_to_handle}. Queue: {updated_interruptions_queue}"
                )
        except Exception as e:  # Broad catch for safety
            logger.warning(f"[{node_name}] Error removing interruption from queue: {e}")

    # --- Prepare Delta ---
    updated_state_delta: Dict[str, Any] = {}
    updated_state_delta["current_agent_goal"] = effective_goal

    # Only update queue in delta if it actually changed
    if updated_interruptions_queue != interruptions_queue:  # Compare with original copy
        updated_state_delta["user_interruptions_queue"] = updated_interruptions_queue

    if planned_action_command:
        updated_state_delta["next_agent_action_command"] = planned_action_command
        updated_state_delta["action_parameters"] = planned_action_parameters
        logger.info(
            f"[{node_name}] Planned Action: {planned_action_command}, Params: {planned_action_parameters}"
        )
    else:
        # Ensure these are explicitly set to None/empty if no action is planned
        # This helps clear them from previous turns if they were set.
        updated_state_delta["next_agent_action_command"] = None
        updated_state_delta["action_parameters"] = {}
        logger.info(f"[{node_name}] No specific action planned for this turn.")

    updated_state_delta["last_processing_error"] = None
    logger.info(
        f"[{node_name}] Planner finished. Final Planned Goal: {effective_goal.get('goal_type')}"
    )
    return updated_state_delta
