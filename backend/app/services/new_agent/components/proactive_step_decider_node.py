# backend/app/services/ai_reply/new_agent/components/proactive_step_decider_node.py

from typing import Dict, Any, Optional
from loguru import logger
import json
import time  # Para current_datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

# Schemas e Definições de Estado
from ..state_definition import (
    RichConversationState,
    AgentGoal,
    AgentActionType,
    AgentActionDetails,
    # Outros tipos necessários para formatar o contexto
)
from ..schemas.proactive_step_output import ProactiveStepDecision

# Helpers (ex: para formatar histórico)
try:
    from .input_processor import _format_recent_chat_history
except ImportError:

    def _format_recent_chat_history(*args, **kwargs) -> str:
        return "Histórico indisponível."


# --- Prompt para o LLM Decisor de Passo Proativo ---

PROMPT_DETERMINE_PROACTIVE_STEP = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Estrategista de Vendas IA Sênior. Sua tarefa é analisar o ESTADO ATUAL DA CONVERSA e determinar a PRÓXIMA MELHOR AÇÃO PROATIVA que o agente de vendas deve tomar para manter a conversa engajada, produtiva e guiá-la em direção a um resultado positivo (venda, qualificação, etc.).

**ESTADO ATUAL DA CONVERSA (Contexto para sua decisão):**

1.  **Turno Atual da Conversa:** {current_turn_number}
2.  **Goal Atual do Agente (Antes de decidir tomar esta iniciativa):**
    - Tipo: {current_goal_type_before_initiative}
    - Detalhes do Goal: {current_goal_details_before_initiative_json}

3.  **Última Ação Realizada pelo Agente:**
    - Tipo: {last_agent_action_type}
    - Detalhes da Ação: {last_agent_action_details_json}
    - Texto Gerado pelo Agente: "{last_agent_action_text}"

4.  **Última Mensagem do Usuário (se houver, e sua análise):**
    - Texto: "{last_user_message_text}"
    - Intenção Discernida: {last_discerned_intent}
    - Análise da Resposta à Ação do Agente: {user_response_to_agent_action_analysis}

5.  **Fila de Interrupções Pendentes do Usuário:**
    {interruptions_queue_formatted}
    (Se vazia, ótimo! Se não, considere se a ação proativa ainda é válida ou se uma interrupção deve ser tratada primeiro pelo Planner principal.)

6.  **Perfil Dinâmico do Cliente (Resumido):**
    - Objeções Ativas: {active_objections_summary}
    - Objeções Resolvidas Recentemente: {resolved_objections_summary}
    - Necessidades Confirmadas: {confirmed_needs_summary}
    - Status do Processo de Fechamento: {closing_process_status}

7.  **Histórico Recente da Conversa:**
    {chat_history}

8.  **Data e Hora Atuais:** {current_datetime}

**SUA TAREFA:**

Com base no contexto acima, decida qual `AgentActionType` e `AgentActionDetails` (parâmetros) o agente deve executar proativamente.

**Diretrizes para Decisão:**

*   **Priorize o Fluxo Natural:** Se o usuário deu um gancho claro (nova pergunta, objeção), o Planner principal provavelmente já tratou disso. Sua função entra quando o fluxo está estagnado ou o usuário deu uma resposta mínima.
*   **Relevância do Goal:** Sua ação proativa deve, idealmente, ajudar a progredir o `{current_goal_type_before_initiative}` ou transicionar para um novo goal lógico.
*   **Exemplos de Iniciativas (NÃO se limite a estes):**
    *   Se o goal era `INVESTIGATING_NEEDS` e o ciclo SPIN não está completo: Sugira a próxima pergunta SPIN (`ASK_SPIN_QUESTION` com o `spin_type` apropriado).
    *   Se uma solução foi apresentada (`PRESENTING_SOLUTION`) e o usuário está hesitante/silencioso: Faça uma pergunta para descobrir a causa da hesitação (`ASK_CLARIFYING_QUESTION`) ou reforce um benefício chave e verifique o interesse (`PRESENT_SOLUTION_OFFER` com foco específico).
    *   Se uma objeção foi recentemente resolvida e o goal anterior era `ATTEMPTING_CLOSE`: Sugira retomar o fechamento (`CONFIRM_ORDER_DETAILS` ou `INITIATE_CLOSING` se apropriado).
    *   Se o cliente parece pronto e necessidades foram atendidas: Considere `INITIATE_CLOSING`.
    *   Se o usuário está silencioso por muito tempo (indicado por um evento de timeout, se aplicável no sistema externo): Envie uma mensagem de reengajamento (pode ser um `ASK_CLARIFYING_QUESTION` genérico como "Ainda está por aí?" ou "Precisa de mais tempo?").
*   **Evite Repetição:** Não sugira uma ação que acabou de ser feita ou uma pergunta que está pendente de resposta.
*   **Se Nenhuma Ação Proativa Clara:** Se, após analisar tudo, nenhuma ação proativa parecer genuinamente útil ou apropriada, retorne `null` para `proactive_action_command`.

**FORMATO DE SAÍDA ESPERADO (JSON - Schema `ProactiveStepDecision`):**
Você DEVE responder com um objeto JSON contendo:
- `proactive_action_command`: A string do `AgentActionType` (ex: "ASK_SPIN_QUESTION") ou `null`.
- `proactive_action_parameters`: Um objeto com os parâmetros para a ação (ex: {{"spin_type": "NeedPayoff"}}), ou um objeto vazio.
- `justification`: (Opcional, mas útil) Uma breve explicação da sua escolha.

Exemplo de Saída:
{{
  "proactive_action_command": "ASK_SPIN_QUESTION",
  "proactive_action_parameters": {{ "spin_type": "NeedPayoff" }},
  "justification": "O goal atual é investigar necessidades, a última pergunta SPIN foi Implication, e o usuário deu uma resposta mínima. A próxima pergunta lógica é NeedPayoff."
}}

Analise o estado e as diretrizes CUIDADOSAMENTE e forneça sua decisão no formato JSON especificado.
Lembre-se, o objetivo é manter a conversa PRODUTIVA e GUIADA pelo agente.
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
    should take initiative rather than waiting for explicit user input.
    It uses an LLM to analyze the current conversation state and decide
    on the best proactive action and its parameters.

    Args:
        state: The current RichConversationState.
        config: The graph configuration, expected to contain an LLM instance
                for this decision under 'llm_strategy_instance' or similar.

    Returns:
        A dictionary with updates for 'next_agent_action_command' and
        'action_parameters' based on the LLM's decision.
        If no proactive action is decided, these will be None/empty.
    """
    node_name = "proactive_step_decider_node"
    current_turn = state.get("current_turn_number", 0)
    logger.info(f"--- Starting Node: {node_name} (Turn: {current_turn}) ---")

    # Prioritize a specific LLM for strategy if available, else use primary
    llm_strategist = config.get("configurable", {}).get(
        "llm_strategy_instance"
    ) or config.get("configurable", {}).get("llm_primary_instance")

    if not llm_strategist:
        logger.error(f"[{node_name}] No suitable LLM instance found in config.")
        return {
            "next_agent_action_command": None,  # Fallback: do nothing
            "action_parameters": {},
            "last_processing_error": "LLM for proactive step decision unavailable.",
        }

    # --- 1. Formatar o Estado Atual para o Prompt do LLM ---
    current_goal_before_initiative = state.get(
        "current_agent_goal",
        AgentGoal(goal_type="IDLE", goal_details={}, previous_goal_if_interrupted=None),
    )
    last_agent_action = state.get("last_agent_action")
    user_analysis = state.get(
        "user_input_analysis_result"
    )  # This should be from the current turn's input processing

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
        else "Nenhuma."
    )

    # Summarize complex profile parts if they get too long for the prompt
    active_objections = [
        o.get("text")
        for o in state.get("customer_profile_dynamic", {}).get(
            "identified_objections", []
        )
        if o.get("status") == "active"
    ]
    resolved_objections = [
        o.get("text")
        for o in state.get("customer_profile_dynamic", {}).get(
            "identified_objections", []
        )
        if o.get("status") == "resolved"
    ]
    confirmed_needs = [
        n.get("text")
        for n in state.get("customer_profile_dynamic", {}).get("identified_needs", [])
        if n.get("status") == "confirmed_by_user"
    ]

    user_response_analysis_text = "N/A"
    if user_analysis and isinstance(user_analysis, dict):
        analysis_detail = user_analysis.get("analysis_of_response_to_agent_action", {})
        if isinstance(analysis_detail, dict):
            user_response_analysis_text = analysis_detail.get(
                "user_response_to_agent_action", "N/A"
            )

    prompt_context = {
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
        "last_user_message_text": state.get("current_user_input_text", "N/A"),
        "last_discerned_intent": state.get("customer_profile_dynamic", {}).get(
            "last_discerned_intent", "N/A"
        ),
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
        # Passar constantes que o prompt usa
        "MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION": MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION,
        "MAX_SPIN_QUESTIONS_PER_CYCLE": MAX_SPIN_QUESTIONS_PER_CYCLE,
    }

    # --- 2. Chamar o LLM ---
    if not hasattr(llm_strategist, "with_structured_output"):
        logger.error(
            f"[{node_name}] LLM instance does not support with_structured_output."
        )
        return {
            "next_agent_action_command": None,
            "action_parameters": {},
            "last_processing_error": "LLM for proactive step decision lacks structured output.",
        }

    try:
        proactive_chain = (
            PROMPT_DETERMINE_PROACTIVE_STEP
            | llm_strategist.with_structured_output(ProactiveStepDecision)
        )
        logger.debug(f"[{node_name}] Invoking LLM for proactive step decision...")
        # logger.trace(f"[{node_name}] Prompt context for proactive LLM: {to_json_safe(prompt_context, indent=2)}")

        llm_decision: ProactiveStepDecision = await proactive_chain.ainvoke(
            prompt_context
        )
        logger.info(
            f"[{node_name}] LLM proactive decision: {llm_decision.model_dump_json(indent=2)}"
        )

        if llm_decision.justification:
            logger.info(
                f"[{node_name}] LLM Justification: {llm_decision.justification}"
            )

    except Exception as e:
        logger.exception(
            f"[{node_name}] Error invoking LLM for proactive step decision: {e}"
        )
        return {
            "next_agent_action_command": None,
            "action_parameters": {},
            "last_processing_error": f"Proactive step LLM invocation failed: {e}",
        }

    # --- 3. Preparar o delta do estado ---
    # O `current_agent_goal` não é modificado por este nó diretamente.
    # Este nó apenas decide a *próxima ação* que o Planner procedural não conseguiu determinar.
    # O Planner procedural já teria definido o goal apropriado (ex: retomado um goal anterior).
    updated_state_delta: Dict[str, Any] = {
        "next_agent_action_command": llm_decision.proactive_action_command,
        "action_parameters": llm_decision.proactive_action_parameters or {},
        "last_processing_error": None,  # Limpar erro se decisão foi bem-sucedida
    }

    if llm_decision.proactive_action_command:
        logger.info(
            f"[{node_name}] Proactive action decided: {llm_decision.proactive_action_command} with params {llm_decision.proactive_action_parameters}"
        )
    else:
        logger.info(
            f"[{node_name}] LLM decided no proactive action is appropriate at this time."
        )

    return updated_state_delta
