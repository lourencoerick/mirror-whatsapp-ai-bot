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
)


async def finalize_turn_state_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Updates the state at the very end of the agent's turn, after response generation and formatting.
    Adds the final AI message to history, records the action taken, and cleans up temporary fields.
    """
    node_name = "finalize_turn_state_node"
    current_turn = state.get("current_turn_number", "N/A")
    logger.info(f"--- Starting Node: {node_name} (Finalizing Turn: {current_turn}) ---")

    updated_state_delta: Dict[str, Any] = {}
    profile_changed_by_final_updater = False  # <<< INICIALIZAR AQUI

    # --- 1. Adicionar Mensagem do Agente ao Histórico ---
    final_text_to_send = state.get("final_agent_message_text")
    raw_generated_text = state.get("last_agent_generation_text")

    current_messages = list(state.get("messages", []))

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

    # --- 3. Limpar Campos Temporários do Turno ---
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

    logger.debug(f"[{node_name}] Cleared temporary turn fields.")
    logger.info(f"[{node_name}] Turn finalization complete for Turn: {current_turn}")

    logger.bind(payload=updated_state_delta).info(
        f"[{node_name}] Returning state delta."
    )

    return updated_state_delta
