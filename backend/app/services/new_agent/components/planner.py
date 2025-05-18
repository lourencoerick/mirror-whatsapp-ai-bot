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
    CustomerQuestionEntry,
    CustomerQuestionStatusType,
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
# (Helper functions _find_priority_interruption, _find_question_status_in_log,
# _get_goal_for_interruption, _get_previous_goal_to_store, _check_goal_resumption,
# _find_objection_in_profile, _get_next_spin_type,
# _select_product_and_benefit_for_presentation remain unchanged from your original)


def _find_priority_interruption(
    queue: List[UserInterruption],
) -> Optional[UserInterruption]:
    """
    Finds the highest priority pending interruption in the queue.
    """
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


def _find_question_status_in_log(
    question_log: List[CustomerQuestionEntry], question_text: str
) -> CustomerQuestionStatusType:
    """
    Finds the status of the most recent log entry for a given question text.
    Defaults to 'newly_asked' if not found.
    """
    if not question_text:
        return "newly_asked"

    normalized_question_text = question_text.strip().lower()
    for i in range(len(question_log) - 1, -1, -1):
        log_entry = question_log[i]
        log_core_text = log_entry.get("extracted_question_core", "")
        if log_core_text and log_core_text.strip().lower() == normalized_question_text:
            status = log_entry.get("status", "newly_asked")
            valid_statuses: List[CustomerQuestionStatusType] = [
                "newly_asked",
                "answered_satisfactorily",
                "answered_with_fallback",
                "pending_agent_answer",
                "repetition_after_satisfactory_answer",
                "repetition_after_fallback",
                "ignored_by_agent",
            ]
            return status if status in valid_statuses else "newly_asked"
    return "newly_asked"


def _get_goal_for_interruption(
    interruption: UserInterruption,
) -> Tuple[AgentGoalType, Dict[str, Any]]:
    """
    Determines the temporary goal type and details based on an interruption.
    """
    interruption_type = interruption.get("type")
    interruption_text = interruption.get("text", "")
    goal_type: AgentGoalType = "IDLE"
    goal_details: Dict[str, Any] = {}

    if interruption_type == "objection":
        goal_type = "HANDLING_OBJECTION"
        goal_details = {"original_objection_text": interruption_text}
    elif interruption_type == "direct_question":
        goal_type = "CLARIFYING_USER_INPUT"
        goal_details = {"text": interruption_text, "clarification_type": "question"}
    elif interruption_type == "vague_statement":
        goal_type = "CLARIFYING_USER_INPUT"
        goal_details = {"text": interruption_text, "clarification_type": "vague"}
    elif interruption_type == "off_topic_comment":
        goal_type = "ACKNOWLEDGE_AND_TRANSITION"
        goal_details = {"reason": "Handling off-topic", "text": interruption_text}
    else:
        logger.warning(f"Unknown interruption type '{interruption_type}' encountered.")
        goal_type = "CLARIFYING_USER_INPUT"
        goal_details = {"text": interruption_text, "clarification_type": "unknown"}
    return goal_type, goal_details


def _get_previous_goal_to_store(
    current_goal: AgentGoal, goal_type_for_interruption: AgentGoalType
) -> Optional[AgentGoal]:
    """
    Determines which goal to store as the 'previous_goal_if_interrupted'.
    """
    if current_goal.get("goal_type") == goal_type_for_interruption:
        return current_goal.get("previous_goal_if_interrupted")
    elif current_goal.get("goal_type") not in [
        "HANDLING_OBJECTION",
        "CLARIFYING_USER_INPUT",
        "ACKNOWLEDGE_AND_TRANSITION",
    ]:
        return current_goal
    else:
        return current_goal.get("previous_goal_if_interrupted")


def _check_goal_resumption(
    current_goal: AgentGoal,
    customer_profile: DynamicCustomerProfile,
    interruptions_queue: List[UserInterruption],
) -> Tuple[bool, Optional[AgentGoal]]:
    """
    Checks if the agent should resume a previously interrupted goal.
    """
    previous_goal_to_resume = current_goal.get("previous_goal_if_interrupted")
    if not previous_goal_to_resume:
        return False, None

    current_goal_type = current_goal.get("goal_type")
    has_pending_interruptions = any(
        interruption.get("status") == "pending_resolution"
        for interruption in interruptions_queue
    )

    if current_goal_type in ["CLARIFYING_USER_INPUT", "ACKNOWLEDGE_AND_TRANSITION"]:
        if not has_pending_interruptions:
            logger.info(
                f"Temporary goal {current_goal_type} completed. Attempting to resume."
            )
            return True, previous_goal_to_resume
        else:
            logger.debug(
                f"Temporary goal {current_goal_type} completed, but other interruptions pending."
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
                if not _find_priority_interruption(interruptions_queue):
                    logger.info(
                        f"Objection '{original_objection_text}' resolved. Attempting to resume."
                    )
                    return True, previous_goal_to_resume
                else:
                    logger.debug(
                        f"Objection '{original_objection_text}' resolved, but other interruptions pending."
                    )
                    return False, None
            logger.debug(
                f"HANDLING_OBJECTION resumption check: Objection status is '{obj_entry.get('status') if obj_entry else 'Not Found'}'."
            )
            return False, None
        else:
            logger.warning(
                "HANDLING_OBJECTION goal lacks original_objection_text detail."
            )
            return False, None
    return False, None


def _find_objection_in_profile(
    customer_profile: DynamicCustomerProfile, objection_text: str
) -> Optional[IdentifiedObjectionEntry]:
    """
    Finds a specific objection entry in the profile by its text.
    """
    if objection_text is None:
        return None
    for obj_entry in customer_profile.get("identified_objections", []):
        if obj_entry.get("text") == objection_text:
            return cast(IdentifiedObjectionEntry, obj_entry)
    return None


def _get_next_spin_type(last_spin_type: Optional[SpinQuestionType]) -> SpinQuestionType:
    """
    Determines the next SPIN question type in the standard S->P->I->N sequence.
    """
    if last_spin_type == "Situation":
        return "Problem"
    elif last_spin_type == "Problem":
        return "Implication"
    elif last_spin_type == "Implication":
        return "NeedPayoff"
    elif last_spin_type == "NeedPayoff":
        return "Problem"
    else:
        return "Situation"


def _select_product_and_benefit_for_presentation(
    customer_profile: DynamicCustomerProfile,
    company_profile_offerings: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Selects a product and key benefit to highlight based on identified needs.
    """
    product_to_present = "Nossa Solução Principal"
    key_benefit = "atender às suas necessidades gerais"
    identified_needs: List[IdentifiedNeedEntry] = customer_profile.get(
        "identified_needs", []
    )
    target_need: Optional[IdentifiedNeedEntry] = None

    needs_to_consider = sorted(
        [n for n in identified_needs if n.get("status") != "addressed_by_agent"],
        key=lambda x: (
            x.get("status") == "confirmed_by_user",
            x.get("priority") if isinstance(x.get("priority"), int) else 0,
            x.get("source_turn", 0),
        ),
        reverse=True,
    )

    if needs_to_consider:
        target_need = cast(IdentifiedNeedEntry, needs_to_consider[0])

    if target_need:
        target_need_text = target_need.get("text", "sua necessidade principal")
        key_benefit = f"o seu desafio em relação a '{target_need_text}'"
        if company_profile_offerings:
            best_match_score = -1
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
                logger.warning(f"Error during product selection keyword matching: {e}")
            product_to_present = best_match_product
            logger.debug(
                f"Planner: Matched need '{target_need_text}' to product '{product_to_present}'."
            )
        else:
            logger.warning("Planner: No company offerings found.")
    return product_to_present, key_benefit


# --- Main Planner Node ---
async def goal_and_action_planner_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determines the agent's next goal and action based on the current state.
    """
    node_name = "goal_and_action_planner_node"
    current_turn = state.get("current_turn_number", 0)
    logger.info(f"--- Starting Node: {node_name} (Turn: {current_turn}) ---")

    # MODIFICATION 1: Initialize updated_state_delta to clear proactive suggestion fields by default
    updated_state_delta: Dict[str, Any] = {
        "suggested_goal_type": None,
        "suggested_goal_details": None,
        "last_processing_error": None,
    }

    # MODIFICATION 2: Check for Replan Directive and set effective_goal if needed
    is_replan_from_proactive = False
    # This variable will hold the goal determined by either proactive suggestion or standard logic
    # It must be defined before the main action planning block.
    effective_goal: Optional[AgentGoal] = None

    if state.get("next_agent_action_command") == "REPLAN_WITH_SUGGESTED_GOAL":
        suggested_type = state.get("suggested_goal_type")
        suggested_details = state.get("suggested_goal_details")
        if suggested_type:
            logger.info(
                f"[{node_name}] Re-planning with proactively suggested goal: {suggested_type}, Details: {suggested_details}"
            )
            effective_goal = AgentGoal(
                goal_type=suggested_type,
                goal_details=(
                    copy.deepcopy(suggested_details) if suggested_details else {}
                ),
                previous_goal_if_interrupted=None,
            )
            is_replan_from_proactive = True
        else:
            logger.warning(
                f"[{node_name}] 'REPLAN_WITH_SUGGESTED_GOAL' was set, but no 'suggested_goal_type' found. Proceeding with normal planning."
            )
            # is_replan_from_proactive remains False, effective_goal will be set by standard logic

    # Load other state components
    user_analysis = state.get("user_input_analysis_result")
    interruptions_queue = list(state.get("user_interruptions_queue", []))
    customer_profile = cast(
        DynamicCustomerProfile, copy.deepcopy(state.get("customer_profile_dynamic", {}))
    )
    last_agent_action = copy.deepcopy(state.get("last_agent_action"))
    company_profile = state.get("company_profile", {})
    customer_question_log = state.get("customer_question_log", [])  # type: ignore
    trigger_event = state.get("trigger_event")

    # MODIFICATION 3: Conditional standard goal determination logic
    interruption_to_handle: Optional[UserInterruption] = (
        None  # Define for broader scope
    )

    if not is_replan_from_proactive:
        # Standard goal determination logic starts here
        if trigger_event == "follow_up_timeout" and state.get("follow_up_scheduled"):
            logger.info(
                f"[{node_name}] Follow-up timeout detected. Planning DECIDE_PROACTIVE_STEP."
            )
            current_attempts = state.get("follow_up_attempt_count", 0)
            max_attempts = state.get("agent_config", {}).get(
                "max_follow_up_attempts", 3
            )

            # This delta is returned directly, overwriting the initial updated_state_delta
            if current_attempts < max_attempts:
                timeout_delta = {
                    "current_agent_goal": copy.deepcopy(
                        state.get("current_agent_goal")
                    ),
                    "next_agent_action_command": "DECIDE_PROACTIVE_STEP",
                    "action_parameters": {
                        "trigger_source": "follow_up_timeout",
                        "current_follow_up_attempts": current_attempts,
                        "max_follow_up_attempts_total": max_attempts,
                    },
                    "user_interruptions_queue": interruptions_queue,
                    "last_processing_error": None,
                    "trigger_event": None,
                    "follow_up_attempt_count": current_attempts + 1,
                    "suggested_goal_type": None,
                    "suggested_goal_details": None,
                }
                logger.info(
                    f"[{node_name}] Proceeding with proactive step for follow-up (attempt state to be {current_attempts + 1})."
                )
                return timeout_delta
            else:  # Max attempts reached
                logger.warning(
                    f"[{node_name}] Max follow-up attempts ({max_attempts}) reached. Ending."
                )
                farewell_goal = AgentGoal(
                    goal_type="ENDING_CONVERSATION",
                    goal_details={
                        "reason": f"Inactivity after {max_attempts} follow-ups."
                    },
                    previous_goal_if_interrupted=None,
                )
                timeout_farewell_delta = {
                    "current_agent_goal": farewell_goal,
                    "next_agent_action_command": "GENERATE_FAREWELL",
                    "action_parameters": {
                        "reason": "Inatividade prolongada do usuário."
                    },
                    "user_interruptions_queue": [],
                    "last_processing_error": None,
                    "trigger_event": None,
                    "follow_up_scheduled": False,
                    "follow_up_attempt_count": current_attempts,
                    "suggested_goal_type": None,
                    "suggested_goal_details": None,
                }
                return timeout_farewell_delta

        # 1. High-Priority Goal Transitions
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

        effective_goal = current_goal_from_state
        goal_determined_by_high_priority_transition = False

        last_intent = customer_profile.get("last_discerned_intent")
        active_objections = any(
            obj.get("status") == "active"
            for obj in customer_profile.get("identified_objections", [])
        )

        # General buying signals that might warrant a presentation if one hasn't just occurred
        general_buying_signals: List[str] = [
            "RequestForNextStepInPurchase",
            "PositiveFeedbackToProposal",
        ]
        # Signals specifically confirming a closing step
        closing_confirmation_signals: List[str] = [
            "ConfirmingCloseAttempt",
            "FinalOrderConfirmation",  # Though this usually means success already
            "ProvidingCorrectionDetails",  # Leads back to awaiting_confirmation
        ]

        if last_intent in general_buying_signals and not active_objections:
            logger.info(
                f"[{node_name}] High-Priority: General buying signal '{last_intent}'."
            )

            just_presented_solution = (
                last_agent_action
                and last_agent_action.get("action_type") == "PRESENT_SOLUTION_OFFER"
                and current_goal_from_state.get("goal_type")
                == "PRESENTING_SOLUTION"  # Check original goal too
            )

            if not just_presented_solution:
                logger.info(
                    f"[{node_name}] General buying signal, but no recent presentation. Transitioning to PRESENTING_SOLUTION."
                )
                effective_goal = AgentGoal(
                    goal_type="PRESENTING_SOLUTION",
                    goal_details={},
                    previous_goal_if_interrupted=None,
                )
                goal_determined_by_high_priority_transition = True
            else:
                logger.info(
                    f"[{node_name}] General buying signal after presentation. Transitioning to ATTEMPTING_CLOSE."
                )
                effective_goal = AgentGoal(
                    goal_type="ATTEMPTING_CLOSE",
                    goal_details={"closing_step": "initial_attempt"},
                    previous_goal_if_interrupted=None,
                )
                goal_determined_by_high_priority_transition = True

        elif last_intent in closing_confirmation_signals and not active_objections:
            # If user is confirming a closing step, we should ensure the goal is ATTEMPTING_CLOSE
            # and let the ATTEMPTING_CLOSE logic handle the specific next action based on closing_process_status.
            logger.info(
                f"[{node_name}] High-Priority: Closing confirmation signal '{last_intent}'. Ensuring goal is ATTEMPTING_CLOSE."
            )
            if effective_goal.get("goal_type") != "ATTEMPTING_CLOSE":
                # If current goal wasn't already ATTEMPTING_CLOSE (e.g. if it was an interruption goal that got resolved by this confirmation)
                effective_goal = AgentGoal(
                    goal_type="ATTEMPTING_CLOSE",
                    goal_details={
                        "closing_step": state.get(
                            "closing_process_status", "initial_attempt"
                        )
                    },  # Use current status or default
                    previous_goal_if_interrupted=None,
                )
            # If goal is already ATTEMPTING_CLOSE, we let its internal logic proceed based on the new intent and status.
            # The key is that this intent should not revert us to PRESENTING_SOLUTION.
            goal_determined_by_high_priority_transition = True

        # 2. Handle Interruptions
        if not goal_determined_by_high_priority_transition:
            interruption_to_handle = _find_priority_interruption(interruptions_queue)
            if interruption_to_handle:
                logger.info(
                    f"[{node_name}] Prioritizing interruption: {interruption_to_handle.get('type')}"
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
            else:
                # 3. Goal Resumption
                should_resume, goal_to_resume = _check_goal_resumption(
                    current_goal_from_state, customer_profile, interruptions_queue
                )
                if should_resume and goal_to_resume:
                    logger.info(
                        f"[{node_name}] Resuming previous goal: {goal_to_resume.get('goal_type')}"
                    )
                    effective_goal = copy.deepcopy(goal_to_resume)  # type: ignore
                    effective_goal["previous_goal_if_interrupted"] = None
                    if effective_goal.get("goal_details") is None:
                        effective_goal["goal_details"] = {}
    # End of `if not is_replan_from_proactive:`

    # Ensure effective_goal is set
    if (
        effective_goal is None
    ):  # This should only happen if replan was indicated but suggested_type was missing
        logger.error(
            f"[{node_name}] Effective goal is None after initial determination. Defaulting to IDLE."
        )
        effective_goal = AgentGoal(
            goal_type="IDLE", goal_details={}, previous_goal_if_interrupted=None
        )

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

    user_response_quality = None
    is_vague_response = False
    if user_analysis and isinstance(user_analysis, dict):
        analysis_detail = user_analysis.get("analysis_of_response_to_agent_action")
        if analysis_detail and isinstance(analysis_detail, dict):
            user_response_quality = analysis_detail.get("user_response_to_agent_action")
        is_vague_response = user_analysis.get("is_primarily_vague_statement", False)

    minimal_or_vague_user_response = (
        user_response_quality
        in ["acknowledged_action", "partially_answered", "ignored_agent_action"]
        or is_vague_response
    )
    # if minimal_or_vague_user_response:
    logger.debug(
        f"AQUIIIIIIIIII MINIMAL RESPONSE:{user_analysis} {user_response_quality} AND {minimal_or_vague_user_response}"
    )
    # --- Action Planning Logic per Goal (Copied from your original file) ---
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
                    effective_goal["previous_goal_if_interrupted"] = None
                    planned_action_command = "GENERATE_FAREWELL"
                    planned_action_parameters = {
                        "reason": f"Impasse sobre a objeção: {original_objection_text[:50]}..."
                    }
            elif obj_entry and obj_entry.get("status") == "addressing":
                logger.info(
                    f"[{node_name}] Objection '{original_objection_text[:30]}' is 'addressing'. Waiting for user response."
                )
                planned_action_command = None
            else:
                logger.info(
                    f"[{node_name}] In HANDLING_OBJECTION goal, but objection '{original_objection_text[:30]}' is not 'active' or 'addressing' (Status: {obj_entry.get('status') if obj_entry else 'Not Found'}). No action planned."
                )
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
            question_status = _find_question_status_in_log(
                customer_question_log, text_to_clarify
            )
            planned_action_parameters["question_to_answer_status"] = question_status
        elif clarification_type == "vague" and text_to_clarify:
            planned_action_command = "ASK_CLARIFYING_QUESTION"
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
        if prev_goal_obj and isinstance(prev_goal_obj, dict):
            prev_goal_type_stored = prev_goal_obj.get("goal_type")
            if prev_goal_type_stored == "INVESTIGATING_NEEDS":
                prev_goal_topic = "suas necessidades"
            elif prev_goal_type_stored == "PRESENTING_SOLUTION":
                prev_goal_topic = "nossa solução"
            elif prev_goal_type_stored == "ATTEMPTING_CLOSE":
                prev_goal_topic = "os próximos passos para o pedido"
        planned_action_parameters["previous_goal_topic"] = prev_goal_topic

    elif effective_goal_type == "INVESTIGATING_NEEDS":

        should_defer_to_proactive_for_this_goal = (
            minimal_or_vague_user_response
            and last_agent_action
            and last_agent_action.get("action_type")
            in ["ASK_SPIN_QUESTION", "ANSWER_DIRECT_QUESTION", "GENERATE_REBUTTAL"]
        )

        if (
            should_defer_to_proactive_for_this_goal and not is_replan_from_proactive
        ):  # Only defer if NOT a replan
            logger.info(
                f"[{node_name}] User gave minimal/vague response after agent action '{last_agent_action.get('action_type')}'. Deferring to proactive step logic for INVESTIGATING_NEEDS."
            )
            planned_action_command = None

        else:
            spin_details = effective_goal.get("goal_details", {})
            spin_questions_asked = spin_details.get(
                "spin_questions_asked_this_cycle", 0
            )
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
                logger.info(
                    f"[{node_name}] Transitioning from SPIN. Reason: {exit_reason}"
                )
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
                effective_goal["goal_details"] = {
                    "presenting_product": product_to_present,
                    "main_benefit_focus": key_benefit,
                }
            else:
                next_spin_type = _get_next_spin_type(last_spin_type_asked)
                planned_action_command = "ASK_SPIN_QUESTION"
                planned_action_parameters["spin_type"] = next_spin_type
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
            planned_action_command = None
        else:
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
        was_resumed_this_cycle = (
            state.get("current_agent_goal", {}).get("goal_type")
            != "ATTEMPTING_CLOSE"  # Check original state goal
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
        elif closing_status in ["not_started", "attempt_made"]:
            if (
                last_agent_action
                and last_agent_action.get("action_type") == "INITIATE_CLOSING"
            ):
                logger.info(
                    f"[{node_name}] Agent just initiated closing (status={closing_status}). Waiting for user response."
                )
                planned_action_command = None
            else:
                if closing_status == "attempt_made":
                    logger.info(
                        f"[{node_name}] Closing status is 'attempt_made', but no clear positive intent or not resuming. Waiting."
                    )
                    planned_action_command = None
                else:  # Status is 'not_started'
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
        else:
            logger.warning(
                f"[{node_name}] Unhandled closing_status '{closing_status}' in ATTEMPTING_CLOSE goal. Waiting."
            )
            planned_action_command = None

    elif effective_goal_type == "ENDING_CONVERSATION":
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
        if (
            last_agent_action
            and last_agent_action.get("action_type") == "GENERATE_GREETING"
        ):
            logger.info(
                f"[{node_name}] Greeting sent. Transitioning to INVESTIGATING_NEEDS."
            )
            effective_goal["goal_type"] = "INVESTIGATING_NEEDS"
            planned_action_command = "ASK_SPIN_QUESTION"
            planned_action_parameters["spin_type"] = "Situation"
            effective_goal["goal_details"] = {
                "spin_questions_asked_this_cycle": 0,
                "last_spin_type_asked": None,
            }
        elif not last_agent_action or (
            last_agent_action
            and last_agent_action.get("action_type") == "GENERATE_FAREWELL"
        ):
            logger.info(
                f"[{node_name}] Goal is IDLE or GREETING (initial). Planning GREETING."
            )
            planned_action_command = "GENERATE_GREETING"
            effective_goal["goal_type"] = "GREETING"
            effective_goal["goal_details"] = {}
        else:
            logger.info(
                f"[{node_name}] Goal is {effective_goal_type}, already acted. Waiting or re-evaluating."
            )
            planned_action_command = None
    # --- End of Action Planning Logic per Goal ---

    # --- MODIFICATION 4: Adjust proactive trigger conditions ---
    if planned_action_command is None and trigger_event != "follow_up_timeout":
        agent_is_explicitly_waiting = False
        if (
            effective_goal_type == "PRESENTING_SOLUTION"
            and last_agent_action
            and last_agent_action.get("action_type") == "PRESENT_SOLUTION_OFFER"
            and not minimal_or_vague_user_response
        ):
            agent_is_explicitly_waiting = True
        elif (
            effective_goal_type == "ATTEMPTING_CLOSE"
            and state.get("closing_process_status") == "attempt_made"
            and last_agent_action
            and last_agent_action.get("action_type") == "INITIATE_CLOSING"
        ):
            agent_is_explicitly_waiting = True
        elif effective_goal_type == "HANDLING_OBJECTION":
            original_objection_text = effective_goal.get("goal_details", {}).get(
                "original_objection_text"
            )
            if original_objection_text:
                obj_entry = _find_objection_in_profile(
                    customer_profile, original_objection_text
                )
                if obj_entry and obj_entry.get("status") == "addressing":
                    agent_is_explicitly_waiting = True

        if not agent_is_explicitly_waiting:
            if effective_goal_type != "ENDING_CONVERSATION" and not (
                last_agent_action
                and last_agent_action.get("action_type") == "GENERATE_FAREWELL"
            ):
                logger.info(
                    f"[{node_name}] No standard action from goal '{effective_goal_type}'. Planning DECIDE_PROACTIVE_STEP."
                )
                planned_action_command = "DECIDE_PROACTIVE_STEP"
                planned_action_parameters = {
                    "trigger_source": "user_response_or_stagnation",
                    "current_follow_up_attempts": state.get(
                        "follow_up_attempt_count", 0
                    ),
                    "max_follow_up_attempts_total": state.get("agent_config", {}).get(
                        "max_follow_up_attempts", 3
                    ),
                }
        else:
            logger.debug(
                f"[{node_name}] Agent is explicitly waiting or proactive step handled by timeout. No proactive action."
            )

    # --- Update Interrupt Queue ---
    updated_interruptions_queue = list(interruptions_queue)
    # MODIFICATION 5: Conditional interruption queue update
    goal_determined_by_interruption_this_cycle = False
    if (
        not is_replan_from_proactive and interruption_to_handle
    ):  # interruption_to_handle is from this cycle's standard logic
        # Check if the effective_goal set by standard logic matches the goal for the interruption found
        if (
            effective_goal.get("goal_type")
            == _get_goal_for_interruption(interruption_to_handle)[0]
        ):
            goal_determined_by_interruption_this_cycle = True

    if (
        goal_determined_by_interruption_this_cycle
        and planned_action_command
        and interruption_to_handle
    ):
        try:
            idx_to_remove = -1
            for i, item in enumerate(updated_interruptions_queue):
                if item == interruption_to_handle:
                    idx_to_remove = i
                    break
            if idx_to_remove != -1:
                updated_interruptions_queue.pop(idx_to_remove)
                logger.debug(
                    f"[{node_name}] Removed handled interruption from queue: {interruption_to_handle.get('type')}"
                )
        except Exception as e:
            logger.warning(f"[{node_name}] Error removing interruption from queue: {e}")

    # --- Prepare Delta ---
    # `updated_state_delta` was initialized at the start to clear proactive fields.
    updated_state_delta["current_agent_goal"] = effective_goal
    if updated_interruptions_queue != interruptions_queue:
        updated_state_delta["user_interruptions_queue"] = updated_interruptions_queue

    if planned_action_command:
        updated_state_delta["next_agent_action_command"] = planned_action_command
        updated_state_delta["action_parameters"] = planned_action_parameters
        logger.info(
            f"[{node_name}] Planned Action: {planned_action_command}, Params: {planned_action_parameters}"
        )
    else:
        updated_state_delta["next_agent_action_command"] = None
        updated_state_delta["action_parameters"] = {}
        logger.info(
            f"[{node_name}] No specific action planned by planner for this turn."
        )

    logger.info(
        f"[{node_name}] Planner finished. Final Planned Goal: {effective_goal.get('goal_type')}"
    )
    return updated_state_delta
