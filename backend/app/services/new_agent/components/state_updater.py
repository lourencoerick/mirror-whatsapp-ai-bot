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
    logger.warning(
        f"[Analytics Event - TODO] MISSING_INFORMATION: Account={account_id}, Conv={conversation_id}, Question='{question_core}'"
    )
    pass


async def update_conversation_state_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
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

    current_question_log = [
        entry.copy() for entry in state.get("customer_question_log", [])
    ]
    current_interruptions = [
        inter.copy() for inter in state.get("user_interruptions_queue", [])
    ]
    current_dynamic_profile_dict = copy.deepcopy(
        state.get("customer_profile_dynamic", {})
    )

    # Construir dynamic_profile_data como um dicionário
    # A validação de tipo ocorre implicitamente ao acessar chaves esperadas pelo TypedDict
    # e ao construir os TypedDicts internos como IdentifiedNeedEntry.
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
    # Se você quiser forçar uma validação Pydantic aqui (embora TypedDict não tenha .model_validate):
    try:
        DynamicCustomerProfile(
            **dynamic_profile_data
        )  # Tenta construir para validar estrutura
    except TypeError as te:
        logger.error(
            f"[{node_name}] Constructed dynamic_profile_data does not match TypedDict: {te}"
        )
        # Lidar com o erro, talvez resetando para um perfil vazio

    profile_changed = False

    if analysis.overall_intent:
        if dynamic_profile_data.get("last_discerned_intent") != analysis.overall_intent:
            dynamic_profile_data["last_discerned_intent"] = analysis.overall_intent
            profile_changed = True
            logger.debug(f"Updated last_discerned_intent to: {analysis.overall_intent}")

    # --- 1. Processar Perguntas Extraídas ---
    newly_added_to_log_count = 0
    updated_log_entry_count = 0
    questions_for_interrupt_queue_texts: List[str] = []
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
            new_status: CustomerQuestionStatusType = log_entry_to_update.get("status")
            if q_analysis.status_of_original_answer == "answered_satisfactorily":
                new_status = "repetition_after_satisfactory_answer"
            elif q_analysis.status_of_original_answer == "answered_with_fallback":
                new_status = "repetition_after_fallback"
                await _log_missing_information_event(
                    state.get("account_id"),
                    state.get("conversation_id"),
                    q_analysis.question_text,
                )
            else:
                new_status = "repetition_after_fallback"
            if log_entry_to_update.get("status") != new_status:
                log_entry_to_update["status"] = new_status
                updated_log_entry_count += 1
            if new_status in [
                "repetition_after_satisfactory_answer",
                "repetition_after_fallback",
            ]:
                questions_for_interrupt_queue_texts.append(q_analysis.question_text)
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
            questions_for_interrupt_queue_texts.append(q_analysis.question_text)
    if newly_added_to_log_count > 0 or updated_log_entry_count > 0:
        updated_state_delta["customer_question_log"] = current_question_log

    # --- 2. Processar Objeções Extraídas ---
    logger.debug(
        f"[{node_name}] P2 Start: initial identified_objections in dynamic_profile_data: {dynamic_profile_data.get('identified_objections')}"
    )
    identified_objections_list_p2 = dynamic_profile_data.setdefault(
        "identified_objections", []
    )

    for obj_idx, obj_from_analysis in enumerate(analysis.extracted_objections):
        logger.debug(
            f"[{node_name}] P2: Processing extracted_objection from analysis #{obj_idx}: '{obj_from_analysis.objection_text}'"
        )

        is_duplicate = any(
            existing_obj.get("text") == obj_from_analysis.objection_text
            and existing_obj.get("status") in ["active", "addressing"]
            for existing_obj in identified_objections_list_p2  # Checar contra a lista atual
        )
        logger.debug(
            f"[{node_name}] P2: Is '{obj_from_analysis.objection_text}' duplicate in current list? {is_duplicate}"
        )

        if not is_duplicate:
            new_objection_entry = IdentifiedObjectionEntry(
                text=obj_from_analysis.objection_text,
                status="active",
                rebuttal_attempts=0,
                source_turn=next_turn_number,
                related_to_proposal=None,
            )
            identified_objections_list_p2.append(new_objection_entry)
            profile_changed = True
            logger.debug(
                f"[{node_name}] P2: Added new objection: '{obj_from_analysis.objection_text}'. Current list: {identified_objections_list_p2}"
            )
        else:
            logger.debug(
                f"[{node_name}] P2: Objection '{obj_from_analysis.objection_text}' is a duplicate, not adding again in P2."
            )

    logger.debug(
        f"[{node_name}] P2 End: final identified_objections in dynamic_profile_data: {dynamic_profile_data.get('identified_objections')}"
    )

    # --- 3. Processar Necessidades/Dores Extraídas ---
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
            else:
                entry_data = IdentifiedPainPointEntry(
                    text=np.text, status="active", source_turn=next_turn_number
                )
            target_list_in_profile.append(entry_data)
            profile_changed = True

    # --- 4. Processar Status da Objeção Após Rebuttal ---
    if (
        analysis.objection_status_after_rebuttal
        and analysis.objection_status_after_rebuttal.status != "not_applicable"
        and analysis.objection_status_after_rebuttal.original_objection_text_handled
    ):
        original_obj_text = (
            analysis.objection_status_after_rebuttal.original_objection_text_handled
        )
        new_status_from_analysis = analysis.objection_status_after_rebuttal.status
        new_obj_text = analysis.objection_status_after_rebuttal.new_objection_text

        found_and_updated_original_objection = False
        identified_objections_list_p4 = dynamic_profile_data.setdefault(
            "identified_objections", []
        )
        for i, obj_entry_dict in enumerate(identified_objections_list_p4):
            if obj_entry_dict.get("text") == original_obj_text and obj_entry_dict.get(
                "status"
            ) not in ["resolved", "ignored"]:
                logger.debug(
                    f"[{node_name}] P4: Updating status for objection: '{original_obj_text[:50]}...' to '{new_status_from_analysis}'"
                )
                original_obj_status_before_update = obj_entry_dict.get("status")
                current_rebuttal_attempts = obj_entry_dict.get("rebuttal_attempts", 0)

                if new_status_from_analysis == "appears_resolved":
                    identified_objections_list_p4[i]["status"] = "resolved"
                    current_interruptions = [
                        inter
                        for inter in current_interruptions
                        if not (
                            inter.get("type") == "objection"
                            and inter.get("text") == original_obj_text
                        )
                    ]
                elif new_status_from_analysis == "still_persists":
                    identified_objections_list_p4[i]["status"] = "active"
                    # Remover depois de testar sem e funcionar, entender o pq
                    # identified_objections_list_p4[i]["rebuttal_attempts"] = (
                    #     current_rebuttal_attempts + 1
                    # )
                    logger.debug(
                        f"[{node_name}] P4: Objection '{original_obj_text[:50]}' updated to active, attempts incremented."
                    )
                elif (
                    new_status_from_analysis == "new_objection_raised" and new_obj_text
                ):
                    identified_objections_list_p4[i]["status"] = "ignored"
                    is_new_obj_duplicate = any(
                        eo.get("text") == new_obj_text
                        and eo.get("status") in ["active", "addressing"]
                        for eo in identified_objections_list_p4
                    )
                    if not is_new_obj_duplicate:
                        identified_objections_list_p4.append(
                            IdentifiedObjectionEntry(
                                text=new_obj_text,
                                status="active",
                                rebuttal_attempts=0,
                                source_turn=next_turn_number,
                                related_to_proposal=None,
                            )
                        )
                elif new_status_from_analysis in [
                    "unclear_still_evaluating",
                    "changed_topic",
                ]:
                    identified_objections_list_p4[i]["status"] = "active"

                # Checar se houve mudança real para setar profile_changed
                if (
                    identified_objections_list_p4[i].get("status")
                    != original_obj_status_before_update
                    or identified_objections_list_p4[i].get("rebuttal_attempts")
                    != current_rebuttal_attempts
                ):
                    profile_changed = True
                found_and_updated_original_objection = True
                break

        if (
            not found_and_updated_original_objection
            and new_status_from_analysis == "new_objection_raised"
            and new_obj_text
        ):
            identified_objections_list_p4 = dynamic_profile_data.setdefault(
                "identified_objections", []
            )
            is_new_obj_duplicate = any(
                eo.get("text") == new_obj_text
                and eo.get("status") in ["active", "addressing"]
                for eo in identified_objections_list_p4
            )
            if not is_new_obj_duplicate:
                identified_objections_list_p4.append(
                    IdentifiedObjectionEntry(
                        text=new_obj_text,
                        status="active",
                        rebuttal_attempts=0,
                        source_turn=next_turn_number,
                        related_to_proposal=None,
                    )
                )
                profile_changed = True

    # --- 5. Processar Reação à Apresentação de Solução ---
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
            identified_objections_list_p5 = dynamic_profile_data.setdefault(
                "identified_objections", []
            )
            found_and_updated = False
            for i, obj_entry_dict in enumerate(identified_objections_list_p5):
                if obj_entry_dict.get("text") == obj_text_from_reaction:
                    if obj_entry_dict.get("related_to_proposal") is not True:
                        identified_objections_list_p5[i]["related_to_proposal"] = True
                        profile_changed = True
                    found_and_updated = True
                    break
            if not found_and_updated:
                identified_objections_list_p5.append(
                    IdentifiedObjectionEntry(
                        text=obj_text_from_reaction,
                        status="active",
                        rebuttal_attempts=0,
                        source_turn=next_turn_number,
                        related_to_proposal=True,
                    )
                )
                profile_changed = True
        # ... (outros casos de reaction) ...

    if profile_changed:
        updated_state_delta["customer_profile_dynamic"] = dynamic_profile_data

    # --- 6. Atualizar Fila de Interrupções (Consolidado) ---
    # ... (lógica como antes, usando dynamic_profile_data.get("identified_objections", [])) ...
    for q_text in questions_for_interrupt_queue_texts:
        if not any(
            inter.get("text") == q_text and inter.get("type") == "direct_question"
            for inter in current_interruptions
        ):
            current_interruptions.append(
                UserInterruption(
                    type="direct_question",
                    text=q_text,
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )
    for obj_entry_dict in dynamic_profile_data.get("identified_objections", []):
        if obj_entry_dict.get("status") == "active":
            if not any(
                inter.get("text") == obj_entry_dict.get("text")
                and inter.get("type") == "objection"
                for inter in current_interruptions
            ):
                current_interruptions.append(
                    UserInterruption(
                        type="objection",
                        text=obj_entry_dict.get("text", ""),
                        status="pending_resolution",
                        turn_detected=next_turn_number,
                    )
                )
    if analysis.is_primarily_vague_statement:
        if not any(
            inter.get("type") == "vague_statement"
            and inter.get("turn_detected") == next_turn_number
            for inter in current_interruptions
        ):
            current_interruptions.append(
                UserInterruption(
                    type="vague_statement",
                    text=state.get("current_user_input_text", ""),
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )
    if analysis.is_primarily_off_topic:
        if not any(
            inter.get("type") == "off_topic_comment"
            and inter.get("turn_detected") == next_turn_number
            for inter in current_interruptions
        ):
            current_interruptions.append(
                UserInterruption(
                    type="off_topic_comment",
                    text=state.get("current_user_input_text", ""),
                    status="pending_resolution",
                    turn_detected=next_turn_number,
                )
            )
    if current_interruptions != state.get(
        "user_interruptions_queue", []
    ):  # Comparar com a fila original do estado
        updated_state_delta["user_interruptions_queue"] = current_interruptions

    # --- 7. Processar Análise da Resposta à Ação do Agente ---
    logger.debug(
        f"Analysis of user response to agent action: {analysis.analysis_of_response_to_agent_action.user_response_to_agent_action}"
    )

    # --- 8. Atualizar Metadados e Limpeza ---
    updated_state_delta["last_interaction_timestamp"] = time.time()
    updated_state_delta["user_input_analysis_result"] = None
    updated_state_delta["last_processing_error"] = None

    logger.info(f"[{node_name}] State update complete for Turn {next_turn_number}.")
    logger.debug(f"[{node_name}] State delta keys: {list(updated_state_delta.keys())}")

    return updated_state_delta
