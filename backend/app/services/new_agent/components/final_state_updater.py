# app/services/ai_reply/new_agent/components/final_state_updater.py
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
)


async def finalize_turn_state_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Updates the state at the very end of the agent's turn, after response generation.
    Adds AI message to history, records the action taken, and cleans up temporary fields.
    """
    node_name = "finalize_turn_state_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    updated_state_delta: Dict[str, Any] = {}

    # --- 1. Adicionar Mensagem do Agente ao Histórico ---
    generated_text = state.get(
        "last_agent_generation_text"
    )  # Texto antes da formatação final
    # Ou usar o texto formatado? Depende se queremos o histórico com ou sem formatação.
    # Vamos usar o texto gerado antes da formatação final para o histórico interno.

    current_messages = list(state.get("messages", []))  # Cópia

    if generated_text:
        ai_message = AIMessage(content=generated_text)
        current_messages.append(ai_message)
        updated_state_delta["messages"] = current_messages
        logger.debug(f"[{node_name}] Added AIMessage to history.")
    else:
        logger.warning(f"[{node_name}] No generated text found to add to history.")

    # --- 2. Registrar a Ação Executada ---
    # Pegar o comando e parâmetros que *foram usados* para gerar a resposta
    action_command_executed: Optional[AgentActionType] = state.get(
        "next_agent_action_command"
    )
    action_params_executed: AgentActionDetails = state.get("action_parameters", {})

    if action_command_executed and generated_text:
        # Criar o registro da ação que acabou de acontecer
        last_action = PendingAgentAction(
            action_type=action_command_executed,
            details=copy.deepcopy(action_params_executed),  # Copiar detalhes
            action_generation_text=generated_text,  # Texto gerado
            attempts=1,  # Assumindo primeira tentativa bem-sucedida aqui
        )
        updated_state_delta["last_agent_action"] = last_action
        logger.debug(
            f"[{node_name}] Recorded last agent action: {action_command_executed}"
        )
    elif not generated_text and action_command_executed:
        # Se um comando foi planejado mas não gerou texto (erro/fallback no generator)
        # talvez registrar a tentativa falha? Ou apenas limpar? Limpar por ora.
        updated_state_delta["last_agent_action"] = None
        logger.warning(
            f"[{node_name}] Action {action_command_executed} was planned but no text generated. Clearing last_agent_action."
        )
    else:
        # Se nenhum comando foi planejado, limpar last_agent_action
        updated_state_delta["last_agent_action"] = None

    # --- 3. Limpar Campos Temporários do Turno ---
    updated_state_delta["next_agent_action_command"] = None
    updated_state_delta["action_parameters"] = {}
    updated_state_delta["retrieved_knowledge_for_next_action"] = None
    updated_state_delta["last_agent_generation_text"] = None
    # Manter o final_agent_message_text? Ou ele só é usado para enviar? Limpar.
    updated_state_delta["final_agent_message_text"] = None
    # Limpar o resultado da análise do input se ainda não foi limpo pelo StateUpdater inicial
    updated_state_delta["user_input_analysis_result"] = None

    logger.debug(f"[{node_name}] Cleared temporary turn fields.")
    logger.info(f"[{node_name}] Turn finalization complete.")

    return updated_state_delta
