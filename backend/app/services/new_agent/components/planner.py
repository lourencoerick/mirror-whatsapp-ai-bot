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
)

INTERRUPTION_TO_ACTION_MAP: Dict[str, AgentActionType] = {
    "direct_question": "ANSWER_DIRECT_QUESTION",
    "objection": "GENERATE_REBUTTAL",
    "vague_statement": "ASK_CLARIFYING_QUESTION",
    "off_topic_comment": "ACKNOWLEDGE_AND_TRANSITION",
}
MAX_SPIN_QUESTIONS_PER_CYCLE = 5
MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION = 2


# --- Helper Functions --- (Keep as they were)
# ... (_find_priority_interruption, _get_goal_for_interruption, etc.) ...
def _find_priority_interruption(
    queue: List[UserInterruption],
) -> Optional[UserInterruption]:
    """Finds the highest priority interruption."""
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
    """Determines the temporary goal type and details for an interruption."""
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

    return goal_type, goal_details


def _get_previous_goal_to_store(
    current_goal: AgentGoal, goal_type_for_interruption: AgentGoalType
) -> Optional[AgentGoal]:
    """Determines which goal to store as the 'previous' one."""
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
    current_goal: AgentGoal, customer_profile: DynamicCustomerProfile
) -> Tuple[bool, Optional[AgentGoal]]:
    """Checks if the agent should resume a previously interrupted goal."""
    previous_goal_to_resume = current_goal.get("previous_goal_if_interrupted")
    if not previous_goal_to_resume:
        return False, None

    current_goal_type = current_goal.get("goal_type")

    if current_goal_type in ["CLARIFYING_USER_INPUT", "ACKNOWLEDGE_AND_TRANSITION"]:
        logger.info(
            f"Temporary goal {current_goal_type} completed. Attempting to resume."
        )
        return True, previous_goal_to_resume

    elif current_goal_type == "HANDLING_OBJECTION":
        original_objection_text = current_goal.get("goal_details", {}).get(
            "original_objection_text"
        )
        if original_objection_text:
            for obj in customer_profile.get("identified_objections", []):
                if (
                    obj.get("text") == original_objection_text
                    and obj.get("status") == "resolved"
                ):
                    logger.info(
                        f"Objection '{original_objection_text}' resolved. Attempting to resume."
                    )
                    return True, previous_goal_to_resume
        logger.debug(
            f"HANDLING_OBJECTION resumption check failed: Objection '{original_objection_text}' not resolved."
        )
        return False, None

    return False, None


def _find_objection_in_profile(
    customer_profile: DynamicCustomerProfile, objection_text: str
) -> Optional[IdentifiedObjectionEntry]:
    """Finds a specific objection entry in the profile by text."""
    for obj_entry in customer_profile.get("identified_objections", []):
        if obj_entry.get("text") == objection_text:
            return obj_entry
    return None


def _get_next_spin_type(last_spin_type: Optional[SpinQuestionType]) -> SpinQuestionType:
    """Determines the next SPIN question type in the sequence."""
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
    """Selects a product and key benefit based on identified needs."""
    product_to_present = "Nossa Solução Principal"
    key_benefit = "atender às suas necessidades gerais"
    identified_needs: List[IdentifiedNeedEntry] = customer_profile.get(
        "identified_needs", []
    )
    target_need: Optional[IdentifiedNeedEntry] = None
    confirmed_needs = [
        n for n in identified_needs if n.get("status") == "confirmed_by_user"
    ]
    active_needs = [n for n in identified_needs if n.get("status") == "active"]

    if confirmed_needs:
        confirmed_needs.sort(
            key=lambda x: (x.get("priority", 0), x.get("source_turn", 0)), reverse=True
        )
        target_need = confirmed_needs[0]
    elif active_needs:
        active_needs.sort(
            key=lambda x: (x.get("priority", 0), x.get("source_turn", 0)), reverse=True
        )
        target_need = active_needs[0]

    if target_need:
        target_need_text = target_need.get("text", "sua necessidade principal")
        key_benefit = f"o seu desafio em relação a '{target_need_text}'"
        if company_profile_offerings:
            best_match_score = 0
            best_match_product = company_profile_offerings[0].get(
                "name", product_to_present
            )
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
            product_to_present = best_match_product
            if best_match_score > 0:
                logger.debug(
                    f"Planner: Matched need '{target_need_text}' to product '{product_to_present}' based on keywords (Score: {best_match_score})."
                )
            else:
                logger.debug(
                    f"Planner: No specific product keyword match for need '{target_need_text}', defaulting to '{product_to_present}'."
                )
        else:
            logger.warning("Planner: No company offerings found to match needs.")
    return product_to_present, key_benefit


# --- Main Planner Node ---
async def goal_and_action_planner_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    # ... (initial setup and logging) ...
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
    interruptions_queue = state.get("user_interruptions_queue", [])
    customer_profile = cast(
        DynamicCustomerProfile, copy.deepcopy(state.get("customer_profile_dynamic", {}))
    )
    last_agent_action = copy.deepcopy(state.get("last_agent_action"))
    company_profile = state.get("company_profile", {})

    # --- 1. Determine Effective Goal for this Turn ---
    effective_goal: AgentGoal = current_goal_from_state
    goal_determined_by_high_priority_transition = False  # <<< Renamed flag
    goal_determined_by_interruption = False
    resumed_goal_this_turn = False

    # --- Check for High-Priority Goal Transitions FIRST ---
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
            goal_determined_by_high_priority_transition = True  # <<< Set specific flag

    # --- If no high-priority transition, check for Interruptions ---
    interruption_to_handle = None  # Define outside the block
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
            goal_determined_by_interruption = True  # <<< Set specific flag
        else:
            # --- If no interruption, check for Goal Resumption ---
            should_resume, goal_to_resume = _check_goal_resumption(
                current_goal_from_state, customer_profile
            )
            if should_resume and goal_to_resume:
                logger.info(
                    f"[{node_name}] Resuming previous goal: {goal_to_resume.get('goal_type')}"
                )
                effective_goal = copy.deepcopy(goal_to_resume)
                effective_goal["previous_goal_if_interrupted"] = None
                resumed_goal_this_turn = True
                if effective_goal.get("goal_type") == "INVESTIGATING_NEEDS":
                    effective_goal["goal_details"] = {
                        "spin_questions_asked_this_cycle": 0,
                        "last_spin_type_asked": None,
                    }
                elif effective_goal.get("goal_details") is None:
                    effective_goal["goal_details"] = {}

    # Ensure details dict exists if not set above
    if effective_goal.get("goal_details") is None:
        effective_goal["goal_details"] = {}

    logger.info(
        f"[{node_name}] Effective goal for planning: {effective_goal.get('goal_type')}"
    )
    if effective_goal.get("goal_details"):
        logger.debug(
            f"[{node_name}] Effective goal details: {effective_goal.get('goal_details')}"
        )

    # --- 2. Plan Action Based on Effective Goal and State ---
    planned_action_command: Optional[AgentActionType] = None
    planned_action_parameters: AgentActionDetails = {}
    effective_goal_type = effective_goal.get("goal_type", "IDLE")

    # --- FIX: Skip action planning ONLY if goal was just RESUMED ---
    if not resumed_goal_this_turn:
        # --- Action Planning Logic per Goal (Place the entire if/elif block here) ---
        if effective_goal_type == "HANDLING_OBJECTION":
            # ... (logic as before)
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
                            f"[{node_name}] Objection '{original_objection_text[:30]}' persists (attempt {attempts+1} needed). Planning rebuttal."
                        )
                        planned_action_command = "GENERATE_REBUTTAL"
                        planned_action_parameters["objection_text_to_address"] = (
                            original_objection_text
                        )
                    else:
                        logger.warning(
                            f"[{node_name}] Max rebuttal attempts ({attempts}) reached for objection '{original_objection_text[:30]}'. Handling impasse."
                        )
                        effective_goal["goal_type"] = (
                            "ENDING_CONVERSATION"  # Update goal
                        )
                        effective_goal["goal_details"] = {
                            "reason": f"Impasse on objection: {original_objection_text}"
                        }
                        effective_goal["previous_goal_if_interrupted"] = None
                        planned_action_command = "ACKNOWLEDGE_AND_TRANSITION"
                        planned_action_parameters = {
                            "off_topic_text": f"Entendo que a objeção sobre '{original_objection_text[:30]}...' continua sendo um ponto crítico.",
                            "previous_goal_topic": "nossos próximos passos ou outras opções",
                        }
                elif obj_entry and obj_entry.get("status") == "addressing":
                    logger.info(
                        f"[{node_name}] Objection '{original_objection_text[:30]}' is being addressed (status='addressing'). Waiting for user response."
                    )
                    planned_action_command = None
                else:  # Fallback if objection state is unexpected
                    logger.warning(
                        f"[{node_name}] In HANDLING_OBJECTION goal, but objection '{original_objection_text[:30]}' is not 'active' or 'addressing'. Status: {obj_entry.get('status') if obj_entry else 'Not Found'}. Waiting."
                    )
                    planned_action_command = None  # Default to wait
            else:
                logger.warning(
                    f"[{node_name}] In HANDLING_OBJECTION goal, but no original_objection_text found in details. Waiting."
                )
                planned_action_command = None

        elif effective_goal_type == "CLARIFYING_USER_INPUT":
            # ... (logic as before)
            clarification_type = effective_goal.get("goal_details", {}).get(
                "clarification_type"
            )
            if clarification_type == "question":
                planned_action_command = "ANSWER_DIRECT_QUESTION"
                planned_action_parameters["question_to_answer_text"] = (
                    effective_goal.get("goal_details", {}).get("text")
                )
            elif clarification_type == "vague":
                planned_action_command = "ASK_CLARIFYING_QUESTION"
            else:
                logger.warning(
                    f"Unknown clarification type: {clarification_type}. Planning ASK_CLARIFYING_QUESTION."
                )
                planned_action_command = "ASK_CLARIFYING_QUESTION"

        elif effective_goal_type == "ACKNOWLEDGE_AND_TRANSITION":
            # ... (logic as before)
            planned_action_command = "ACKNOWLEDGE_AND_TRANSITION"
            planned_action_parameters["off_topic_text"] = effective_goal.get(
                "goal_details", {}
            ).get("text", "[comentário anterior]")
            prev_goal_topic = "o assunto anterior"
            prev_goal = effective_goal.get("previous_goal_if_interrupted")
            if prev_goal:
                if prev_goal.get("goal_type") == "INVESTIGATING_NEEDS":
                    prev_goal_topic = "suas necessidades"
                elif prev_goal.get("goal_type") == "PRESENTING_SOLUTION":
                    prev_goal_topic = "nossa solução"
            planned_action_parameters["previous_goal_topic"] = prev_goal_topic

        elif effective_goal_type == "INVESTIGATING_NEEDS":
            # ... (logic as before)
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
                effective_goal["goal_type"] = "PRESENTING_SOLUTION"  # Update goal
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
            # ... (logic as before - note: buying signal check already happened)
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
                    f"[{node_name}] In PRESENTING_SOLUTION state, but not just presented and no buying signal. Waiting."
                )
                planned_action_command = None

        elif effective_goal_type == "ATTEMPTING_CLOSE":
            closing_status = state.get("closing_process_status", "not_started")
            active_proposal = state.get("active_proposal")  # Get proposal details

            # --- ADDED: Logic based on closing_status ---
            if closing_status == "awaiting_confirmation":
                logger.info(
                    f"[{node_name}] User confirmed initial close. Planning to confirm details."
                )
                planned_action_command = "CONFIRM_ORDER_DETAILS"
                # Pass proposal details for the confirmation message
                if active_proposal:
                    planned_action_parameters["product_name"] = active_proposal.get(
                        "product_name"
                    )
                    planned_action_parameters["price"] = active_proposal.get("price")
                    planned_action_parameters["price_info"] = active_proposal.get(
                        "price_info"
                    )

            elif closing_status == "confirmed_success":
                logger.info(
                    f"[{node_name}] Order details confirmed by user. Planning final processing step."
                )
                planned_action_command = "PROCESS_ORDER_CONFIRMATION"
                # Pass details needed for the final confirmation message/action
                if active_proposal:
                    planned_action_parameters["product_name"] = active_proposal.get(
                        "product_name"
                    )

            # --- END ADDED ---
            elif (
                closing_status == "not_started"
                or not last_agent_action
                or last_agent_action.get("action_type")
                not in [
                    "INITIATE_CLOSING",
                    "CONFIRM_ORDER_DETAILS",
                    "HANDLE_CLOSING_CORRECTION",
                ]
            ):
                logger.info(
                    f"[{node_name}] Initiating closing process (goal already set or restarting)."
                )
                planned_action_command = "INITIATE_CLOSING"
                effective_goal["goal_details"] = {"closing_step": "initial_attempt"}
                if active_proposal:
                    planned_action_parameters["product_name"] = active_proposal.get(
                        "product_name"
                    )
                    planned_action_parameters["price"] = active_proposal.get("price")
            # --- ADDED: Handle other statuses (optional for now) ---
            elif closing_status == "needs_correction":
                logger.info(
                    f"[{node_name}] Closing needs correction. Planning action to handle correction."
                )
                planned_action_command = "HANDLE_CLOSING_CORRECTION"
                # Pass context if needed, e.g., what was being confirmed
                if (
                    last_agent_action
                    and last_agent_action.get("action_type") == "CONFIRM_ORDER_DETAILS"
                ):
                    planned_action_parameters["context"] = (
                        "Estávamos confirmando os detalhes do pedido."
                    )
                else:
                    planned_action_parameters["context"] = (
                        "Estávamos finalizando seu pedido."
                    )
            # Potentially ask what needs correction based on user input analysis
            elif closing_status == "confirmation_rejected":
                logger.info(
                    f"[{node_name}] Closing attempt rejected by user. Transitioning."
                )
                # Transition back or end conversation? For now, let's end.
                effective_goal["goal_type"] = "ENDING_CONVERSATION"
                effective_goal["goal_details"] = {"reason": "Closing attempt rejected"}
                effective_goal["previous_goal_if_interrupted"] = None
                planned_action_command = (
                    "GENERATE_FAREWELL"  # Or ACKNOWLEDGE_AND_TRANSITION
                )
                planned_action_parameters["reason"] = "Closing attempt rejected"

            # --- END ADDED ---
            else:  # Includes attempt_made, confirmed_success, confirmed_failed_to_process
                logger.info(
                    f"[{node_name}] In ATTEMPTING_CLOSE, status is '{closing_status}'. Waiting for user response or external process."
                )
                planned_action_command = None

        elif effective_goal_type == "ENDING_CONVERSATION":
            # ... (logic as before)
            if (
                not planned_action_command
            ):  # If impasse logic didn't already set an action
                logger.info(
                    f"[{node_name}] In ENDING_CONVERSATION goal. Planning farewell."
                )
                planned_action_command = "GENERATE_FAREWELL"
                planned_action_parameters = {
                    "reason": effective_goal.get("goal_details", {}).get(
                        "reason", "concluding"
                    )
                }

        elif effective_goal_type == "IDLE" or effective_goal_type == "GREETING":
            # ... (logic as before)
            logger.info(
                f"[{node_name}] Goal is {effective_goal_type}. Transitioning to INVESTIGATING_NEEDS."
            )
            effective_goal["goal_type"] = "INVESTIGATING_NEEDS"  # Update goal
            planned_action_command = "ASK_SPIN_QUESTION"
            planned_action_parameters["spin_type"] = "Situation"
            effective_goal["goal_details"] = {
                "spin_questions_asked_this_cycle": 0,
                "last_spin_type_asked": None,
            }

    else:  # Goal was just resumed
        logger.info(
            f"[{node_name}] Goal {effective_goal_type} was just resumed. No action planned for this cycle."
        )
        planned_action_command = None

    # --- 3. Update Interrupt Queue ---
    # Remove interruption only if it was handled by setting a temporary goal AND an action was planned for it
    updated_interruptions_queue = list(state.get("user_interruptions_queue", []))
    if (
        goal_determined_by_interruption
        and planned_action_command
        and interruption_to_handle
    ):  # Check the specific flag
        try:
            idx_to_remove = -1
            for i, item in enumerate(updated_interruptions_queue):
                if (
                    item.get("type") == interruption_to_handle.get("type")
                    and item.get("text") == interruption_to_handle.get("text")
                    and item.get("status") == "pending_resolution"
                ):
                    idx_to_remove = i
                    break
            if idx_to_remove != -1:
                updated_interruptions_queue.pop(idx_to_remove)
                logger.debug(
                    f"[{node_name}] Removed handled interruption from queue: {interruption_to_handle.get('type')}"
                )
            else:
                logger.warning(
                    f"[{node_name}] Could not find interruption to remove from queue: {interruption_to_handle}"
                )
        except Exception as e:
            logger.warning(f"[{node_name}] Error removing interruption from queue: {e}")

    # --- 4. Prepare Delta ---
    updated_state_delta: Dict[str, Any] = {}
    # Always include the effective_goal
    updated_state_delta["current_agent_goal"] = effective_goal
    # Update queue only if it changed
    if updated_interruptions_queue != state.get("user_interruptions_queue", []):
        updated_state_delta["user_interruptions_queue"] = updated_interruptions_queue
    # Add planned action if one was decided
    if planned_action_command:
        updated_state_delta["next_agent_action_command"] = planned_action_command
        updated_state_delta["action_parameters"] = planned_action_parameters
        logger.info(
            f"[{node_name}] Planned Action: {planned_action_command}, Params: {planned_action_parameters}"
        )
    else:
        updated_state_delta["next_agent_action_command"] = None
        updated_state_delta["action_parameters"] = {}
        logger.info(f"[{node_name}] No specific action planned for this turn.")
    # Clear previous errors
    updated_state_delta["last_processing_error"] = None
    logger.info(
        f"[{node_name}] Planner finished. Final Planned Goal: {effective_goal.get('goal_type')}"
    )
    return updated_state_delta
