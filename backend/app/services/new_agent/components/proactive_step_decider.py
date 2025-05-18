# backend/app/services/ai_reply/new_agent/components/proactive_step_decider_node.py

from typing import Dict, Any, Optional, List
from loguru import logger
import json
import time

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from ..state_definition import (
    RichConversationState,
    AgentGoal,
    AgentActionType,
    AgentActionDetails,
    AgentGoalType,  # Added
)
from .planner import MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION, MAX_SPIN_QUESTIONS_PER_CYCLE
from ..schemas.proactive_step_output import ProactiveStepDecision

try:
    from .input_processor import _format_recent_chat_history, _call_structured_llm

    logger.info("Successfully imported helper functions from input_processor.")
except ImportError:
    logger.error(
        "Failed to import helper functions from input_processor. Using fallbacks."
    )

    def _format_recent_chat_history(*args, **kwargs) -> str:
        return "Histórico indisponível (fallback)."

    async def _call_structured_llm(*args, **kwargs) -> Optional[Any]:
        logger.error(
            "_call_structured_llm fallback called. This indicates an import error."
        )
        return None


# --- Prompt para o LLM Decisor de Passo Proativo ---

PROMPT_DETERMINE_PROACTIVE_STEP = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Estrategista de Vendas IA Sênior e Proativo. Sua tarefa é analisar o ESTADO ATUAL DA CONVERSA e determinar a MELHOR INICIATIVA para o agente de vendas.
Você pode:
1.  Comandar uma AÇÃO PROATIVA DIRETA (simples e autocontida).
2.  Sugerir um NOVO GOAL para o Planner principal, se a iniciativa for complexa.

**ESTADO ATUAL DA CONVERSA (Contexto para sua decisão):**
{formatted_state_context}

**SUA TAREFA:**
Com base no contexto acima, decida a melhor iniciativa. Preencha o JSON `ProactiveStepDecision`.

**Diretrizes para Decisão:**

*   **Opção 1: Comandar AÇÃO PROATIVA DIRETA (para ações simples)**
    *   Use `proactive_action_command` e `proactive_action_parameters`.
    *   Deixe `suggested_next_goal_type` e `suggested_next_goal_details` como `null` ou vazios.
    *   **Ações Simples Permitidas para Comando Direto:**
        *   `SEND_FOLLOW_UP_MESSAGE`: Se `trigger_source` == 'follow_up_timeout' E `current_follow_up_attempts` < `max_follow_up_attempts_total`.
            *   Parâmetros: `{{"current_follow_up_attempts": {current_follow_up_attempts}, "max_follow_up_attempts_total": {max_follow_up_attempts_total}, "context_goal_type": "{current_goal_type_before_initiative}", "context_last_agent_message": "{last_agent_action_text}"}}`
            *   Justificativa: "Usuário inativo. Enviando follow-up [N+1] de [M]."
        *   `GENERATE_FAREWELL`:
            *   Se `trigger_source` == 'follow_up_timeout' E `current_follow_up_attempts` >= `max_follow_up_attempts_total`.
                *   Parâmetros: `{{"reason": "Inatividade do usuário após múltiplas tentativas de follow-up."}}`
                *   Justificativa: "Limite de follow-ups atingido."
            *   Se a conversa estagnou e um adeus amigável é a melhor opção.
                *   Parâmetros: `{{"reason": "Conversa estagnada ou sem progresso claro."}}`
                *   Justificativa: "Encerrando proativamente devido à estagnação."
        *   `ASK_CLARIFYING_QUESTION`: Se uma pergunta genérica de reengajamento for apropriada (ex: "Precisa de mais um momento para pensar sobre [último tópico]?").
            *   Parâmetros: `{{"context": "Reengajamento suave"}}` (O ResponseGenerator usará isso).
            *   Justificativa: "Tentando reengajar o usuário com uma pergunta aberta."

*   **Opção 2: Sugerir NOVO GOAL para o Planner (para iniciativas complexas)**
    *   Use `suggested_next_goal_type` e `suggested_next_goal_details`.
    *   Deixe `proactive_action_command` e `proactive_action_parameters` como `null` ou vazios.
    *   **Quando Usar:** Se a melhor iniciativa envolve lógica que o Planner principal já possui (ex: seleção de produto, gerenciamento de ciclo SPIN, início de fechamento complexo).
    *   **Exemplos de Goals a Sugerir (NÃO se limite a estes, seja estratégico):**
        *   `INVESTIGATING_NEEDS`: Se a conversa estagnou e mais investigação de necessidades é necessária.
            *   `suggested_next_goal_details`: `{{"spin_questions_asked_this_cycle": 0, "last_spin_type_asked": null, "spin_type_to_ask_next": "Situation"}}` (ou o próximo tipo SPIN lógico).
            *   Justificativa: "Retomando investigação de necessidades para reengajar e descobrir mais."
        *   `PRESENTING_SOLUTION`: Se o cliente parece pronto para uma solução, mas não pediu explicitamente.
            *   `suggested_next_goal_details`: `{}` (O Planner selecionará o produto/benefício).
            *   Justificativa: "Proativamente movendo para apresentação de solução com base no contexto."
        *   `ATTEMPTING_CLOSE`: Se o cliente deu sinais de compra sutis e o fechamento não foi tentado.
            *   `suggested_next_goal_details`: `{{"closing_step": "initial_attempt"}}`
            *   Justificativa: "Sinais de compra detectados, sugerindo tentativa de fechamento."
        *   `IDLE` ou `GREETING`: Se a conversa precisa ser completamente reiniciada de forma amigável (raro).
            *   `suggested_next_goal_details`: `{}`
            *   Justificativa: "Sugerindo um reinício suave da conversa."

*   **Justificativa (OBRIGATÓRIO):** Forneça uma `justification` clara para sua escolha (seja ação direta ou sugestão de goal).

*   **Se Nenhuma Iniciativa Apropriada:** Se nenhuma ação direta ou sugestão de goal parecer útil, retorne `proactive_action_command: null` e `suggested_next_goal_type: null`, com uma justificativa explicando o porquê (ex: "Usuário pediu explicitamente para encerrar, nenhuma iniciativa necessária.").

**FORMATO DE SAÍDA ESPERADO (JSON - Schema `ProactiveStepDecision`):**
Responda APENAS com um objeto JSON que corresponda ao schema `ProactiveStepDecision`.
""",
        ),
    ]
)


def _format_state_for_proactive_prompt(state: RichConversationState) -> str:
    """Formats relevant parts of the state for the proactive decider prompt."""
    current_turn = state.get("current_turn_number", 0)
    current_goal_before_initiative = state.get(
        "current_agent_goal",
        AgentGoal(goal_type="IDLE", goal_details={}, previous_goal_if_interrupted=None),
    )
    last_agent_action = state.get("last_agent_action")
    user_analysis_dict = state.get("user_input_analysis_result")
    user_response_analysis_text = "N/A (Possivelmente timeout ou sem análise recente)"

    if user_analysis_dict and isinstance(user_analysis_dict, dict):
        analysis_detail = user_analysis_dict.get("analysis_of_response_to_agent_action")
        if analysis_detail and isinstance(analysis_detail, dict):
            user_response_analysis_text = analysis_detail.get(
                "user_response_to_agent_action", "Não analisado"
            )
        elif isinstance(analysis_detail, str):  # Should be a dict by now
            user_response_analysis_text = analysis_detail

    def to_json_safe(data: Any, indent: Optional[int] = None) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, indent=indent)
        except TypeError:
            return str(data)

    interruptions_queue = state.get("user_interruptions_queue", [])
    interruptions_formatted = (
        "\n".join(
            [
                f"- Tipo: {inter.get('type')}, Texto: '{inter.get('text')}', Status: {inter.get('status')}"
                for inter in interruptions_queue
            ]
        )
        if interruptions_queue
        else "Nenhuma interrupção pendente."
    )

    profile_dynamic = state.get("customer_profile_dynamic", {})
    active_objections = [
        o.get("text")
        for o in profile_dynamic.get("identified_objections", [])
        if o.get("status") == "active"
    ]
    resolved_objections = [
        o.get("text")
        for o in profile_dynamic.get("identified_objections", [])
        if o.get("status") == "resolved"
    ]
    confirmed_needs = [
        n.get("text")
        for n in profile_dynamic.get("identified_needs", [])
        if n.get("status") == "confirmed_by_user"
    ]

    action_params_from_planner = state.get("action_parameters", {})
    trigger_source = action_params_from_planner.get(
        "trigger_source", "user_response_or_stagnation"
    )
    current_follow_up_attempts = action_params_from_planner.get(
        "current_follow_up_attempts", 0
    )

    agent_config_dict = (
        state.get("agent_config") if isinstance(state.get("agent_config"), dict) else {}
    )
    max_follow_up_attempts_total = agent_config_dict.get("max_follow_up_attempts", 3)

    # Constructing the context string
    context_lines = [
        f"1.  **Gatilho para esta Decisão Proativa:** '{trigger_source}'",
        f"    - (Se 'follow_up_timeout': Tentativa Atual: {current_follow_up_attempts}, Máximo Permitido: {max_follow_up_attempts_total})",
        f"2.  **Turno Atual da Conversa:** {current_turn}",
        f"3.  **Goal Atual do Agente (Antes da Iniciativa):**",
        f"    - Tipo: {current_goal_before_initiative.get('goal_type')}",
        f"    - Detalhes: {to_json_safe(current_goal_before_initiative.get('goal_details'))}",
        f"4.  **Última Ação Realizada pelo Agente:**",
        f"    - Tipo: {last_agent_action.get('action_type', 'N/A') if last_agent_action else 'N/A'}",
        f"    - Detalhes: {to_json_safe(last_agent_action.get('details')) if last_agent_action else '{}'}",
        f"    - Texto Gerado: \"{last_agent_action.get('action_generation_text', 'N/A') if last_agent_action else 'N/A'}\"",
        f"5.  **Última Mensagem do Usuário:**",
        f"    - Texto: \"{state.get('current_user_input_text', 'N/A (Possivelmente timeout)')}\"",
        f"    - Intenção Discernida: {profile_dynamic.get('last_discerned_intent', 'N/A')}",
        f"    - Análise da Resposta à Ação do Agente: {user_response_analysis_text}",
        f"6.  **Fila de Interrupções Pendentes:** {interruptions_formatted}",
        f"7.  **Perfil Dinâmico do Cliente (Resumido):**",
        f"    - Objeções Ativas: {to_json_safe(active_objections) if active_objections else 'Nenhuma.'}",
        f"    - Objeções Resolvidas: {to_json_safe(resolved_objections) if resolved_objections else 'Nenhuma.'}",
        f"    - Necessidades Confirmadas: {to_json_safe(confirmed_needs) if confirmed_needs else 'Nenhuma.'}",
        f"    - Status do Processo de Fechamento: {state.get('closing_process_status', 'not_started')}",
        f"8.  **Histórico Recente da Conversa:**\n    {_format_recent_chat_history(state.get('messages', []))}",
        f"9.  **Data e Hora Atuais:** {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"10. **Constantes de Referência (para sua informação):**",
        f"    - MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION: {MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION}",
        f"    - MAX_SPIN_QUESTIONS_PER_CYCLE: {MAX_SPIN_QUESTIONS_PER_CYCLE}",
        f"    - Nome da Empresa: {state.get('company_profile', {}).get('company_name', 'nossa empresa')}",
    ]
    return "\n".join(context_lines)


async def proactive_step_decider_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Decides the next proactive step or suggests a new goal using an LLM.
    """
    node_name = "proactive_step_decider_node"
    current_turn = state.get("current_turn_number", 0)
    logger.info(f"--- Starting Node: {node_name} (Turn: {current_turn}) ---")

    llm_strategist = config.get("configurable", {}).get(
        "llm_strategy_instance"
    ) or config.get("configurable", {}).get("llm_primary_instance")

    if not llm_strategist or not callable(_call_structured_llm):
        logger.error(f"[{node_name}] No suitable LLM or _call_structured_llm helper.")
        return {
            "next_agent_action_command": None,
            "action_parameters": {},
            "suggested_goal_type": None,
            "suggested_goal_details": {},
            "last_processing_error": "LLM/helper for proactive step decision unavailable.",
        }

    formatted_state_context = _format_state_for_proactive_prompt(state)
    action_params_from_planner = state.get(
        "action_parameters", {}
    )  # For follow-up context
    current_goal_before_initiative = state.get(
        "current_agent_goal",
        AgentGoal(goal_type="IDLE", goal_details={}, previous_goal_if_interrupted=None),
    )
    last_agent_action = state.get("last_agent_action")

    prompt_values = {
        "formatted_state_context": formatted_state_context,
        # Pass individual values needed by the prompt template string directly if they are used in the main system message
        "trigger_source": action_params_from_planner.get(
            "trigger_source", "user_response_or_stagnation"
        ),
        "current_follow_up_attempts": action_params_from_planner.get(
            "current_follow_up_attempts", 0
        ),
        "max_follow_up_attempts_total": state.get("agent_config", {}).get(
            "max_follow_up_attempts", 3
        ),
        "current_goal_type_before_initiative": current_goal_before_initiative.get(
            "goal_type"
        ),
        "last_agent_action_text": (
            last_agent_action.get("action_generation_text", "N/A")
            if last_agent_action
            else "N/A"
        ),
    }

    llm_decision: Optional[ProactiveStepDecision] = await _call_structured_llm(
        llm=llm_strategist,
        prompt_template_str=PROMPT_DETERMINE_PROACTIVE_STEP.messages[0].prompt.template,
        prompt_values=prompt_values,
        output_schema=ProactiveStepDecision,
        node_name_for_logging=node_name,
    )

    updated_state_delta: Dict[str, Any] = {
        "next_agent_action_command": None,
        "action_parameters": {},
        "suggested_goal_type": None,
        "suggested_goal_details": {},
        "last_processing_error": None,
    }

    if llm_decision:
        logger.info(
            f"[{node_name}] LLM proactive decision: {llm_decision.model_dump_json(indent=2)}"
        )
        logger.info(f"[{node_name}] LLM Justification: {llm_decision.justification}")

        if llm_decision.proactive_action_command:
            logger.info(
                f"[{node_name}] LLM decided on DIRECT ACTION: {llm_decision.proactive_action_command}"
            )
            updated_state_delta["next_agent_action_command"] = (
                llm_decision.proactive_action_command
            )
            updated_state_delta["action_parameters"] = (
                llm_decision.proactive_action_parameters or {}
            )
            # Ensure follow-up context is passed if the action is SEND_FOLLOW_UP_MESSAGE
            if llm_decision.proactive_action_command == "SEND_FOLLOW_UP_MESSAGE":
                updated_state_delta["action_parameters"][
                    "current_follow_up_attempts"
                ] = prompt_values["current_follow_up_attempts"]
                updated_state_delta["action_parameters"][
                    "max_follow_up_attempts_total"
                ] = prompt_values["max_follow_up_attempts_total"]

        elif llm_decision.suggested_next_goal_type:
            logger.info(
                f"[{node_name}] LLM decided on SUGGESTED GOAL: {llm_decision.suggested_next_goal_type}"
            )
            updated_state_delta["next_agent_action_command"] = (
                "REPLAN_WITH_SUGGESTED_GOAL"
            )
            updated_state_delta["suggested_goal_type"] = (
                llm_decision.suggested_next_goal_type
            )
            updated_state_delta["suggested_goal_details"] = (
                llm_decision.suggested_next_goal_details or {}
            )
            # Action parameters might be empty or minimal here, planner will fill them
            updated_state_delta["action_parameters"] = {}
        else:
            logger.info(
                f"[{node_name}] LLM decided no proactive action or goal suggestion is appropriate."
            )
            # No action, no goal suggestion. Planner will likely end the turn.
            updated_state_delta["last_processing_error"] = (
                None  # Not an error, a valid decisions
            )
    else:
        logger.warning(
            f"[{node_name}] LLM for proactive step returned None or failed. Defaulting to no action/suggestion."
        )
        updated_state_delta["last_processing_error"] = (
            "LLM proactive step decision failed or was unparsable."
        )

    return updated_state_delta
