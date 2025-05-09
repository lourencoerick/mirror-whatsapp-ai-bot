# backend/app/services/ai_reply/new_agent/components/proactive_step_decider_node.py

from typing import Dict, Any, Optional, List
from loguru import logger
import json
import time  # Para current_datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

# Schemas e Definições de Estado
from ..state_definition import (
    RichConversationState,
    AgentGoal,
)

from .planner import MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION, MAX_SPIN_QUESTIONS_PER_CYCLE
from ..schemas.proactive_step_output import ProactiveStepDecision

# Helpers
try:
    # Tentativa de importar a função auxiliar do input_processor
    from .input_processor import _format_recent_chat_history, _call_structured_llm

    logger.info("Successfully imported helper functions from input_processor.")
except ImportError:
    logger.error(
        "Failed to import helper functions from input_processor. Using fallbacks."
    )

    # Fallbacks simples para permitir que o arquivo seja analisado, mas os testes/execução falharão.
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
            """Você é um Estrategista de Vendas IA Sênior e Proativo. Sua tarefa é analisar o ESTADO ATUAL DA CONVERSA e determinar a PRÓXIMA MELHOR AÇÃO PROATIVA que o agente de vendas deve tomar para manter a conversa engajada, produtiva e guiá-la em direção a um resultado positivo (venda, qualificação, etc.). A conversa parece ter estagnado ou o usuário deu uma resposta mínima, então uma iniciativa é necessária.

**ESTADO ATUAL DA CONVERSA (Contexto para sua decisão):**

1.  **Turno Atual da Conversa:** {current_turn_number}
2.  **Goal Atual do Agente (Goal que o Planner principal definiu antes de decidir por esta iniciativa):**
    - Tipo: {current_goal_type_before_initiative}
    - Detalhes do Goal: {current_goal_details_before_initiative_json}

3.  **Última Ação Realizada pelo Agente (no turno anterior):**
    - Tipo: {last_agent_action_type}
    - Detalhes da Ação: {last_agent_action_details_json}
    - Texto Gerado pelo Agente: "{last_agent_action_text}"

4.  **Última Mensagem do Usuário (que levou a esta necessidade de iniciativa):**
    - Texto: "{last_user_message_text}"
    - Intenção Discernida (pelo InputProcessor): {last_discerned_intent}
    - Análise da Resposta à Ação do Agente (pelo InputProcessor): {user_response_to_agent_action_analysis}

5.  **Fila de Interrupções Pendentes do Usuário (o Planner principal já as considerou; geralmente vazia aqui):**
    {interruptions_queue_formatted}

6.  **Perfil Dinâmico do Cliente (Resumido):**
    - Objeções Ativas: {active_objections_summary}
    - Objeções Resolvidas Recentemente: {resolved_objections_summary}
    - Necessidades Confirmadas: {confirmed_needs_summary}
    - Status do Processo de Fechamento: {closing_process_status}

7.  **Histórico Recente da Conversa (últimas ~5 trocas):**
    {chat_history}

8.  **Data e Hora Atuais:** {current_datetime}

**SUA TAREFA:**

Com base no contexto acima, decida qual `AgentActionType` e `AgentActionDetails` (parâmetros) o agente deve executar proativamente.

**Diretrizes para Decisão:**

*   **Objetivo Principal:** Manter o engajamento e progredir a conversa. Se o usuário deu uma resposta mínima (ex: "ok", "entendi") ou a conversa pausou, sua ação deve reengajar e guiar.
*   **Relevância do Goal:** Sua ação proativa deve, idealmente, ajudar a progredir o `{current_goal_type_before_initiative}` ou transicionar para um novo goal lógico se o atual estiver bloqueado ou concluído.
*   **Exemplos de Iniciativas (NÃO se limite a estes, seja criativo e estratégico):**
    *   Se o goal era `INVESTIGATING_NEEDS` e o ciclo SPIN não está completo (perguntas < {MAX_SPIN_QUESTIONS_PER_CYCLE}): Sugira a próxima pergunta SPIN (`ASK_SPIN_QUESTION` com o `spin_type` apropriado, ex: se `last_spin_type_asked` foi 'Problem', sugira 'Implication').
    *   Se uma solução foi apresentada (`PRESENTING_SOLUTION`) e o usuário está hesitante/silencioso/respondeu minimamente: Faça uma pergunta para descobrir a causa da hesitação (`ASK_CLARIFYING_QUESTION` focada na proposta) ou reforce um benefício chave e verifique o interesse (`PRESENT_SOLUTION_OFFER` com foco específico, talvez um benefício diferente).
    *   Se uma objeção foi recentemente resolvida (ver `resolved_objections_summary`) e o goal anterior era `ATTEMPTING_CLOSE`: Sugira retomar o fechamento (ex: `CONFIRM_ORDER_DETAILS` se `closing_process_status` era `attempt_made`).
    *   Se o cliente parece pronto (necessidades confirmadas, objeções resolvidas) e o fechamento não foi iniciado: Considere `INITIATE_CLOSING`.
    *   Se o usuário está silencioso por muito tempo (assuma que esta chamada é devido a um timeout se `last_user_message_text` for antigo ou "N/A" e `user_response_to_agent_action_analysis` indicar ausência de resposta): Envie uma mensagem de reengajamento (pode ser um `ASK_CLARIFYING_QUESTION` genérico como "Olá, {company_name} aqui. Você gostaria de continuar nossa conversa?" ou "Precisa de mais um momento para pensar sobre [último tópico]?").
*   **Evite Repetição Imediata:** Não sugira EXATAMENTE a mesma ação que o `last_agent_action_type` se a resposta do usuário foi apenas um "ok". Tente uma variação ou um próximo passo lógico.
*   **Se Nenhuma Ação Proativa Clara:** Se, após analisar tudo, nenhuma ação proativa parecer genuinamente útil ou apropriada (ex: o usuário pediu explicitamente para encerrar, ou a conversa está realmente num impasse intransponível), retorne `null` para `proactive_action_command`.

**FORMATO DE SAÍDA ESPERADO (JSON - Schema `ProactiveStepDecision`):**
Você DEVE responder APENAS com um objeto JSON que corresponda ao schema `ProactiveStepDecision`.
O objeto deve conter:
- `proactive_action_command`: A string do `AgentActionType` (ex: "ASK_SPIN_QUESTION") ou `null`.
- `proactive_action_parameters`: Um objeto com os parâmetros para a ação (ex: {{"spin_type": "NeedPayoff"}}), ou um objeto vazio.
- `justification`: Uma breve explicação da sua escolha (ex: "Usuário respondeu 'ok' à pergunta de Implicação. Próximo passo é NeedPayoff para solidificar o valor.").

Analise o estado e as diretrizes CUIDADOSAMENTE e forneça sua decisão no formato JSON especificado.
""",
        ),
    ]
)


async def proactive_step_decider_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Decides the next proactive step for the agent using an LLM.

    This node is invoked when the main planner determines that the agent
    should take initiative. It uses an LLM to analyze the current conversation
    state and decide on the best proactive action and its parameters.
    The output of this node (next_agent_action_command, action_parameters)
    will then be used by the main graph's `route_action` function.

    Args:
        state: The current RichConversationState.
        config: The graph configuration, expected to contain an LLM instance
                for this decision, ideally under 'llm_strategy_instance',
                or falling back to 'llm_primary_instance'.

    Returns:
        A dictionary with updates for 'next_agent_action_command' and
        'action_parameters' based on the LLM's decision.
        If no proactive action is decided, these will be None/empty.
        The 'current_agent_goal' is NOT modified by this node.
    """
    node_name = "proactive_step_decider_node"
    current_turn = state.get("current_turn_number", 0)
    logger.info(f"--- Starting Node: {node_name} (Turn: {current_turn}) ---")

    llm_strategist = config.get("configurable", {}).get(
        "llm_strategy_instance"
    ) or config.get("configurable", {}).get("llm_primary_instance")

    if not llm_strategist or not callable(
        _call_structured_llm
    ):  # Check if helper is callable
        logger.error(
            f"[{node_name}] No suitable LLM instance or _call_structured_llm helper found."
        )
        return {
            "next_agent_action_command": None,
            "action_parameters": {},
            "last_processing_error": "LLM/helper for proactive step decision unavailable.",
        }

    # --- 1. Formatar o Estado Atual para o Prompt do LLM ---
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
        elif isinstance(analysis_detail, str):
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

    prompt_values = {  # Renamed from prompt_context to prompt_values for clarity with _call_structured_llm
        "current_turn_number": current_turn,
        "current_goal_type_before_initiative": current_goal_before_initiative.get(
            "goal_type"
        ),
        "current_goal_details_before_initiative_json": to_json_safe(
            current_goal_before_initiative.get("goal_details")
        ),
        "last_agent_action_type": (
            last_agent_action.get("action_type", "N/A") if last_agent_action else "N/A"
        ),
        "last_agent_action_details_json": (
            to_json_safe(last_agent_action.get("details"))
            if last_agent_action
            else "{}"
        ),
        "last_agent_action_text": (
            last_agent_action.get("action_generation_text", "N/A")
            if last_agent_action
            else "N/A"
        ),
        "last_user_message_text": state.get(
            "current_user_input_text", "N/A (Possivelmente timeout)"
        ),
        "last_discerned_intent": profile_dynamic.get("last_discerned_intent", "N/A"),
        "user_response_to_agent_action_analysis": user_response_analysis_text,
        "interruptions_queue_formatted": interruptions_formatted,
        "active_objections_summary": (
            to_json_safe(active_objections) if active_objections else "Nenhuma."
        ),
        "resolved_objections_summary": (
            to_json_safe(resolved_objections) if resolved_objections else "Nenhuma."
        ),
        "confirmed_needs_summary": (
            to_json_safe(confirmed_needs) if confirmed_needs else "Nenhuma."
        ),
        "closing_process_status": state.get("closing_process_status", "not_started"),
        "chat_history": _format_recent_chat_history(state.get("messages", [])),
        "current_datetime": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION": MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION,
        "MAX_SPIN_QUESTIONS_PER_CYCLE": MAX_SPIN_QUESTIONS_PER_CYCLE,
        # Adicionar quaisquer outras variáveis que o prompt possa usar
        "company_name": state.get("company_profile", {}).get(
            "company_name", "nossa empresa"
        ),
    }

    # --- 2. Chamar o LLM usando a função helper _call_structured_llm ---
    llm_decision: Optional[ProactiveStepDecision] = await _call_structured_llm(
        llm=llm_strategist,
        prompt_template_str=PROMPT_DETERMINE_PROACTIVE_STEP.messages[
            0
        ].prompt.template,  # Acessa o template string do system message
        prompt_values=prompt_values,
        output_schema=ProactiveStepDecision,
        node_name_for_logging=node_name,
    )

    if llm_decision:
        logger.info(
            f"[{node_name}] LLM proactive decision: {llm_decision.model_dump_json(indent=2)}"
        )
        if llm_decision.justification:
            logger.info(
                f"[{node_name}] LLM Justification: {llm_decision.justification}"
            )
    else:
        logger.warning(
            f"[{node_name}] LLM for proactive step returned None or failed. Defaulting to no action."
        )
        llm_decision = (
            ProactiveStepDecision()
        )  # Garante que temos um objeto com defaults (command=None)

    # --- 3. Preparar o delta do estado ---
    updated_state_delta: Dict[str, Any] = {
        "next_agent_action_command": llm_decision.proactive_action_command,
        "action_parameters": llm_decision.proactive_action_parameters or {},
        "last_processing_error": (
            None
            if llm_decision.proactive_action_command is not None
            else "LLM proactive decider returned no action."
        ),
    }
    # Se o LLM falhou completamente (llm_decision foi None antes do default), o erro já estaria em last_processing_error
    # Se o _call_structured_llm falhou, ele retorna None, e o log já foi feito lá.
    # Aqui, se llm_decision.proactive_action_command for None, é uma decisão válida do LLM de não agir.

    if llm_decision.proactive_action_command:
        logger.info(
            f"[{node_name}] Proactive action decided: {llm_decision.proactive_action_command} with params {llm_decision.proactive_action_parameters}"
        )
    else:
        logger.info(
            f"[{node_name}] LLM decided no proactive action is appropriate at this time. Agent will wait or end turn."
        )
        # Se o LLM explicitamente não retorna ação, não é um erro de processamento, mas uma decisão.
        # Poderíamos limpar o last_processing_error se a chamada LLM foi bem-sucedida mas não retornou ação.
        if state.get(
            "last_processing_error"
        ) and "LLM proactive decider returned no action." not in state.get(
            "last_processing_error", ""
        ):
            updated_state_delta["last_processing_error"] = None

    return updated_state_delta
