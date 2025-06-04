# app/services/sales_agent/agent_hooks.py
from typing import Dict, Any, List, Optional, get_args
import time
from datetime import timedelta
from loguru import logger

from langchain_core.messages import (
    SystemMessage,
    BaseMessage,
    HumanMessage,
    AIMessage,
    RemoveMessage,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph.message import REMOVE_ALL_MESSAGES


from app.workers.ai_replier.utils.datetime import calculate_follow_up_delay

from .agent_state import (
    AgentState,
    SalesStageLiteral,
    PendingFollowUpTrigger,
)
from .schemas import StageAnalysisOutput

STATE_CONTEXT_MESSAGE_ID = (
    "stage_context_message_v1"  # Unique ID for our system message
)


async def intelligent_stage_analyzer_hook(
    state: AgentState, config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Analyzes conversation to determine and update sales stage before main LLM call.

    This pre-model hook is executed before the main agent LLM makes its decision
    for the turn. It performs the following steps:
    1.  Checks if the last message is a HumanMessage (i.e., new user input).
        If not, it skips analysis to avoid redundant processing on agent's internal
        turns or tool responses.
    2.  Retrieves a 'primary' LLM instance from the provided `config`.
    3.  If the LLM is available, it analyzes the last few messages of the conversation
        and the current sales stage from the input `state`.
    4.  It prompts the analysis LLM to determine the most appropriate current sales
        stage, provide reasoning, and suggest a strategic focus for the main agent.
    5.  If the analysis LLM determines a new sales stage different from the one in
        the input `state`, this hook updates `current_sales_stage` in the `state_updates`.
    6.  It then constructs a `SystemMessage` containing the (potentially updated)
        sales stage, the reasoning from the analysis, and the suggested focus.
    7.  This `SystemMessage` is prepended to the list of messages that will be
        sent to the main agent LLM for the current turn (using the `messages` key).
        It also ensures any previous context message from this hook is removed.

    If the analysis LLM is not available or an error occurs during analysis,
    it falls back to using the `current_sales_stage` from the input `state` and
    provides a default context message.

    Args:
        state: The current state of the conversation (AgentState object).
        config: The runnable config dictionary, expected to contain
                `configurable.llm_primary_instance` for the analysis LLM.

    Returns:
        A dictionary containing updates to be applied to the agent's state.
        This will include 'messages' for the main LLM and potentially
        'current_sales_stage' if it was changed by the analysis.
        Returns None or minimal updates if analysis is skipped.
    """
    logger.info("--- Executing pre_model_hook: intelligent_stage_analyzer_hook ---")

    state_updates: Dict[str, Any] = {}
    current_messages: List[BaseMessage] = state.messages[:]  # Work with a copy

    # Only run analysis if the last message is from a human (new input)
    if not current_messages or not isinstance(current_messages[-1], HumanMessage):
        logger.debug("No new human message, or history empty. Skipping stage analysis.")
        state_updates["messages"] = []
        return state_updates

    stage_analyzer_llm: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    # Remove previous stage context message if it exists, to avoid duplication
    # This uses the message ID we assign.
    messages_for_llm_input = [
        msg
        for msg in current_messages
        if getattr(msg, "id", None) != STATE_CONTEXT_MESSAGE_ID
    ]

    if not stage_analyzer_llm:
        logger.warning(
            "Stage analyzer LLM not found in config. Using existing stage for context."
        )
        current_sales_stage = state.current_sales_stage
        analysis_reasoning = (
            "Análise de estágio não disponível (LLM de análise ausente)."
        )
        suggested_focus = "Proceda com base no estágio atual e no bom senso."
    else:
        original_sales_stage = state.current_sales_stage
        recent_messages_for_analysis = messages_for_llm_input[-5:]

        available_stages_str = ", ".join(get_args(SalesStageLiteral))

        analysis_prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"""
                    Você é um analista sênior de operações de vendas. Suas tarefas são:
                        1. Determinar o estágio atual de vendas de uma conversa com base nas mensagens recentes e no estágio atual conhecido.
                        2. Fornecer uma breve justificativa para sua determinação de estágio.
                        3. Sugerir um foco estratégico ou um próximo passo lógico para o agente de vendas principal. Esta sugestão deve ser concisa, acionável, e **incentivar o engajamento proativo do cliente**. Por exemplo, se o agente acabou de responder a uma pergunta, o foco sugerido deve incluir uma forma de continuar a conversa (ex: fazer uma pergunta de acompanhamento, conectar a um benefício, sugerir explorar outro aspecto)

                    Os estágios de vendas disponíveis são: {available_stages_str}.
                    O estágio atual conhecido é: {original_sales_stage}.

                    Analise as seguintes mensagens recentes. Envie sua resposta no formato JSON especificado.
                    SEMPRE oriente o agente a verificar se é possível realizar a ação ou oferecer algo.

                    Conversa recente:
                    {{recent_messages_formatted}}""",
                ),
            ]
        )

        formatted_recent_messages = "\n".join(
            [
                f"{msg.type.upper()}: {msg.content}"
                for msg in recent_messages_for_analysis
            ]
        )

        structured_analyzer_llm = stage_analyzer_llm.with_structured_output(
            StageAnalysisOutput
        )
        analysis_chain = analysis_prompt_template | structured_analyzer_llm

        logger.debug(
            f"Invoking the LLM Sales Stage Analyst. Initial stage: {original_sales_stage}"
        )
        try:
            analysis_result: StageAnalysisOutput = await analysis_chain.ainvoke(
                {
                    "recent_messages_formatted": formatted_recent_messages,
                    "original_sales_stage": original_sales_stage,
                    "available_stages_str": available_stages_str,
                }
            )
            analyzed_sales_stage = analysis_result.determined_sales_stage
            analysis_reasoning = analysis_result.reasoning
            suggested_focus = analysis_result.suggested_next_focus
            logger.info(
                f"Analisador de estágio determinou: {analyzed_sales_stage}. "
                f"Razão: {analysis_reasoning}. "
                f"Foco Sugerido: {suggested_focus}"
            )
        except Exception as e:
            logger.error(
                f"Erro durante chamada ao LLM de análise de estágio: {e}. Usando estágio original."
            )
            analyzed_sales_stage = original_sales_stage
            analysis_reasoning = "Análise falhou, usando estágio anterior."
            suggested_focus = "Análise falhou, confie em seu julgamento."

    final_stage_for_turn = analyzed_sales_stage
    if original_sales_stage != analyzed_sales_stage:
        logger.info(
            f"Estágio de vendas atualizado pelo pre-model hook: de '{original_sales_stage}' para '{analyzed_sales_stage}'."
        )
        state_updates["current_sales_stage"] = analyzed_sales_stage
    else:
        logger.info(
            f"Sales stage '{original_sales_stage}' confirmed by pre-model hook analysis."
        )

    stage_context_message = SystemMessage(
        content=f"Atualização de Contexto do Sistema:\n"
        f"- Estágio de Vendas Atual: '{final_stage_for_turn}' (Análise: {analysis_reasoning})\n"
        f"- Foco Sugerido para Próximo Passo: {suggested_focus}\n"
        f"Ajuste sua resposta e ações de acordo.",
        id=STATE_CONTEXT_MESSAGE_ID,  # Assign an ID to this message
    )

    # Prepend the new context message to the (potentially filtered) message history
    first_message = current_messages[0] if current_messages else None
    if first_message and first_message.id == STATE_CONTEXT_MESSAGE_ID:
        messages_to_add = current_messages[1:]
    else:
        messages_to_add = current_messages

    state_updates["messages"] = [
        RemoveMessage(id=REMOVE_ALL_MESSAGES),
        stage_context_message,
        *messages_to_add,
    ]

    logger.debug(f"Pre-model hook returning updates: {list(state_updates.keys())}")
    return state_updates


def auto_follow_up_scheduler_hook(
    state: AgentState, config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Schedules or re-schedules follow-ups automatically after an agent turn.

    This post-model hook is executed after the main agent LLM and any tools
    have completed their actions for the current turn. Its primary responsibilities are:

    1.  **Sequential Follow-ups:** If the current turn was triggered by a
        `follow_up_timeout` event (meaning the agent just handled a scheduled
        follow-up), this hook will schedule the *next* follow-up in the
        sequence, provided the conversation is not closed and the maximum
        number of follow-up attempts has not been reached. It uses an
        incrementing attempt count and potentially an increasing delay.

    2.  **Default "Safety-Net" Follow-up:** If the current turn was *not* a
        follow-up timeout, the conversation is not closed, AND no follow-up
        is already explicitly pending (e.g., set by the agent's `schedule_follow_up`
        tool during the turn), this hook schedules a default initial follow-up.
        This ensures that open conversations receive a follow-up if the agent
        doesn't explicitly schedule one.

    The hook updates the `pending_follow_up_trigger` and `follow_up_attempt_count` fields in the
    `AgentState` by returning a dictionary of updates. These updates are then
    used by the ARQ task system to physically schedule the next check.

    Args:
        state: The current state of the conversation (AgentState object) after
               the agent's turn.
        config: The runnable config dictionary (currently unused in this hook but
                available if needed for future enhancements, e.g., passing settings).

    Returns:
        A dictionary containing updates to be applied to the agent's state,
        primarily for `pending_follow_up_trigger`, and
        `follow_up_attempt_count`. Returns `None` or an empty dictionary if
        no follow-up scheduling action is taken.
    """
    logger.info("--- Executing post_model_hook: auto_follow_up_scheduler_hook ---")

    current_stage: Optional[SalesStageLiteral] = state.current_sales_stage
    current_trigger_event: Optional[str] = state.trigger_event
    # Get pending_follow_up_trigger as a dict if it was stored as such
    existing_pending_trigger_dict: Optional[Dict[str, Any]] = (
        state.pending_follow_up_trigger
    )

    is_conversation_closed = current_stage in ["closed_won", "closed_lost"]
    state_updates: Dict[str, Any] = {}
    last_agent_message_timestamp = time.time()

    try:
        hook_settings = config.get("configurable", {}).get("hook_settings")
        default_delay_seconds = getattr(hook_settings, "default_delay_seconds", 600)
        follow_up_base_delay = getattr(hook_settings, "follow_up_base_delay", 600)
        follow_up_factor = getattr(hook_settings, "follow_up_factor", 11)
        max_follow_up_attempts = getattr(hook_settings, "max_follow_up_attempts", 3)
    except Exception:
        logger.warning(
            "Auto-Follow-Up Hook: Could not load settings, using hardcoded defaults."
        )
        default_delay_seconds = 86400
        follow_up_base_delay = 86400
        follow_up_factor = 2
        max_follow_up_attempts = 3

    if current_trigger_event == "follow_up_timeout":
        if existing_pending_trigger_dict:
            logger.info(
                "Auto-Follow-Up Hook: Agent explicitly scheduled a follow-up during this follow-up turn. Honoring agent's schedule."
            )
            return None

        current_attempt_count = state.follow_up_attempt_count
        next_attempt_number = current_attempt_count + 1

        if is_conversation_closed:
            logger.info(
                f"Auto-Follow-Up Hook: Conversation closed (stage: {current_stage}) during follow-up turn. No further follow-ups."
            )
            return None

        if next_attempt_number > max_follow_up_attempts:
            logger.info(
                f"Auto-Follow-Up Hook: Max follow-up attempts ({max_follow_up_attempts}) reached. Stopping."
            )
            return None

        next_delay = calculate_follow_up_delay(
            attempt_number=next_attempt_number + 1,
            base_delay_seconds=follow_up_base_delay,
            factor=follow_up_factor,
        )

        next_follow_up_reason = (
            f"Continuando nossa conversa (Follow-up {next_attempt_number})."
        )

        current_timestamp = time.time()

        if isinstance(next_delay, timedelta):
            next_delay_seconds = next_delay.total_seconds()
        else:
            next_delay_seconds = next_delay

        due_timestamp = current_timestamp + next_delay_seconds

        next_pending_trigger = PendingFollowUpTrigger(
            follow_up_type="custom_reminder",
            due_timestamp=due_timestamp,
            defer_by=next_delay_seconds,
            target_conversation_id=state.conversation_id,
            context={
                "reason": next_follow_up_reason,
                "current_cart_items_count": len(state.shopping_cart or []),
                "auto_scheduled_sequence": True,
                "sequence_attempt": next_attempt_number,
            },
        )
        state_updates["pending_follow_up_trigger"] = next_pending_trigger.model_dump(
            mode="json"
        )

        state_updates["follow_up_attempt_count"] = next_attempt_number
        state_updates["last_agent_message_timestamp"] = last_agent_message_timestamp

        logger.info(
            f"Auto-Follow-Up Hook: Scheduled NEXT follow-up (Attempt {next_attempt_number}). Due in {next_delay_seconds}s."
        )
        return state_updates

    elif not is_conversation_closed and not existing_pending_trigger_dict:
        logger.info(f"Auto-Follow-Up Hook: Default follow-up. Stage: {current_stage}.")

        auto_follow_up_reason = "Checking in on our recent conversation."

        current_timestamp = time.time()

        due_timestamp = current_timestamp + default_delay_seconds

        auto_pending_trigger = PendingFollowUpTrigger(
            follow_up_type="custom_reminder",
            due_timestamp=due_timestamp,
            defer_by=default_delay_seconds,
            target_conversation_id=state.conversation_id,
            context={
                "reason": auto_follow_up_reason,
                "current_cart_items_count": len(state.shopping_cart or []),
                "auto_scheduled_initial": True,
            },
        )
        state_updates["pending_follow_up_trigger"] = auto_pending_trigger.model_dump(
            mode="json"
        )

        state_updates["follow_up_attempt_count"] = 0
        logger.info(
            f"Auto-Follow-Up Hook: Default follow-up scheduled. Due in {default_delay_seconds}s."
        )
        state_updates["last_agent_message_timestamp"] = last_agent_message_timestamp
        return state_updates

    state_updates["last_agent_message_timestamp"] = last_agent_message_timestamp
    return state_updates
