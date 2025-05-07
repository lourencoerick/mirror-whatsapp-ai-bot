# backend/app/services/ai_reply/new_agent/components/planner.py

from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
import copy

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
    IdentifiedObjectionEntry,  # Adicionado
)

# Adicionar novos tipos de ação se forem necessários
# from ..state_definition import ...

INTERRUPTION_TO_ACTION_MAP: Dict[str, AgentActionType] = {
    "direct_question": "ANSWER_DIRECT_QUESTION",
    "objection": "GENERATE_REBUTTAL",
    "vague_statement": "ASK_CLARIFYING_QUESTION",
    "off_topic_comment": "ACKNOWLEDGE_AND_TRANSITION",
}
MAX_SPIN_QUESTIONS_PER_CYCLE = 5
MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION = 2  # Novo limite


def _get_next_spin_type(last_spin_type: Optional[SpinQuestionType]) -> SpinQuestionType:
    # ... (como antes) ...
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
    customer_profile: Dict[str, Any], company_profile_offerings: List[Dict[str, Any]]
) -> Tuple[str, str]:
    # ... (como antes, usando .get() para customer_profile) ...
    product_to_present = "Nossa Solução Principal"
    key_benefit = "atender às suas necessidades gerais"
    identified_needs: List[IdentifiedNeedEntry] = customer_profile.get(
        "identified_needs", []
    )
    target_need: Optional[IdentifiedNeedEntry] = None
    confirmed_needs = [
        n for n in identified_needs if n.get("status") == "confirmed_by_user"
    ]
    if confirmed_needs:
        confirmed_needs.sort(
            key=lambda x: (x.get("priority", 0), x.get("source_turn", 0)), reverse=True
        )
        target_need = confirmed_needs[0]
    elif identified_needs:
        active_needs = [n for n in identified_needs if n.get("status") == "active"]
        active_needs.sort(
            key=lambda x: (x.get("priority", 0), x.get("source_turn", 0)), reverse=True
        )
        if active_needs:
            target_need = active_needs[0]
    if target_need:
        target_need_text = target_need.get("text", "sua necessidade principal")
        key_benefit = f"o seu desafio em relação a '{target_need_text}'"
        if company_profile_offerings:
            for offering in company_profile_offerings:
                offering_name = offering.get("name", "").lower()
                offering_desc = offering.get("short_description", "").lower()
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
            else:
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
    customer_profile = copy.deepcopy(state.get("customer_profile_dynamic", {}))
    last_agent_action = copy.deepcopy(state.get("last_agent_action"))
    company_profile = state.get("company_profile", {})

    # Obter o resultado da análise do input do turno anterior (que o StateUpdater já processou)
    # O user_input_analysis_result no estado é o do turno ATUAL, antes do StateUpdater rodar para este turno.
    # Para decisões pós-apresentação/pós-rebuttal, precisamos da análise da RESPOSTA do cliente
    # a essas ações. Essa análise já terá sido feita pelo InputProcessor e usada pelo StateUpdater
    # para atualizar, por exemplo, o status das objeções ou adicionar novas interrupções.
    # Portanto, o Planner age sobre o ESTADO ATUALIZADO.

    planned_goal: AgentGoal = current_goal
    planned_action_command: Optional[AgentActionType] = None
    planned_action_parameters: AgentActionDetails = {}
    updated_interruptions_queue = list(interruptions_queue)

    interruption_handled = False
    if updated_interruptions_queue:
        # ... (lógica de tratamento de interrupções como antes) ...
        # (Se uma interrupção é tratada, interruption_handled = True)
        interruption_to_handle = None
        resolved_interruption_index = -1
        for i, interruption in enumerate(updated_interruptions_queue):
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
                        "objection_text": interruption_text,
                        "original_objection_text": interruption_text,
                    }  # Guardar texto original
                elif interruption_type in ["direct_question", "vague_statement"]:
                    goal_type_for_interruption = "CLARIFYING_USER_INPUT"
                    goal_details_for_interruption = {"text": interruption_text}
                elif interruption_type == "off_topic_comment":
                    goal_type_for_interruption = "ACKNOWLEDGE_AND_TRANSITION"
                    goal_details_for_interruption = {"reason": "Handling off-topic"}

                planned_goal = AgentGoal(
                    goal_type=goal_type_for_interruption,
                    previous_goal_if_interrupted=(
                        current_goal
                        if current_goal.get("goal_type") != goal_type_for_interruption
                        else current_goal.get("previous_goal_if_interrupted")
                    ),  # Evitar aninhar o mesmo goal
                    goal_details=goal_details_for_interruption,
                )
                updated_interruptions_queue.pop(resolved_interruption_index)
                interruption_handled = True
            else:  # Interrupção não mapeada
                logger.warning(
                    f"[{node_name}] No action for interruption type: {interruption_type}. Removing."
                )
                updated_interruptions_queue.pop(resolved_interruption_index)

    if not interruption_handled:
        goal_to_plan_for = current_goal
        if current_goal.get("previous_goal_if_interrupted"):
            # ... (lógica de retomada como antes, planned_goal é atualizado) ...
            resumed_goal = current_goal["previous_goal_if_interrupted"]
            logger.info(
                f"[{node_name}] Resuming previous goal: {resumed_goal.get('goal_type')}"
            )
            goal_to_plan_for = resumed_goal
            goal_to_plan_for["previous_goal_if_interrupted"] = None
            planned_goal = goal_to_plan_for

        current_goal_type = goal_to_plan_for.get("goal_type", "IDLE")
        if planned_goal.get("goal_details") is None:
            planned_goal["goal_details"] = {}

        logger.debug(
            f"[{node_name}] Planning action for goal type: {current_goal_type}, details: {planned_goal.get('goal_details')}"
        )

        if current_goal_type == "IDLE" or current_goal_type == "GREETING":
            # ... (como antes) ...
            planned_goal["goal_type"] = "INVESTIGATING_NEEDS"
            planned_action_command = "ASK_SPIN_QUESTION"
            planned_action_parameters["spin_type"] = "Situation"
            planned_goal["goal_details"] = {
                "spin_questions_asked_this_cycle": 0,
                "last_spin_type_asked": None,
            }

        elif current_goal_type == "INVESTIGATING_NEEDS":
            # ... (lógica SPIN e transição para PRESENTING_SOLUTION como antes) ...
            # (Assume que _select_product_and_benefit_for_presentation é chamada aqui)
            # (E planned_goal, planned_action_command, planned_action_parameters são definidos)
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

            confirmed_needs = [
                n
                for n in customer_profile.get("identified_needs", [])
                if n.get("status") == "confirmed_by_user"
            ]
            high_priority_need_after_needpayoff = False
            if last_spin_type_for_next == "NeedPayoff":
                for need_entry in customer_profile.get("identified_needs", []):
                    if need_entry.get("status") == "active":
                        priority = need_entry.get("priority")
                        if priority is not None and priority >= 7:
                            high_priority_need_after_needpayoff = True
                            break

            should_exit_spin, exit_reason = False, ""
            if confirmed_needs and last_spin_type_for_next == "NeedPayoff":
                should_exit_spin, exit_reason = (
                    True,
                    f"Confirmed need(s) after NeedPayoff: {[n.get('text','N/A') for n in confirmed_needs]}",
                )
            elif high_priority_need_after_needpayoff:
                should_exit_spin, exit_reason = (
                    True,
                    "High priority need after NeedPayoff.",
                )
            elif spin_questions_asked >= MAX_SPIN_QUESTIONS_PER_CYCLE:
                should_exit_spin, exit_reason = True, "Max SPIN questions reached."

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
            else:
                next_spin_type = _get_next_spin_type(last_spin_type_for_next)
                planned_action_command = "ASK_SPIN_QUESTION"
                planned_action_parameters["spin_type"] = next_spin_type
                planned_goal["goal_details"].update(
                    {
                        "spin_questions_asked_this_cycle": spin_questions_asked + 1,
                        "last_spin_type_asked": next_spin_type,
                    }
                )

        elif current_goal_type == "PRESENTING_SOLUTION":
            logger.info(
                f"[{node_name}] Goal is PRESENTING_SOLUTION. Analyzing context."
            )

            # A ação primária após apresentar é ESPERAR a reação do cliente.
            # O Planner só deve agir neste estado se:
            # 1. Uma interrupção clara (pergunta/objeção) foi detectada (tratada no início).
            # 2. O InputProcessor/StateUpdater detectaram um SINAL DE COMPRA explícito.

            # Verificar se a última ação foi apresentar. Se sim, esperar.
            if (
                last_agent_action
                and last_agent_action.get("action_type") == "PRESENT_SOLUTION_OFFER"
            ):
                logger.info(
                    f"[{node_name}] Agent just presented solution. Waiting for user response."
                )
                planned_action_command = None
            else:
                # Se a última ação NÃO foi apresentar (ex: respondemos pergunta sobre a solução),
                # E NÃO há interrupções pendentes, podemos considerar o próximo passo.
                # O próximo passo IDEALMENTE seria baseado em um sinal de compra.

                # --- LÓGICA DE TRANSIÇÃO PARA FECHAMENTO (REQUER SINAL) ---
                # Exemplo: Verificar um campo que o StateUpdater preencheu
                # com base na análise do InputProcessor.
                # (Esta parte depende de termos essa análise implementada)

                # Placeholder para detecção de sinal de compra:
                user_showed_strong_buying_signal = False
                # Exemplo de como poderia ser:
                # last_analysis = state.get("user_input_analysis_result_processed") # Um campo hipotético
                # if last_analysis and last_analysis.get("overall_intent") == "RequestForNextStepInPurchase":
                #     user_showed_strong_buying_signal = True

                if user_showed_strong_buying_signal:
                    logger.info(
                        f"[{node_name}] Strong buying signal detected. Transitioning to ATTEMPTING_CLOSE."
                    )
                    planned_goal["goal_type"] = "ATTEMPTING_CLOSE"
                    planned_action_command = "INITIATE_CLOSING"
                    planned_goal["goal_details"] = {}
                else:
                    # Se não houve sinal de compra explícito e não há interrupções,
                    # o que fazer?
                    # Opção 1: Esperar (mais seguro).
                    # Opção 2: Fazer uma pergunta de acompanhamento/verificação.
                    # Opção 3: Tentar fechar mesmo assim (agressivo - como estava antes).

                    # Vamos escolher ESPERAR por enquanto, é mais seguro.
                    logger.info(
                        f"[{node_name}] In PRESENTING_SOLUTION state, no new interruptions or strong buying signal detected. Waiting."
                    )
                    planned_action_command = None
                    # Manter o goal como PRESENTING_SOLUTION

        elif current_goal_type == "HANDLING_OBJECTION":
            logger.info(
                f"[{node_name}] Goal is HANDLING_OBJECTION. Analyzing user's reaction to rebuttal."
            )
            # A última ação do agente (last_agent_action) deveria ter sido GENERATE_REBUTTAL.
            # O StateUpdater já processou a resposta do usuário a esse rebuttal e atualizou
            # o status da objeção em customer_profile_dynamic.

            objection_details_from_goal = planned_goal.get("goal_details", {})
            # O texto da objeção que estava sendo tratada
            original_objection_text = objection_details_from_goal.get(
                "original_objection_text"
            )

            if not original_objection_text:
                logger.warning(
                    f"[{node_name}] In HANDLING_OBJECTION goal, but no original_objection_text in goal_details. Resuming previous goal if any."
                )
                if planned_goal.get("previous_goal_if_interrupted"):
                    planned_goal = planned_goal["previous_goal_if_interrupted"]
                    planned_goal["previous_goal_if_interrupted"] = None
                else:
                    planned_goal["goal_type"] = "INVESTIGATING_NEEDS"  # Fallback
                planned_action_command = (
                    None  # Deixar o próximo ciclo do planner decidir
                )
            else:
                obj_entry_in_profile: Optional[IdentifiedObjectionEntry] = None
                for obj in customer_profile.get("identified_objections", []):
                    if obj.get("text") == original_objection_text:
                        obj_entry_in_profile = obj
                        break

                if (
                    obj_entry_in_profile
                    and obj_entry_in_profile.get("status") == "resolved"
                ):
                    logger.info(
                        f"[{node_name}] Objection '{original_objection_text[:30]}...' is resolved. Resuming previous goal."
                    )
                    if planned_goal.get("previous_goal_if_interrupted"):
                        planned_goal = planned_goal["previous_goal_if_interrupted"]
                        planned_goal["previous_goal_if_interrupted"] = None
                    else:
                        planned_goal["goal_type"] = "INVESTIGATING_NEEDS"  # Fallback
                    planned_action_command = (
                        None  # Deixar o próximo ciclo do planner decidir
                    )

                elif (
                    obj_entry_in_profile
                    and obj_entry_in_profile.get("status") == "active"
                ):  # Persiste
                    attempts = obj_entry_in_profile.get("rebuttal_attempts", 0)
                    if attempts < MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION:
                        logger.info(
                            f"[{node_name}] Objection '{original_objection_text[:30]}...' persists (attempt {attempts+1}). Planning another rebuttal."
                        )
                        planned_action_command = "GENERATE_REBUTTAL"
                        planned_action_parameters["objection_text_to_address"] = (
                            original_objection_text
                        )
                        # Manter o goal como HANDLING_OBJECTION, goal_details já tem o texto.
                    else:
                        logger.warning(
                            f"[{node_name}] Max rebuttal attempts for objection '{original_objection_text[:30]}...'. Considering impasse."
                        )
                        planned_goal["goal_type"] = (
                            "ENDING_CONVERSATION"  # Ou HANDLE_IMPASSE
                        )
                        planned_goal["goal_details"] = {
                            "reason": f"Impasse on objection: {original_objection_text}"
                        }
                        planned_action_command = "ACKNOWLEDGE_AND_TRANSITION"  # Ou uma ação de impasse específica
                        planned_action_parameters = {
                            "off_topic_text": "Não conseguimos resolver esta objeção.",
                            "previous_goal_topic": "nossos próximos passos",
                        }

                elif (
                    not obj_entry_in_profile
                ):  # Objeção não encontrada no perfil (deveria ter sido marcada como ignored se uma nova surgiu)
                    logger.info(
                        f"[{node_name}] Original objection '{original_objection_text[:30]}...' not found or no longer active. Resuming previous goal."
                    )
                    if planned_goal.get("previous_goal_if_interrupted"):
                        planned_goal = planned_goal["previous_goal_if_interrupted"]
                        planned_goal["previous_goal_if_interrupted"] = None
                    else:
                        planned_goal["goal_type"] = "INVESTIGATING_NEEDS"
                    planned_action_command = None
                else:  # Outro status (addressing, ignored) - esperar
                    logger.info(
                        f"[{node_name}] Objection '{original_objection_text[:30]}...' status is '{obj_entry_in_profile.get('status')}'. Waiting."
                    )
                    planned_action_command = None

        elif current_goal_type == "CLARIFYING_USER_INPUT":
            # Se o objetivo era CLARIFYING e não houve interrupção, significa que
            # a ação de clarificação foi feita. Agora, retomar o objetivo anterior.
            # A lógica de retomada no início deste bloco "if not interruption_handled" já deve ter feito isso.
            # Se, por algum motivo, goal_to_plan_for ainda é CLARIFYING, é um estado inesperado.
            # Ou, se a última ação foi ASK_CLARIFYING_QUESTION, então esperamos a resposta.
            if last_agent_action and last_agent_action.get("action_type") in [
                "ASK_CLARIFYING_QUESTION",
                "ANSWER_DIRECT_QUESTION",
            ]:
                logger.info(
                    f"[{node_name}] Agent just asked/answered for clarification. Waiting for user response."
                )
                planned_action_command = None
            else:  # Estado inesperado, tentar retomar
                logger.warning(
                    f"[{node_name}] In CLARIFYING_USER_INPUT without recent clarifying action. Attempting to resume previous goal."
                )
                if planned_goal.get("previous_goal_if_interrupted"):
                    planned_goal = planned_goal["previous_goal_if_interrupted"]
                    planned_goal["previous_goal_if_interrupted"] = None
                else:
                    planned_goal["goal_type"] = "INVESTIGATING_NEEDS"
                planned_action_command = (
                    None  # Deixar o próximo ciclo do planner decidir
                )

        # Adicionar ATTEMPTING_CLOSE
        elif current_goal_type == "ATTEMPTING_CLOSE":
            # Lógica inicial: se estamos aqui, a primeira ação é INITIATE_CLOSING
            # O Planner do próximo turno analisará a resposta.
            # (Assumindo que o InputProcessor/StateUpdater não mudou o goal se o cliente aceitou)
            closing_status = state.get("closing_process_status", "not_started")

            if (
                closing_status == "not_started"
                or not last_agent_action
                or last_agent_action.get("action_type")
                not in [
                    "INITIATE_CLOSING",
                    "CONFIRM_ORDER_DETAILS",
                    "HANDLE_CLOSING_CORRECTION",
                ]
            ):
                logger.info(f"[{node_name}] Initiating closing process.")
                planned_action_command = "INITIATE_CLOSING"
                # Parâmetros podem vir de active_proposal no estado
                active_proposal = state.get("active_proposal")
                if active_proposal:
                    planned_action_parameters["product_name"] = active_proposal.get(
                        "product_name"
                    )
                    planned_action_parameters["price"] = active_proposal.get("price")
                planned_goal["goal_details"] = {"closing_step": "initial_attempt"}
            else:
                # Se já houve uma ação de fechamento, esperar a resposta do usuário.
                # O InputProcessor/StateUpdater analisarão a resposta e o Planner do próximo turno
                # decidirá se continua com CONFIRM_ORDER_DETAILS, HANDLE_CLOSING_CORRECTION,
                # ou volta para HANDLING_OBJECTION.
                logger.info(
                    f"[{node_name}] In ATTEMPTING_CLOSE, waiting for user response to action: {last_agent_action.get('action_type') if last_agent_action else 'N/A'}"
                )
                planned_action_command = None

        else:  # Fallback para goals não implementados
            logger.warning(
                f"[{node_name}] No specific action logic for goal: {current_goal_type}. No action planned."
            )
            planned_action_command = None
            # planned_goal['goal_type'] = "IDLE" # Opcional

    # --- Preparar o Delta de Atualização do Estado ---
    updated_state_delta: Dict[str, Any] = {}
    updated_state_delta["current_agent_goal"] = planned_goal
    if updated_interruptions_queue != state.get("user_interruptions_queue", []):
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
