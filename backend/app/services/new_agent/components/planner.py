# backend/app/services/ai_reply/new_agent/components/planner.py

from typing import Dict, List, Optional, Any, Tuple
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
    PendingAgentAction,  # Adicionado para last_agent_action
    IdentifiedNeedEntry,  # Para checar necessidades
)

# (Opcional) LLM para refinamento (não usado na v1)
# from langchain_core.language_models import BaseChatModel

# --- Constantes ---
# DEFAULT_SALES_GOAL_SEQUENCE: List[AgentGoalType] = [...] # Pode ser removido se não usado diretamente

INTERRUPTION_TO_ACTION_MAP: Dict[str, AgentActionType] = {
    "direct_question": "ANSWER_DIRECT_QUESTION",
    "objection": "GENERATE_REBUTTAL",
    "vague_statement": "ASK_CLARIFYING_QUESTION",
    "off_topic_comment": "ACKNOWLEDGE_AND_TRANSITION",
}

MAX_SPIN_QUESTIONS_PER_CYCLE = 5  # Definido aqui para clareza


# --- Funções Auxiliares ---
def _get_next_spin_type(last_spin_type: Optional[SpinQuestionType]) -> SpinQuestionType:
    """Determina o próximo tipo de pergunta SPIN numa sequência simples."""
    if last_spin_type == "Situation":
        return "Problem"
    elif last_spin_type == "Problem":
        return "Implication"
    elif last_spin_type == "Implication":
        return "NeedPayoff"
    elif last_spin_type == "NeedPayoff":
        return "Problem"  # Loop back
    else:
        return "Situation"  # Default start


def _select_product_and_benefit_for_presentation(
    customer_profile: Dict[str, Any],  # customer_profile_dynamic
    company_profile_offerings: List[
        Dict[str, Any]
    ],  # company_profile.offering_overview
) -> Tuple[str, str]:
    """
    Seleciona um produto e benefício para apresentar com base nas necessidades identificadas.
    Lógica inicial simples.
    """
    product_to_present = "Nossa Solução Principal"  # Default
    key_benefit = "atender às suas necessidades gerais"

    identified_needs: List[IdentifiedNeedEntry] = customer_profile.get(
        "identified_needs", []
    )

    # Priorizar necessidades confirmadas ou de alta prioridade
    target_need: Optional[IdentifiedNeedEntry] = None
    confirmed_needs = [
        n for n in identified_needs if n.get("status") == "confirmed_by_user"
    ]

    if confirmed_needs:
        # Ordenar por prioridade (maior primeiro) ou pegar a mais recente se não houver prioridade
        confirmed_needs.sort(
            key=lambda x: (x.get("priority", 0), x.get("source_turn", 0)), reverse=True
        )
        target_need = confirmed_needs[0]
    elif identified_needs:
        # Se não há confirmadas, pegar a de maior prioridade ou mais recente das ativas
        active_needs = [n for n in identified_needs if n.get("status") == "active"]
        active_needs.sort(
            key=lambda x: (x.get("priority", 0), x.get("source_turn", 0)), reverse=True
        )
        if active_needs:
            target_need = active_needs[0]

    if target_need:
        target_need_text = target_need.get("text", "sua necessidade principal")
        key_benefit = f"o seu desafio em relação a '{target_need_text}'"

        # Lógica de Mapeamento Necessidade -> Produto (Muito Simplificada)
        # TODO: Melhorar esta lógica, talvez com embeddings ou LLM
        if company_profile_offerings:
            for offering in company_profile_offerings:
                offering_name = offering.get("name", "").lower()
                offering_desc = offering.get("short_description", "").lower()
                # Tentar um match simples de palavras-chave
                # (Isso é frágil e precisa ser melhorado)
                if any(
                    keyword in target_need_text.lower()
                    for keyword in offering_name.split() + offering_desc.split()
                    if len(keyword) > 3
                ):
                    product_to_present = offering.get("name", product_to_present)
                    logger.debug(
                        f"Planner: Matched need '{target_need_text}' to product '{product_to_present}' based on keywords."
                    )
                    break
            else:  # Se nenhum match por keyword
                product_to_present = (
                    company_profile_offerings[0].get("name", product_to_present)
                    if company_profile_offerings
                    else product_to_present
                )
                logger.debug(
                    f"Planner: No specific product match for need '{target_need_text}', defaulting to '{product_to_present}'."
                )
        else:
            logger.warning("Planner: No company offerings found to match needs.")

    return product_to_present, key_benefit


# --- Nó Principal do Planejador ---
async def goal_and_action_planner_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    node_name = "goal_and_action_planner_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    current_goal = copy.deepcopy(state.get("current_agent_goal", {"goal_type": "IDLE"}))
    interruptions_queue = [
        inter.copy() for inter in state.get("user_interruptions_queue", [])
    ]
    # Obter cópias para evitar modificar o estado diretamente se não for o resultado final
    customer_profile = copy.deepcopy(state.get("customer_profile_dynamic", {}))
    last_agent_action = copy.deepcopy(state.get("last_agent_action"))
    company_profile = state.get("company_profile", {})  # Usado para offerings

    planned_goal: AgentGoal = current_goal
    planned_action_command: Optional[AgentActionType] = None
    planned_action_parameters: AgentActionDetails = {}
    updated_interruptions_queue = list(interruptions_queue)  # Garantir cópia

    interruption_handled = False
    if updated_interruptions_queue:  # Usar a cópia
        # ... (lógica de tratamento de interrupções como antes, usando updated_interruptions_queue.pop) ...
        interruption_to_handle = None
        resolved_interruption_index = -1
        for i, interruption in enumerate(
            updated_interruptions_queue
        ):  # Iterar na cópia
            if interruption.get("status") == "pending_resolution":
                interruption_to_handle = interruption
                resolved_interruption_index = i
                logger.info(
                    f"[{node_name}] Prioritizing interruption: Type='{interruption.get('type')}', Text='{interruption.get('text', '')[:50]}...'"
                )
                break

        if interruption_to_handle:
            interruption_type = interruption_to_handle.get("type")
            interruption_text = interruption_to_handle.get("text", "")
            action_for_interruption = INTERRUPTION_TO_ACTION_MAP.get(interruption_type)

            if action_for_interruption:
                planned_action_command = action_for_interruption
                if interruption_type == "direct_question":
                    planned_action_parameters["question_to_answer_text"] = (
                        interruption_text
                    )
                elif interruption_type == "objection":
                    planned_action_parameters["objection_text_to_address"] = (
                        interruption_text
                    )

                goal_type_for_interruption: AgentGoalType = "IDLE"
                goal_details_for_interruption: Dict[str, Any] = {}
                if interruption_type == "objection":
                    goal_type_for_interruption = "HANDLING_OBJECTION"
                    goal_details_for_interruption = {
                        "objection_text": interruption_text
                    }
                elif interruption_type in ["direct_question", "vague_statement"]:
                    goal_type_for_interruption = "CLARIFYING_USER_INPUT"
                    goal_details_for_interruption = {"text": interruption_text}
                elif interruption_type == "off_topic_comment":
                    goal_type_for_interruption = "ACKNOWLEDGE_AND_TRANSITION"
                    goal_details_for_interruption = {"reason": "Handling off-topic"}

                planned_goal = AgentGoal(
                    goal_type=goal_type_for_interruption,
                    previous_goal_if_interrupted=current_goal,
                    goal_details=goal_details_for_interruption,
                )
                updated_interruptions_queue.pop(resolved_interruption_index)
                interruption_handled = True
                logger.debug(
                    f"[{node_name}] Interruption handled. Planned action: {planned_action_command}. Temp Goal: {planned_goal['goal_type']}"
                )
            else:
                logger.warning(
                    f"[{node_name}] No action for interruption type: {interruption_type}. Removing."
                )
                updated_interruptions_queue.pop(resolved_interruption_index)

    if not interruption_handled:
        goal_to_plan_for = current_goal
        if current_goal.get("previous_goal_if_interrupted"):
            resumed_goal = current_goal["previous_goal_if_interrupted"]
            logger.info(
                f"[{node_name}] Resuming previous goal: {resumed_goal.get('goal_type')}"
            )
            goal_to_plan_for = resumed_goal
            goal_to_plan_for["previous_goal_if_interrupted"] = None
            planned_goal = goal_to_plan_for

        current_goal_type = goal_to_plan_for.get("goal_type", "IDLE")
        if planned_goal.get("goal_details") is None:  # Garantir que goal_details exista
            planned_goal["goal_details"] = {}

        logger.debug(
            f"[{node_name}] Planning action for goal type: {current_goal_type}, details: {planned_goal.get('goal_details')}"
        )

        if current_goal_type == "IDLE" or current_goal_type == "GREETING":
            planned_goal["goal_type"] = "INVESTIGATING_NEEDS"
            planned_action_command = "ASK_SPIN_QUESTION"
            planned_action_parameters["spin_type"] = "Situation"
            planned_goal["goal_details"] = {
                "spin_questions_asked_this_cycle": 0,
                "last_spin_type_asked": None,
            }
            logger.debug(
                f"[{node_name}] Transitioning to INVESTIGATING_NEEDS. Action: Ask Situation question."
            )

        elif current_goal_type == "INVESTIGATING_NEEDS":
            spin_questions_asked = planned_goal["goal_details"].get(
                "spin_questions_asked_this_cycle", 0
            )
            last_spin_type_asked_from_goal = planned_goal["goal_details"].get(
                "last_spin_type_asked"
            )
            last_spin_type_for_next: Optional[SpinQuestionType] = None

            if last_spin_type_asked_from_goal is not None:
                last_spin_type_for_next = last_spin_type_asked_from_goal
            elif (
                last_agent_action
                and last_agent_action.get("action_type") == "ASK_SPIN_QUESTION"
            ):
                last_spin_type_for_next = last_agent_action.get("details", {}).get(
                    "spin_type"
                )

            # Critérios de Saída do SPIN
            confirmed_needs = [
                need
                for need in customer_profile.get("identified_needs", [])
                if need.get("status") == "confirmed_by_user"
            ]
            high_priority_need_after_needpayoff = False
            if last_spin_type_for_next == "NeedPayoff":
                for need_entry in customer_profile.get("identified_needs", []):
                    if need_entry.get("status") == "active":
                        priority = need_entry.get("priority")  # Pode ser None
                        if (
                            priority is not None and priority >= 7
                        ):  # Checar se não é None ANTES de comparar
                            high_priority_need_after_needpayoff = True
                            break

            should_exit_spin = False
            exit_reason = ""
            if confirmed_needs and last_spin_type_for_next == "NeedPayoff":
                should_exit_spin = True
                exit_reason = f"Confirmed need(s) found after NeedPayoff: {[n.get('text','N/A') for n in confirmed_needs]}"
            elif high_priority_need_after_needpayoff:
                should_exit_spin = True
                exit_reason = "High priority need identified after NeedPayoff."
            elif spin_questions_asked >= MAX_SPIN_QUESTIONS_PER_CYCLE:
                should_exit_spin = True
                exit_reason = "Max SPIN questions reached."

            if should_exit_spin:
                logger.info(
                    f"[{node_name}] Transitioning from SPIN. Reason: {exit_reason}"
                )
                planned_goal["goal_type"] = "PRESENTING_SOLUTION"

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
                planned_goal["goal_details"] = {
                    "presenting_product": product_to_present,
                    "main_benefit_focus": key_benefit,
                }
            else:  # Continuar SPIN
                next_spin_type = _get_next_spin_type(last_spin_type_for_next)
                planned_action_command = "ASK_SPIN_QUESTION"
                planned_action_parameters["spin_type"] = next_spin_type
                planned_goal["goal_details"].update(
                    {
                        "spin_questions_asked_this_cycle": spin_questions_asked + 1,
                        "last_spin_type_asked": next_spin_type,
                    }
                )
                logger.debug(
                    f"[{node_name}] Continuing INVESTIGATING_NEEDS. Action: Ask {next_spin_type} question. (Asked: {spin_questions_asked + 1})"
                )

        elif current_goal_type == "PRESENTING_SOLUTION":
            logger.info(
                f"[{node_name}] Was presenting solution or awaiting feedback. No new proactive action planned by agent this turn."
            )
            planned_action_command = None  # Esperar resposta do usuário
            # Manter o goal como PRESENTING_SOLUTION ou AWAITING_FEEDBACK...

        elif current_goal_type == "HANDLING_OBJECTION":
            logger.info(
                f"[{node_name}] Was handling objection, now waiting for user response. No action planned."
            )
            planned_action_command = None

        elif current_goal_type == "CLARIFYING_USER_INPUT":
            logger.info(
                f"[{node_name}] Was clarifying user input, now waiting for user response. No action planned."
            )
            planned_action_command = None

        # TODO: Adicionar lógica para BUILDING_CERTAINTY, ATTEMPTING_CLOSE, etc.
        else:
            logger.warning(
                f"[{node_name}] No specific action logic for goal: {current_goal_type}. No action planned."
            )
            planned_action_command = None
            # planned_goal['goal_type'] = "IDLE" # Opcional: voltar para IDLE

    # --- Preparar o Delta de Atualização do Estado ---
    updated_state_delta: Dict[str, Any] = {}
    updated_state_delta["current_agent_goal"] = planned_goal
    if updated_interruptions_queue != state.get(
        "user_interruptions_queue", []
    ):  # Só atualiza se mudou
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
        logger.info(f"[{node_name}] No specific action planned for this turn.")
    updated_state_delta["last_processing_error"] = None

    logger.info(
        f"[{node_name}] Planner finished. Next Goal: {planned_goal.get('goal_type')}"
    )
    return updated_state_delta
