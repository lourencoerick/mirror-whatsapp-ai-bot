# backend/app/services/ai_reply/new_agent/components/final_state_updater.py

import time
from typing import Dict, Any, List, Optional
from loguru import logger
import copy

from langchain_core.messages import AIMessage, BaseMessage

from ..state_definition import (
    RichConversationState,
    PendingAgentAction,
    AgentActionDetails,
    AgentActionType,
    # Se for modificar IdentifiedObjectionEntry, importe-o
    IdentifiedObjectionEntry,
    CustomerQuestionEntry,
    CustomerQuestionStatusType,
    AgentGoal,
    ProposedSolution,
)


async def finalize_turn_state_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Performs final state updates at the end of the agent's turn.

    This node is responsible for:
    1. Adding the final formatted AI message (from `final_agent_message_text`
       or falling back to `last_agent_generation_text`) to the message history.
    2. Recording the action performed by the agent in this turn (`last_agent_action`)
       based on the `next_agent_action_command` and `action_parameters` set by
       the Planner, and the `last_agent_generation_text` from the Generator.
    3. If the action was `GENERATE_REBUTTAL`, updates the corresponding objection's
       status to 'addressing' and increments its `rebuttal_attempts` count in the
       customer profile.
    4. Clearing temporary fields from the state that are only relevant within a
       single turn (e.g., `next_agent_action_command`, `action_parameters`,
       `retrieved_knowledge_for_next_action`, generation texts, analysis result).

    Args:
        state: The current conversation state dictionary.
        config: The graph configuration dictionary (not used in this node).

    Returns:
        A dictionary containing the state updates (delta) to be merged into the
        main conversation state. This includes the updated message history,
        the recorded last action, potentially updated customer profile, and
        cleared temporary fields.
    """
    node_name = "finalize_turn_state_node"
    current_turn = state.get("current_turn_number", "N/A")
    logger.info(f"--- Starting Node: {node_name} (Finalizing Turn: {current_turn}) ---")

    updated_state_delta: Dict[str, Any] = {}
    profile_changed_by_final_updater = False  # <<< INICIALIZAR AQUI
    question_log_changedby_final_updater = False

    # --- 1. Adicionar Mensagem do Agente ao Histórico ---
    final_text_to_send = state.get("final_agent_message_text")
    raw_generated_text = state.get("last_agent_generation_text")

    current_messages = list(state.get("messages", []))
    current_question_log: List[CustomerQuestionEntry] = [
        entry.copy() for entry in state.get("customer_question_log", [])
    ]

    text_for_history = final_text_to_send if final_text_to_send else raw_generated_text
    if text_for_history:
        ai_message = AIMessage(content=text_for_history)
        current_messages.append(ai_message)
        updated_state_delta["messages"] = current_messages
        logger.debug(
            f"[{node_name}] Added AIMessage to history: '{text_for_history[:100]}...'"
        )
    else:
        logger.warning(
            f"[{node_name}] No agent message text (formatted or raw) found to add to history."
        )

    # --- 2. Registrar a Ação Executada e Atualizar Perfil se Rebuttal ---
    action_command_executed: Optional[AgentActionType] = state.get(
        "next_agent_action_command"
    )
    action_params_executed: AgentActionDetails = state.get("action_parameters", {})
    text_for_action_record = (
        raw_generated_text if raw_generated_text else final_text_to_send
    )

    # Fazer uma cópia profunda apenas se formos modificar o perfil dinâmico
    dynamic_profile_data_copy = None

    if action_command_executed and text_for_action_record:
        last_action = PendingAgentAction(
            action_type=action_command_executed,
            details=copy.deepcopy(action_params_executed),
            action_generation_text=text_for_action_record,
            attempts=1,
        )
        updated_state_delta["last_agent_action"] = last_action
        logger.debug(
            f"[{node_name}] Recorded last_agent_action: {action_command_executed}"
        )

        if action_command_executed == "GENERATE_REBUTTAL":
            # Só fazer deepcopy se realmente precisar modificar
            if dynamic_profile_data_copy is None:
                dynamic_profile_data_copy = copy.deepcopy(
                    state.get("customer_profile_dynamic", {})
                )
                dynamic_profile_data_copy.setdefault("identified_objections", [])

            objection_text_rebutted = action_params_executed.get(
                "objection_text_to_address"
            )
            if objection_text_rebutted:
                found_obj_to_update = False
                # Usar a cópia para modificação
                for i, obj_entry in enumerate(
                    dynamic_profile_data_copy.get("identified_objections", [])
                ):
                    if (
                        obj_entry.get("text") == objection_text_rebutted
                        and obj_entry.get("status")
                        == "active"  # Só atualiza se estava ativa
                    ):
                        # Modificar a cópia
                        dynamic_profile_data_copy["identified_objections"][i][
                            "status"
                        ] = "addressing"
                        dynamic_profile_data_copy["identified_objections"][i][
                            "rebuttal_attempts"
                        ] = (obj_entry.get("rebuttal_attempts", 0) + 1)
                        profile_changed_by_final_updater = True
                        found_obj_to_update = True
                        logger.info(
                            f"[{node_name}] Objection '{objection_text_rebutted[:30]}' status updated to 'addressing', attempts incremented to {dynamic_profile_data_copy['identified_objections'][i]['rebuttal_attempts']}."
                        )
                        break
                if not found_obj_to_update:
                    logger.warning(
                        f"[{node_name}] Tried to update status for rebutted objection '{objection_text_rebutted[:30]}', but it was not found with 'active' status in profile."
                    )

        elif action_command_executed == "ANSWER_DIRECT_QUESTION":

            question_answered_text = last_action.get("details", {}).get(
                "question_to_answer_text"
            )
            generated_answer_text = last_action.get("action_generation_text", "")

            if question_answered_text and generated_answer_text:
                # Obter texto de fallback do perfil da empresa
                company_profile = state.get("company_profile", {})
                fallback_text = company_profile.get(
                    "fallback_contact_info", "DEFAULT_FALLBACK_TEXT_IF_MISSING"
                )
                if not fallback_text:
                    fallback_text = "DEFAULT_FALLBACK_TEXT_IF_MISSING"  # Garantir que não seja vazio

                # Encontrar a pergunta correspondente no log (a mais recente com status 'newly_asked')
                question_log_index_to_update = -1
                for i in range(len(current_question_log) - 1, -1, -1):
                    log_entry = current_question_log[i]
                    # Comparar com o texto da pergunta nos detalhes da ação
                    if (
                        log_entry.get("extracted_question_core", "").lower()
                        == question_answered_text.lower()
                        and log_entry.get("status") == "newly_asked"
                    ):
                        question_log_index_to_update = i
                        break

                if question_log_index_to_update != -1:
                    new_status: CustomerQuestionStatusType
                    # Heurística: Checar se a resposta gerada contém o texto de fallback
                    if (
                        fallback_text != "DEFAULT_FALLBACK_TEXT_IF_MISSING"
                        and fallback_text.lower() in generated_answer_text.lower()
                    ):
                        new_status = "answered_with_fallback"
                        logger.info(
                            f"[{node_name}] Question '{question_answered_text[:30]}...' answered with fallback."
                        )
                    else:
                        new_status = "answered_satisfactorily"
                        logger.info(
                            f"[{node_name}] Question '{question_answered_text[:30]}...' answered satisfactorily."
                        )

                    # Atualizar o status na cópia do log
                    current_question_log[question_log_index_to_update][
                        "status"
                    ] = new_status
                    # Opcional: Adicionar resumo da resposta?
                    # current_question_log[question_log_index_to_update]["agent_direct_response_summary"] = generated_answer_text[:100] # Exemplo
                    question_log_changedby_final_updater = True
                    logger.info(
                        f"[{node_name}] Changing the question log... {current_question_log[question_log_index_to_update]} '"
                    )
                else:
                    logger.warning(
                        f"[{node_name}] Could not find 'newly_asked' question in log matching answered text: '{question_answered_text[:50]}...'"
                    )

        elif action_command_executed == "PRESENT_SOLUTION_OFFER":
            product_name = action_params_executed.get("product_name_to_present")
            key_benefit = action_params_executed.get("key_benefit_to_highlight")

            if product_name:
                logger.info(
                    f"[{node_name}] Action was PRESENT_SOLUTION_OFFER for product: {product_name}."
                )
                # Try to get price and URL from company_profile if available
                # This requires company_profile and offering_overview to be structured
                price: Optional[float] = None
                price_info_str: Optional[str] = None
                product_url: Optional[str] = None

                company_profile = state.get("company_profile")
                if company_profile and isinstance(company_profile, dict):
                    offerings = company_profile.get("offering_overview", [])
                    for offer in offerings:
                        if (
                            isinstance(offer, dict)
                            and offer.get("name") == product_name
                        ):
                            # Attempt to parse price if it's a string like "R$99,90"
                            price_str_from_profile = offer.get("price_info")
                            if price_str_from_profile:
                                try:
                                    # Basic parsing, might need to be more robust
                                    cleaned_price_str = (
                                        price_str_from_profile.replace("R$", "")
                                        .replace(",", ".")
                                        .strip()
                                    )
                                    price = float(cleaned_price_str)
                                    price_info_str = price_str_from_profile  # Keep original string for display
                                except ValueError:
                                    logger.warning(
                                        f"Could not parse price '{price_str_from_profile}' for {product_name}. Using original string."
                                    )
                                    price_info_str = price_str_from_profile  # Store the unparsed string
                                    price = None  # Explicitly set price to None if parsing fails

                            product_url = offer.get("link")
                            break

                new_proposal = ProposedSolution(
                    product_name=product_name,
                    product_url=product_url,  # Can be None
                    quantity=None,  # Default, can be updated later
                    price=price,  # Can be None if not found/parsed
                    price_info=price_info_str,  # Can be None
                    key_benefits_highlighted=[key_benefit] if key_benefit else [],
                    turn_proposed=int(current_turn),  # current_turn should be int
                    status="proposed",
                )
                updated_state_delta["active_proposal"] = new_proposal
                # Also update closing_process_status to indicate a proposal has been made,
                # but not yet fully initiated for closing.
                # 'not_started' might still be appropriate until user confirms interest in this proposal.
                # Or a new status like 'proposal_made'. For now, let's assume it doesn't change closing_process_status yet.
                logger.info(f"[{node_name}] Set active_proposal: {new_proposal}")
            else:
                logger.warning(
                    f"[{node_name}] PRESENT_SOLUTION_OFFER executed but no product_name found in action_parameters."
                )

    elif (
        action_command_executed and not text_for_action_record
    ):  # Ação planejada, mas sem texto
        logger.warning(
            f"[{node_name}] Action '{action_command_executed}' was planned but no text generated. Clearing last_agent_action."
        )
        updated_state_delta["last_agent_action"] = None
    else:  # Nenhuma ação planejada
        if state.get("last_agent_action") is not None:
            logger.debug(
                f"[{node_name}] No action command was planned for this turn. Clearing last_agent_action."
            )
            updated_state_delta["last_agent_action"] = None

    if profile_changed_by_final_updater and dynamic_profile_data_copy is not None:
        updated_state_delta["customer_profile_dynamic"] = dynamic_profile_data_copy

    if question_log_changedby_final_updater:
        updated_state_delta["customer_question_log"] = current_question_log

    # --- 3. Gerenciamento de Flags de Follow-up por Inatividade ---
    trigger_event = state.get("trigger_event")

    # Se o turno foi iniciado por uma mensagem real do usuário (não um timeout)
    # E havia um follow-up agendado, cancele-o e resete a contagem.
    if trigger_event == "user_message" or (
        trigger_event is None and state.get("current_user_input_text") is not None
    ):
        if state.get("follow_up_scheduled"):
            logger.info(
                f"[{node_name}] User responded. Cancelling scheduled follow-up."
            )
            updated_state_delta["follow_up_scheduled"] = False
            updated_state_delta["follow_up_attempt_count"] = 0
            updated_state_delta["last_message_from_agent_timestamp"] = (
                None  # Limpar timestamp
            )

    # Se o agente enviou uma mensagem neste turno, potencialmente agendar um follow-up
    if (
        final_text_to_send
    ):  # Verifica se uma mensagem foi efetivamente enviada ao usuário
        # Não agendar follow-up para despedidas ou confirmações finais de pedido
        actions_that_dont_need_follow_up: List[AgentActionType] = [
            "GENERATE_FAREWELL",
            "PROCESS_ORDER_CONFIRMATION",
        ]
        # Também não agendar se a ação foi DECIDE_PROACTIVE_STEP, pois ela mesma é um tipo de follow-up
        # ou leva a uma ação que pode precisar de seu próprio follow-up.
        if (
            action_command_executed
            and action_command_executed not in actions_that_dont_need_follow_up
            and action_command_executed != "DECIDE_PROACTIVE_STEP"
        ):

            # Não reagendar se o trigger foi um timeout e o agente acabou de enviar um follow-up
            # A menos que queiramos follow-ups encadeados, o que precisa de mais lógica.
            # Por agora, um follow-up por timeout não agenda outro imediatamente.
            if trigger_event != "follow_up_timeout":
                logger.info(
                    f"[{node_name}] Agent sent a message. Scheduling potential follow-up."
                )
                updated_state_delta["follow_up_scheduled"] = True
                updated_state_delta["last_message_from_agent_timestamp"] = time.time()
                # follow_up_attempt_count é incrementado pelo Planner quando um timeout ocorre
            else:
                logger.info(
                    f"[{node_name}] Agent sent a follow-up message due to timeout. Not re-scheduling follow-up immediately."
                )
                # Manter follow_up_scheduled como True se quisermos permitir múltiplos, mas o Planner controlaria o attempt_count.
                # Por segurança, vamos desativar para evitar loops se o Planner não resetar.
                # O Planner deve resetar `follow_up_scheduled` se o limite de tentativas for atingido.
                # Se o LLM do proactive_step_decider_node decidir por GENERATE_FAREWELL,
                # a condição acima (actions_that_dont_need_follow_up) já o pegaria.
                # Se o LLM decidir por outra ação, e quisermos outro follow-up,
                # o `follow_up_scheduled` deve permanecer True.
                # Vamos assumir que se o trigger foi timeout, o `follow_up_scheduled` já está True
                # e o `follow_up_attempt_count` foi incrementado pelo Planner.
                # Se a ação proativa não for um farewell, o `follow_up_scheduled` permanece True.
                if action_command_executed not in actions_that_dont_need_follow_up:
                    updated_state_delta["last_message_from_agent_timestamp"] = (
                        time.time()
                    )  # Atualiza o timestamp para o novo follow-up
                else:  # Se a ação proativa foi um farewell, desagenda.
                    updated_state_delta["follow_up_scheduled"] = False
                    updated_state_delta["follow_up_attempt_count"] = 0  # Reset
                    updated_state_delta["last_message_from_agent_timestamp"] = None

    # --- 4. Resetar Goal se Farewell foi Gerado ---
    if action_command_executed == "GENERATE_FAREWELL":
        logger.info(f"[{node_name}] Farewell generated. Resetting agent goal to IDLE.")
        updated_state_delta["current_agent_goal"] = AgentGoal(
            goal_type="IDLE", goal_details={}, previous_goal_if_interrupted=None
        )
        # Também garantir que o follow-up seja desativado após um farewell
        updated_state_delta["follow_up_scheduled"] = False
        updated_state_delta["follow_up_attempt_count"] = 0
        updated_state_delta["last_message_from_agent_timestamp"] = None

    # --- 5. Limpar Campos Temporários do Turno ---
    updated_state_delta["next_agent_action_command"] = None
    updated_state_delta["action_parameters"] = {}
    updated_state_delta["retrieved_knowledge_for_next_action"] = None
    updated_state_delta["last_agent_generation_text"] = None
    updated_state_delta["final_agent_message_text"] = None
    if (
        "user_input_analysis_result" in state
        and state["user_input_analysis_result"] is not None
    ):
        updated_state_delta["user_input_analysis_result"] = None

    if state.get("trigger_event") is not None:
        updated_state_delta["trigger_event"] = None

    logger.debug(f"[{node_name}] Cleared temporary turn fields.")
    logger.info(f"[{node_name}] Turn finalization complete for Turn: {current_turn}")

    logger.bind(payload=updated_state_delta).info(
        f"[{node_name}] Returning state delta."
    )

    return updated_state_delta
