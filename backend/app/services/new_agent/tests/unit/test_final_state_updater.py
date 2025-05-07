# tests/unit/test_final_state_updater.py

import pytest
import time
from uuid import uuid4
from typing import Dict, Any, List

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from app.services.new_agent.components.final_state_updater import (
    finalize_turn_state_node,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    PendingAgentAction,
    AgentActionDetails,
    AgentActionType,
)


@pytest.fixture
def base_state_for_final_updater() -> RichConversationState:
    """Provides a base RichConversationState for final updater tests."""
    return RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={},
        agent_config={},
        messages=[],
        current_user_input_text="User input",
        current_turn_number=1,  # Turn já incrementado
        current_agent_goal={"goal_type": "IDLE"},
        last_agent_action=None,  # Será preenchido pelo nó
        user_interruptions_queue=[],
        customer_profile_dynamic={},
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        # Campos que este nó usa e depois limpa:
        next_agent_action_command=None,
        action_parameters={},
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,  # Texto bruto do ResponseGenerator
        final_agent_message_text=None,  # Texto formatado do OutputFormatter
        user_input_analysis_result={
            "overall_intent": "some_analysis"
        },  # Simular que não foi limpo
        # ---
        conversation_summary_for_llm=None,
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
    )


@pytest.mark.asyncio
async def test_finalize_turn_adds_ai_message_and_records_action(
    base_state_for_final_updater,
):
    state = base_state_for_final_updater
    state["messages"] = [HumanMessage(content="Olá")]  # Histórico inicial
    state["final_agent_message_text"] = "Olá! Como posso ajudar? (Formatado)"
    state["last_agent_generation_text"] = "Olá! Como posso ajudar?"  # Bruto
    state["next_agent_action_command"] = "GENERATE_GREETING"
    state["action_parameters"] = {"greeting_type": "initial"}

    delta = await finalize_turn_state_node(state, {})

    assert "messages" in delta
    assert len(delta["messages"]) == 2
    assert isinstance(delta["messages"][-1], AIMessage)
    assert delta["messages"][-1].content == "Olá! Como posso ajudar? (Formatado)"

    assert "last_agent_action" in delta
    last_action = delta["last_agent_action"]
    assert last_action is not None
    assert last_action.get("action_type") == "GENERATE_GREETING"
    assert last_action.get("details") == {"greeting_type": "initial"}
    assert (
        last_action.get("action_generation_text") == "Olá! Como posso ajudar?"
    )  # Usa o bruto
    assert last_action.get("attempts") == 1

    # Verificar limpeza
    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    assert delta.get("last_agent_generation_text") is None
    assert delta.get("final_agent_message_text") is None
    assert delta.get("user_input_analysis_result") is None


@pytest.mark.asyncio
async def test_finalize_turn_no_generated_text(base_state_for_final_updater):
    state = base_state_for_final_updater
    state["messages"] = [HumanMessage(content="Olá")]
    state["final_agent_message_text"] = None  # Sem texto formatado
    state["last_agent_generation_text"] = None  # Sem texto bruto
    state["next_agent_action_command"] = (
        "ACKNOWLEDGE_AND_TRANSITION"  # Ação foi planejada
    )

    delta = await finalize_turn_state_node(state, {})

    assert "messages" not in delta  # Não adiciona mensagem vazia
    assert "last_agent_action" in delta
    assert delta.get("last_agent_action") is None  # Limpo porque não houve texto
    assert delta.get("next_agent_action_command") is None  # Limpo


@pytest.mark.asyncio
async def test_finalize_turn_no_action_planned(base_state_for_final_updater):
    state = base_state_for_final_updater
    state["messages"] = [HumanMessage(content="Olá"), AIMessage(content="Oi")]
    state["final_agent_message_text"] = "Entendido."  # Agente disse algo
    state["last_agent_generation_text"] = "Entendido."
    state["next_agent_action_command"] = None  # Nenhuma ação planejada pelo Planner

    # Simular uma last_agent_action anterior para ver se é limpa
    state["last_agent_action"] = PendingAgentAction(
        action_type="SOME_PREVIOUS_ACTION",
        details={},
        action_generation_text="...",
        attempts=1,
    )

    delta = await finalize_turn_state_node(state, {})

    assert "messages" in delta
    assert delta["messages"][-1].content == "Entendido."

    assert "last_agent_action" in delta
    assert delta.get("last_agent_action") is None  # Limpo porque não houve novo comando
