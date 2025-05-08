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


async def _log_missing_information_event(account_id, conversation_id, question_core):
    """Logs an event when information is missing (placeholder)."""
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
    the RichConversationState, updating the question log, dynamic customer
    profile (needs, pains, objections), interruption queue, and other relevant
    metadata for the next turn.

    Args:
        state: The current conversation state.
        config: The graph configuration (not typically used directly here).

    Returns:
        A dictionary containing the state updates (delta).
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
            f"[{node_name}] No user_input_analysis_result. Skipping detailed state update."
        )
        return {"last_processing_error": None, "current_turn_number": next_turn_number}
    try:
        analysis = UserInputAnalysisOutput.model_validate(user_input_analysis_dict)
    except Exception as e:
        logger.exception(
            f"[{node_name}] Failed to validate user_input_analysis_result: {e}"
        )
        return {
            "last_processing_error": f"State update failed: Invalid input analysis. Details: {e}"
        }

    # --- Prepare working copies ---
    current_question_log = [
        entry.copy() for entry in state.get("customer_question_log", [])
    ]
    new_interruptions_this_turn: List[UserInterruption] = []
    current_dynamic_profile_dict = copy.deepcopy(
        state.get("customer_profile_dynamic", {})
    )
    dynamic_profile_data: DynamicCustomerProfile = {
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
    }
    profile_changed = False
    log_changed = False
    processed_interrupt_texts = set()

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
            new_status: CustomerQuestionStatusType = log_entry_to_update.get("status")  # type: ignore
            should_add_to_interrupt = False
            if q_analysis.status_of_original_answer == "answered_satisfactorily":
                new_status = "repetition_after_satisfactory_answer"
                should_add_to_interrupt = True
            elif q_analysis.status_of_original_answer == "answered_with_fallback":
                new_status = "repetition_after_fallback"
                await _log_missing_information_event(
                    state.get("account_id"),
                    state.get("conversation_id"),
                    q_analysis.question_text,
                )
                should_add_to_interrupt = True
            else:
                new_status = "repetition_after_fallback"
                should_add_to_interrupt = True

            if log_entry_to_update.get("status") != new_status:
                log_entry_to_update["status"] = new_status
                updated_log_entry_count += 1
                log_changed = True

            if should_add_to_interrupt:
                questions_to_interrupt.append(q_analysis)
        else:
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
            questions_to_interrupt.append(q_analysis)

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
            target_list_in_profile.append(entry_data)
            profile_changed = True
    if needs_added > 0 or pains_added > 0:
        logger.debug(
            f"[{node_name}] Profile updated: {needs_added} needs, {pains_added} pains added."
        )

    # --- REFINED OBJECTION HANDLING ---
    objections_list = dynamic_profile_data.setdefault("identified_objections", [])
    handled_original_objection_text: Optional[str] = None
    was_persistence_detected = False
    newly_raised_objection_text_after_rebuttal: Optional[str] = None
    objections_added_this_turn_texts = set()  # Track texts added in this update

    # 3. Process Status of Objection After Rebuttal FIRST
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
        handled_original_objection_text = original_obj_text_handled

        original_obj_index = -1
        for i, obj_entry in enumerate(objections_list):
            if obj_entry.get("text") == original_obj_text_handled:
                original_obj_index = i
                break

        if original_obj_index != -1:
            logger.debug(
                f"[{node_name}] P3: Found original objection '{original_obj_text_handled}' at index {original_obj_index} to update based on status '{new_status_from_analysis}'."
            )
            original_obj_status_before_update = objections_list[original_obj_index].get(
                "status"
            )

            if new_status_from_analysis == "appears_resolved":
                objections_list[original_obj_index]["status"] = "resolved"
            elif new_status_from_analysis == "still_persists":
                objections_list[original_obj_index]["status"] = "active"
                was_persistence_detected = (
                    True  # Flag that persistence was handled for the original objection
                )
            elif new_status_from_analysis == "new_objection_raised":
                objections_list[original_obj_index]["status"] = "ignored"
                if new_obj_text_if_raised:
                    newly_raised_objection_text_after_rebuttal = new_obj_text_if_raised
            elif new_status_from_analysis in [
                "unclear_still_evaluating",
                "changed_topic",
            ]:
                objections_list[original_obj_index][
                    "status"
                ] = "active"  # Treat as active/persistent

            if (
                objections_list[original_obj_index].get("status")
                != original_obj_status_before_update
            ):
                profile_changed = True
                logger.debug(
                    f"[{node_name}] P3: Updated status of '{original_obj_text_handled}' from '{original_obj_status_before_update}' to '{objections_list[original_obj_index]['status']}'."
                )
        else:
            logger.warning(
                f"[{node_name}] P3: Could not find original objection '{original_obj_text_handled}' in profile to update status based on rebuttal analysis."
            )
            if (
                new_status_from_analysis == "new_objection_raised"
                and new_obj_text_if_raised
            ):
                newly_raised_objection_text_after_rebuttal = new_obj_text_if_raised

    # 4. Process Extracted Objections (from current input)
    objections_added_from_extraction = 0
    for obj_from_analysis in analysis.extracted_objections:
        # Skip if this objection text was already identified as the 'newly_raised_objection_text_after_rebuttal'
        if (
            newly_raised_objection_text_after_rebuttal
            and obj_from_analysis.objection_text
            == newly_raised_objection_text_after_rebuttal
        ):
            logger.debug(
                f"[{node_name}] P4: Skipping extracted objection '{obj_from_analysis.objection_text}' as it was handled as 'new_objection_raised' after rebuttal."
            )
            continue

        # Skip if persistence was detected for the original objection. Assume this extracted text is just a rephrasing.
        if was_persistence_detected:
            logger.debug(
                f"[{node_name}] P4: Skipping extracted objection '{obj_from_analysis.objection_text}' because persistence of original objection '{handled_original_objection_text}' was detected."
            )
            continue

        # Check for duplicates among existing active/addressing objections
        is_duplicate = any(
            existing_obj.get("text") == obj_from_analysis.objection_text
            and existing_obj.get("status") in ["active", "addressing"]
            for existing_obj in objections_list
        )
        if not is_duplicate:
            new_objection_entry = IdentifiedObjectionEntry(
                text=obj_from_analysis.objection_text,
                status="active",
                rebuttal_attempts=0,
                source_turn=next_turn_number,
                related_to_proposal=None,  # Default
            )
            objections_list.append(new_objection_entry)
            objections_added_from_extraction += 1
            objections_added_this_turn_texts.add(
                obj_from_analysis.objection_text
            )  # Track added text
            profile_changed = True

    # Add the newly raised objection from the rebuttal analysis if it wasn't added above and isn't duplicate
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
                f"[{node_name}] Added new objection '{newly_raised_objection_text_after_rebuttal}' from rebuttal analysis."
            )

    if objections_added_from_extraction > 0:
        logger.debug(
            f"[{node_name}] Profile updated: {objections_added_from_extraction} new objections added from direct extraction."
        )

    # 5. Process Reaction to Solution Presentation
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
            objections_list_p5 = dynamic_profile_data.setdefault(
                "identified_objections", []
            )
            found_existing_objection = False
            for i, obj_entry in enumerate(objections_list_p5):
                if obj_entry.get("text") == obj_text_from_reaction:
                    if obj_entry.get("related_to_proposal") is not True:
                        objections_list_p5[i]["related_to_proposal"] = True
                        profile_changed = True
                        logger.debug(
                            f"[{node_name}] Marked existing objection '{obj_text_from_reaction[:50]}' as related to proposal."
                        )
                    found_existing_objection = True
                    break
            if not found_existing_objection:
                # Add it as a new objection if not already added
                is_duplicate = any(
                    existing_obj.get("text") == obj_text_from_reaction
                    and existing_obj.get("status") in ["active", "addressing"]
                    for existing_obj in objections_list_p5
                )
                if (
                    not is_duplicate
                    and obj_text_from_reaction not in objections_added_this_turn_texts
                ):
                    objections_list_p5.append(
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

    # --- NEW: 5b. Process Confirmation/Rejection of Closing Attempt ---
    closing_status_changed = False
    current_closing_status = state.get("closing_process_status", "not_started")

    last_action = state.get(
        "last_agent_action"
    )  # Get the action object (could be None)
    last_action_type = None
    if isinstance(last_action, dict):  # Check if it's a dictionary before getting type
        last_action_type = last_action.get("action_type")

    if last_action_type in [
        "INITIATE_CLOSING",
        "CONFIRM_ORDER_DETAILS",
        "HANDLE_CLOSING_CORRECTION",
    ]:
        if (
            analysis.overall_intent == "ConfirmingCloseAttempt"
            and last_action_type == "INITIATE_CLOSING"
        ):
            # Only move to awaiting_confirmation after initial confirmation
            if current_closing_status != "awaiting_confirmation":
                updated_state_delta["closing_process_status"] = "awaiting_confirmation"
                closing_status_changed = True
                logger.info(
                    f"[{node_name}] Closing status updated to awaiting_confirmation."
                )
        elif (
            analysis.overall_intent == "FinalOrderConfirmation"
            and last_action_type == "CONFIRM_ORDER_DETAILS"
        ):
            # Only move to confirmed_success after final confirmation
            if current_closing_status != "confirmed_success":
                updated_state_delta["closing_process_status"] = "confirmed_success"
                closing_status_changed = True
                logger.info(
                    f"[{node_name}] Closing status updated to confirmed_success."
                )
        elif analysis.overall_intent == "RejectingCloseAttempt":
            if current_closing_status != "confirmation_rejected":
                updated_state_delta["closing_process_status"] = "confirmation_rejected"
                closing_status_changed = True
                logger.info(
                    f"[{node_name}] Closing status updated to confirmation_rejected (after {last_action_type})."
                )
        elif analysis.overall_intent == "RequestingOrderCorrection":
            if current_closing_status != "needs_correction":
                updated_state_delta["closing_process_status"] = "needs_correction"
                closing_status_changed = True
                logger.info(
                    f"[{node_name}] Closing status updated to needs_correction (after {last_action_type})."
                )

        elif analysis.overall_intent == "ProvidingCorrectionDetails":
            # Store correction details (e.g., in a temporary field or log) - For now, just log
            if analysis.correction_details_text:
                logger.info(
                    f"[{node_name}] User provided correction details: {analysis.correction_details_text}"
                )
                # TODO: Decide how to store/use this text later (e.g., update active_proposal?)
            # Set status back to awaiting confirmation for the planner
            if current_closing_status != "awaiting_confirmation":
                updated_state_delta["closing_process_status"] = "awaiting_confirmation"
                closing_status_changed = True
                logger.info(
                    f"[{node_name}] Closing status updated to awaiting_confirmation (after correction provided)."
                )

    # --- 6. Update Interruption Queue (Consolidated) ---
    # Rebuild the queue based on the final state of questions and objections

    # Add questions needing attention
    for q_analysis in questions_to_interrupt:
        if q_analysis.question_text not in processed_interrupt_texts:
            new_interruptions_this_turn.append(
                UserInterruption(
                    type="direct_question",
                    text=q_analysis.question_text,
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )
            processed_interrupt_texts.add(q_analysis.question_text)

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
                    turn_detected=obj_entry.get(
                        "source_turn", next_turn_number
                    ),  # Use source turn if available
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
    # Compare based on content, not just object identity
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
    if profile_changed or closing_status_changed:
        # Convert back to plain dicts if necessary for state serialization
        # (TypedDicts are structurally dicts, so this might not be needed depending on LangGraph/checkpointer)
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

    updated_state_delta["last_interaction_timestamp"] = time.time()
    updated_state_delta["user_input_analysis_result"] = None
    updated_state_delta["last_processing_error"] = None

    logger.info(f"[{node_name}] State update complete for Turn {next_turn_number}.")
    logger.debug(f"[{node_name}] State delta keys: {list(updated_state_delta.keys())}")
    if profile_changed:
        logger.trace(
            f"[{node_name}] Updated dynamic profile: {updated_state_delta.get('customer_profile_dynamic')}"
        )
    if log_changed:
        logger.trace(f"[{node_name}] Updated question log: {current_question_log}")
    if "user_interruptions_queue" in updated_state_delta:
        logger.trace(
            f"[{node_name}] Updated interrupt queue: {updated_state_delta['user_interruptions_queue']}"
        )

    return updated_state_delta
