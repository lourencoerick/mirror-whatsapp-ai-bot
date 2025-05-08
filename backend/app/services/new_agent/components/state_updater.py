# backend/app/services/ai_reply/new_agent/components/state_updater.py

import time
from typing import Dict, List, Optional, Any, cast
from loguru import logger
import copy

from ..state_definition import (
    RichConversationState,
    CustomerQuestionEntry,
    UserInterruption,
    IdentifiedObjectionEntry,
    IdentifiedNeedEntry,
    IdentifiedPainPointEntry,
    DynamicCustomerProfile,
    CustomerQuestionStatusType,
    ObjectionStatusType,
    UserInterruptionType,
)
from ..schemas.input_analysis import (
    UserInputAnalysisOutput,
    ExtractedQuestionAnalysis,
    ReactionToPresentation,
    ObjectionAfterRebuttalStatus,
)


async def _log_missing_information_event(
    account_id: str, conversation_id: str, question_core: str
):
    """
    Logs an event indicating the agent lacked information to answer a question.

    This is a placeholder for integrating with an analytics or monitoring system.
    It's triggered when a user repeats a question that was previously answered
    with a fallback due to missing knowledge.

    Args:
        account_id: The account ID associated with the conversation.
        conversation_id: The ID of the conversation.
        question_core: The core text of the question the agent couldn't answer.
    """
    logger.warning(
        f"[Analytics Event - TODO] MISSING_INFORMATION: Account={account_id}, Conv={conversation_id}, Question='{question_core}'"
    )
    # In a real implementation, this would send data to an analytics service.
    pass


async def update_conversation_state_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Updates the conversation state based on the analysis of the user's input.

    This node integrates the structured analysis from the InputProcessor into
    the RichConversationState. It updates the question log, dynamic customer
    profile (needs, pains, objections, intent), closing process status,
    and rebuilds the user interruption queue based on the latest state.

    Args:
        state: The current conversation state dictionary.
        config: The graph configuration dictionary (not typically used directly here).

    Returns:
        A dictionary containing the state updates (delta) to be merged into the
        main conversation state. Includes increments to turn number, updates to
        logs, profiles, queues, and clears temporary analysis fields. Returns
        an error message if input analysis validation fails.
    """
    node_name = "update_conversation_state_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    updated_state_delta: Dict[str, Any] = {}
    current_turn = state.get("current_turn_number", 0)
    next_turn_number = current_turn + 1
    updated_state_delta["current_turn_number"] = next_turn_number

    user_input_analysis_dict = state.get("user_input_analysis_result")
    if not user_input_analysis_dict:
        logger.warning(
            f"[{node_name}] No user_input_analysis_result found in state. Skipping detailed state update."
        )
        return {"last_processing_error": None, "current_turn_number": next_turn_number}
    try:
        # Validate the structure of the analysis results
        analysis = UserInputAnalysisOutput.model_validate(user_input_analysis_dict)
    except Exception as e:
        logger.exception(
            f"[{node_name}] Failed to validate user_input_analysis_result: {e}"
        )
        # Return error and do not proceed with state update
        return {
            "last_processing_error": f"State update failed: Invalid input analysis. Details: {e}"
        }

    # --- Prepare working copies of mutable state parts ---
    current_question_log = [
        entry.copy() for entry in state.get("customer_question_log", [])
    ]
    new_interruptions_this_turn: List[UserInterruption] = []
    # Deepcopy profile data as it will be modified extensively
    current_dynamic_profile_dict = copy.deepcopy(
        state.get("customer_profile_dynamic", {})
    )
    # Ensure structure conforms to TypedDict for internal use and type checking
    # Cast helps type checkers understand the structure after retrieval/copying
    dynamic_profile_data: DynamicCustomerProfile = cast(
        DynamicCustomerProfile,
        {
            "identified_needs": [
                IdentifiedNeedEntry(**n)
                for n in current_dynamic_profile_dict.get("identified_needs", [])
            ],
            "identified_pain_points": [
                IdentifiedPainPointEntry(**p)
                for p in current_dynamic_profile_dict.get("identified_pain_points", [])
            ],
            "identified_objections": [
                IdentifiedObjectionEntry(**o)
                for o in current_dynamic_profile_dict.get("identified_objections", [])
            ],
            "certainty_levels": current_dynamic_profile_dict.get(
                "certainty_levels",
                {
                    "product": None,
                    "agent": None,
                    "company": None,
                    "last_assessed_turn": None,
                },
            ),
            "last_discerned_intent": current_dynamic_profile_dict.get(
                "last_discerned_intent", None
            ),
        },
    )

    profile_changed = False  # Flag to track if dynamic_profile needs updating in delta
    log_changed = False  # Flag to track if customer_question_log needs updating
    processed_interrupt_texts = set()  # Avoid duplicate interruptions in this turn

    # --- 0. Update Last Discerned Intent ---
    if analysis.overall_intent:
        if dynamic_profile_data.get("last_discerned_intent") != analysis.overall_intent:
            dynamic_profile_data["last_discerned_intent"] = analysis.overall_intent
            profile_changed = True
            logger.debug(
                f"[{node_name}] Updated last_discerned_intent to: {analysis.overall_intent}"
            )

    # --- 1. Process Extracted Questions ---
    newly_added_to_log_count = 0
    updated_log_entry_count = 0
    questions_to_interrupt: List[ExtractedQuestionAnalysis] = []

    for q_analysis in analysis.extracted_questions:
        log_entry_to_update = None
        if q_analysis.is_repetition and q_analysis.original_question_turn is not None:
            # Search backwards for the most recent matching original question
            for i in range(len(current_question_log) - 1, -1, -1):
                log_entry = current_question_log[i]
                if (
                    log_entry.get("turn_asked") == q_analysis.original_question_turn
                    and log_entry.get("extracted_question_core")
                    == q_analysis.original_question_core_text
                ):
                    log_entry_to_update = log_entry
                    break

        if log_entry_to_update:
            # Update status of the existing log entry based on repetition analysis
            new_status: CustomerQuestionStatusType = log_entry_to_update.get("status")  # type: ignore
            should_add_to_interrupt = False
            if q_analysis.status_of_original_answer == "answered_satisfactorily":
                new_status = "repetition_after_satisfactory_answer"
                should_add_to_interrupt = (
                    True  # Add to queue for planner to potentially address again
                )
            elif q_analysis.status_of_original_answer == "answered_with_fallback":
                new_status = "repetition_after_fallback"
                # Log event for missing info
                await _log_missing_information_event(
                    state.get("account_id", "unknown"),  # type: ignore
                    state.get("conversation_id", "unknown"),  # type: ignore
                    q_analysis.question_text,
                )
                should_add_to_interrupt = True  # Definitely interrupt
            else:  # Includes "unknown_previous_status"
                new_status = "repetition_after_fallback"  # Treat as needing attention
                should_add_to_interrupt = True

            if log_entry_to_update.get("status") != new_status:
                log_entry_to_update["status"] = new_status
                updated_log_entry_count += 1
                log_changed = True

            if should_add_to_interrupt:
                questions_to_interrupt.append(q_analysis)
        else:
            # Add new question to the log
            current_question_log.append(
                CustomerQuestionEntry(
                    original_question_text=q_analysis.question_text,
                    extracted_question_core=q_analysis.question_text,
                    turn_asked=next_turn_number,
                    status="newly_asked",
                    agent_direct_response_summary=None,
                    repetition_of_turn=None,
                    similarity_vector=None,
                )
            )
            newly_added_to_log_count += 1
            log_changed = True
            questions_to_interrupt.append(q_analysis)  # New questions always interrupt

    if log_changed:
        updated_state_delta["customer_question_log"] = current_question_log
        logger.debug(
            f"[{node_name}] Question log updated: {newly_added_to_log_count} added, {updated_log_entry_count} updated."
        )

    # --- 2. Process Extracted Needs and Pains ---
    needs_added = 0
    pains_added = 0
    for np in analysis.extracted_needs_or_pains:
        target_list_key = (
            "identified_needs" if np.type == "need" else "identified_pain_points"
        )
        target_list_in_profile = dynamic_profile_data.setdefault(target_list_key, [])
        is_duplicate = any(
            existing_np.get("text") == np.text for existing_np in target_list_in_profile
        )
        if not is_duplicate:
            entry_data: Any
            if np.type == "need":
                entry_data = IdentifiedNeedEntry(
                    text=np.text,
                    status="active",
                    priority=None,
                    source_turn=next_turn_number,
                )
                needs_added += 1
            else:
                entry_data = IdentifiedPainPointEntry(
                    text=np.text, status="active", source_turn=next_turn_number
                )
                pains_added += 1
            target_list_in_profile.append(entry_data)  # type: ignore
            profile_changed = True
    if needs_added > 0 or pains_added > 0:
        logger.debug(
            f"[{node_name}] Profile updated: {needs_added} needs, {pains_added} pains added."
        )

    # --- 3. REFINED OBJECTION HANDLING ---
    objections_list = dynamic_profile_data.setdefault("identified_objections", [])
    handled_original_objection_text: Optional[str] = None
    was_persistence_detected = False
    newly_raised_objection_text_after_rebuttal: Optional[str] = None
    objections_added_this_turn_texts = set()

    # 3a. Process Status of Objection After Rebuttal FIRST
    if (
        analysis.objection_status_after_rebuttal
        and analysis.objection_status_after_rebuttal.status != "not_applicable"
        and analysis.objection_status_after_rebuttal.original_objection_text_handled
    ):
        original_obj_text_handled = (
            analysis.objection_status_after_rebuttal.original_objection_text_handled
        )
        new_status_from_analysis = analysis.objection_status_after_rebuttal.status
        new_obj_text_if_raised = (
            analysis.objection_status_after_rebuttal.new_objection_text
        )
        handled_original_objection_text = (
            original_obj_text_handled  # Track which one was handled
        )

        original_obj_index = -1
        for i, obj_entry in enumerate(objections_list):
            if obj_entry.get("text") == original_obj_text_handled:
                original_obj_index = i
                break

        if original_obj_index != -1:
            logger.debug(
                f"[{node_name}] P3a: Found original objection '{original_obj_text_handled}' to update based on status '{new_status_from_analysis}'."
            )
            original_obj_status_before_update = objections_list[original_obj_index].get(
                "status"
            )
            new_objection_status: ObjectionStatusType = original_obj_status_before_update  # type: ignore

            if new_status_from_analysis == "appears_resolved":
                new_objection_status = "resolved"
            elif new_status_from_analysis == "still_persists":
                new_objection_status = "active"
                was_persistence_detected = True
            elif new_status_from_analysis == "new_objection_raised":
                new_objection_status = "ignored"
                if new_obj_text_if_raised:
                    newly_raised_objection_text_after_rebuttal = new_obj_text_if_raised
            elif new_status_from_analysis in [
                "unclear_still_evaluating",
                "changed_topic",
            ]:
                new_objection_status = "active"

            if (
                objections_list[original_obj_index].get("status")
                != new_objection_status
            ):
                objections_list[original_obj_index]["status"] = new_objection_status
                profile_changed = True
                logger.debug(
                    f"[{node_name}] P3a: Updated status of '{original_obj_text_handled}' from '{original_obj_status_before_update}' to '{new_objection_status}'."
                )
        else:
            logger.warning(
                f"[{node_name}] P3a: Could not find original objection '{original_obj_text_handled}' in profile."
            )
            if (
                new_status_from_analysis == "new_objection_raised"
                and new_obj_text_if_raised
            ):
                newly_raised_objection_text_after_rebuttal = new_obj_text_if_raised

    # 3b. Process Extracted Objections (from current input)
    objections_added_from_extraction = 0
    for obj_from_analysis in analysis.extracted_objections:
        obj_text = obj_from_analysis.objection_text
        # Skip if handled as 'newly_raised' or if persistence was detected for original
        if (
            newly_raised_objection_text_after_rebuttal
            and obj_text == newly_raised_objection_text_after_rebuttal
        ) or (
            was_persistence_detected and obj_text != handled_original_objection_text
        ):  # Skip rephrased persistent objections
            logger.debug(
                f"[{node_name}] P3b: Skipping extracted objection '{obj_text}' due to prior handling."
            )
            continue

        is_duplicate = any(
            ex_obj.get("text") == obj_text
            and ex_obj.get("status") in ["active", "addressing"]
            for ex_obj in objections_list
        )
        if not is_duplicate:
            objections_list.append(
                IdentifiedObjectionEntry(
                    text=obj_text,
                    status="active",
                    rebuttal_attempts=0,
                    source_turn=next_turn_number,
                    related_to_proposal=None,
                )
            )
            objections_added_from_extraction += 1
            objections_added_this_turn_texts.add(obj_text)
            profile_changed = True

    # 3c. Add the newly raised objection from rebuttal analysis if needed
    if (
        newly_raised_objection_text_after_rebuttal
        and newly_raised_objection_text_after_rebuttal
        not in objections_added_this_turn_texts
    ):
        is_new_duplicate = any(
            eo.get("text") == newly_raised_objection_text_after_rebuttal
            and eo.get("status") in ["active", "addressing"]
            for eo in objections_list
        )
        if not is_new_duplicate:
            objections_list.append(
                IdentifiedObjectionEntry(
                    text=newly_raised_objection_text_after_rebuttal,
                    status="active",
                    rebuttal_attempts=0,
                    source_turn=next_turn_number,
                    related_to_proposal=None,
                )
            )
            profile_changed = True
            objections_added_this_turn_texts.add(
                newly_raised_objection_text_after_rebuttal
            )
            logger.debug(
                f"[{node_name}] P3c: Added new objection '{newly_raised_objection_text_after_rebuttal}' from rebuttal analysis."
            )

    if objections_added_from_extraction > 0:
        logger.debug(
            f"[{node_name}] Profile updated: {objections_added_from_extraction} new objections added from direct extraction."
        )

    # --- 4. Process Reaction to Solution Presentation ---
    if (
        analysis.reaction_to_solution_presentation
        and analysis.reaction_to_solution_presentation.reaction_type != "not_applicable"
    ):
        reaction = analysis.reaction_to_solution_presentation
        logger.info(
            f"[{node_name}] Processing reaction to solution presentation: {reaction.reaction_type}"
        )
        if reaction.reaction_type == "new_objection_to_solution" and reaction.details:
            obj_text_from_reaction = reaction.details
            found_existing = False
            for i, obj_entry in enumerate(objections_list):
                if obj_entry.get("text") == obj_text_from_reaction:
                    if obj_entry.get("related_to_proposal") is not True:
                        objections_list[i]["related_to_proposal"] = True
                        profile_changed = True
                        logger.debug(
                            f"[{node_name}] Marked existing objection '{obj_text_from_reaction[:50]}' as related to proposal."
                        )
                    found_existing = True
                    break
            if (
                not found_existing
                and obj_text_from_reaction not in objections_added_this_turn_texts
            ):
                is_duplicate = any(
                    ex_obj.get("text") == obj_text_from_reaction
                    and ex_obj.get("status") in ["active", "addressing"]
                    for ex_obj in objections_list
                )
                if not is_duplicate:
                    objections_list.append(
                        IdentifiedObjectionEntry(
                            text=obj_text_from_reaction,
                            status="active",
                            rebuttal_attempts=0,
                            source_turn=next_turn_number,
                            related_to_proposal=True,
                        )
                    )
                    profile_changed = True
                    objections_added_this_turn_texts.add(obj_text_from_reaction)
                    logger.debug(
                        f"[{node_name}] Added new objection '{obj_text_from_reaction[:50]}' from presentation reaction."
                    )

    # --- 5. Process Closing Status Updates ---
    closing_status_changed = False
    current_closing_status = state.get("closing_process_status", "not_started")
    last_action = state.get("last_agent_action")
    last_action_type = (
        last_action.get("action_type") if isinstance(last_action, dict) else None
    )

    if last_action_type in [
        "INITIATE_CLOSING",
        "CONFIRM_ORDER_DETAILS",
        "HANDLE_CLOSING_CORRECTION",
    ]:
        new_closing_status = current_closing_status
        intent = analysis.overall_intent
        if (
            intent == "ConfirmingCloseAttempt"
            and last_action_type == "INITIATE_CLOSING"
        ):
            new_closing_status = "awaiting_confirmation"
        elif (
            intent == "FinalOrderConfirmation"
            and last_action_type == "CONFIRM_ORDER_DETAILS"
        ):
            new_closing_status = "confirmed_success"
        elif intent == "RejectingCloseAttempt":
            new_closing_status = "confirmation_rejected"
        elif intent == "RequestingOrderCorrection":
            new_closing_status = "needs_correction"
        elif intent == "ProvidingCorrectionDetails":
            new_closing_status = (
                "awaiting_confirmation"  # Back to confirm after correction
            )

        if new_closing_status != current_closing_status:
            updated_state_delta["closing_process_status"] = new_closing_status
            closing_status_changed = True
            logger.info(
                f"[{node_name}] Closing status updated from '{current_closing_status}' to '{new_closing_status}' based on intent '{intent}' after action '{last_action_type}'."
            )

    # --- 6. Update Interruption Queue (Consolidated) ---
    # Add questions needing attention
    for q_analysis in questions_to_interrupt:
        q_text = q_analysis.question_text
        if q_text not in processed_interrupt_texts:
            new_interruptions_this_turn.append(
                UserInterruption(
                    type="direct_question",
                    text=q_text,
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )
            processed_interrupt_texts.add(q_text)

    # Add ACTIVE objections from the *updated* profile
    for obj_entry in dynamic_profile_data.get("identified_objections", []):
        obj_text = obj_entry.get("text", "")
        if (
            obj_entry.get("status") == "active"
            and obj_text not in processed_interrupt_texts
        ):
            new_interruptions_this_turn.append(
                UserInterruption(
                    type="objection",
                    text=obj_text,
                    status="pending_resolution",
                    turn_detected=obj_entry.get("source_turn", next_turn_number),
                )
            )
            processed_interrupt_texts.add(obj_text)

    # Add vague/off-topic flags
    if (
        analysis.is_primarily_vague_statement
        and "vague" not in processed_interrupt_texts
    ):
        vague_text = state.get("current_user_input_text", "[vague statement]")
        new_interruptions_this_turn.append(
            UserInterruption(
                type="vague_statement",
                text=vague_text,
                status="pending_resolution",
                turn_detected=next_turn_number,
            )
        )
        processed_interrupt_texts.add("vague")
    if analysis.is_primarily_off_topic and "off_topic" not in processed_interrupt_texts:
        off_topic_text = state.get("current_user_input_text", "[off-topic comment]")
        new_interruptions_this_turn.append(
            UserInterruption(
                type="off_topic_comment",
                text=off_topic_text,
                status="pending_resolution",
                turn_detected=next_turn_number,
            )
        )
        processed_interrupt_texts.add("off_topic")

    # Only update the state delta if the queue has actually changed
    current_queue_repr = sorted(
        [str(item) for item in state.get("user_interruptions_queue", [])]
    )
    new_queue_repr = sorted([str(item) for item in new_interruptions_this_turn])
    if new_queue_repr != current_queue_repr:
        updated_state_delta["user_interruptions_queue"] = new_interruptions_this_turn
        logger.debug(
            f"[{node_name}] Interrupt queue updated: {len(new_interruptions_this_turn)} items."
        )

    # --- 7. Process Analysis of Response to Agent Action ---
    logger.debug(
        f"[{node_name}] Analysis of user response to agent action: {analysis.analysis_of_response_to_agent_action.user_response_to_agent_action}"
    )

    # --- 8. Final Updates and Cleanup ---
    if profile_changed:  # Only add profile to delta if it actually changed
        # Convert back to plain dicts for state serialization
        updated_state_delta["customer_profile_dynamic"] = {
            "identified_needs": [
                dict(n) for n in dynamic_profile_data.get("identified_needs", [])
            ],
            "identified_pain_points": [
                dict(p) for p in dynamic_profile_data.get("identified_pain_points", [])
            ],
            "identified_objections": [
                dict(o) for o in dynamic_profile_data.get("identified_objections", [])
            ],
            "certainty_levels": dynamic_profile_data.get("certainty_levels"),
            "last_discerned_intent": dynamic_profile_data.get("last_discerned_intent"),
        }
        logger.trace(
            f"[{node_name}] Updated dynamic profile: {updated_state_delta.get('customer_profile_dynamic')}"
        )

    updated_state_delta["last_interaction_timestamp"] = time.time()
    updated_state_delta["user_input_analysis_result"] = None  # Clear analysis result
    updated_state_delta["last_processing_error"] = None  # Clear previous errors

    logger.info(f"[{node_name}] State update complete for Turn {next_turn_number}.")
    logger.debug(f"[{node_name}] State delta keys: {list(updated_state_delta.keys())}")
    if log_changed:
        logger.trace(f"[{node_name}] Updated question log: {current_question_log}")
    if "user_interruptions_queue" in updated_state_delta:
        logger.trace(
            f"[{node_name}] Updated interrupt queue: {updated_state_delta['user_interruptions_queue']}"
        )

    return updated_state_delta
