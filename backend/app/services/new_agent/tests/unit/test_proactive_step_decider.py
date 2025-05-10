from langchain_core.language_models import BaseChatModel

# backend/app/services/ai_reply/new_agent/tests/unit/test_proactive_step_decider_node.py

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
import time

# Módulo e função a serem testados
from app.services.new_agent.components.proactive_step_decider import (
    proactive_step_decider_node,
    PROMPT_DETERMINE_PROACTIVE_STEP,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    AgentGoal,
    AgentActionType,  # Importado para ProactiveStepDecision
    AgentActionDetails,  # Importado para ProactiveStepDecision
)
from app.services.new_agent.schemas.proactive_step_output import ProactiveStepDecision

# --- Fixtures ---


@pytest.fixture
def base_state_for_proactive_decider() -> RichConversationState:
    """Fornece um RichConversationState base para os testes do decidor proativo."""
    return RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "Proactive Co",
            "language": "pt-br",
        },  # Adicionado language
        agent_config={},
        messages=[],
        current_user_input_text="Ok.",
        current_turn_number=3,
        current_agent_goal=AgentGoal(
            goal_type="INVESTIGATING_NEEDS",
            goal_details={
                "last_spin_type_asked": "Implication",
                "spin_questions_asked_this_cycle": 2,
            },
            previous_goal_if_interrupted=None,
        ),
        last_agent_action={
            "action_type": "ASK_SPIN_QUESTION",
            "details": {"spin_type": "Implication"},
            "action_generation_text": "Qual o impacto disso?",
            "attempts": 1,
        },
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "last_discerned_intent": "RespondingToAgent",
            "identified_objections": [],
            "identified_needs": [],
            "identified_pain_points": [],
            "certainty_levels": {},
        },
        user_input_analysis_result={
            "analysis_of_response_to_agent_action": {
                "user_response_to_agent_action": "acknowledged_action"
            },
            "overall_intent": "RespondingToAgent",
            "extracted_questions": [],  # Adicionar chaves esperadas pelo UserInputAnalysisOutput
            "extracted_objections": [],
            "extracted_needs_or_pains": [],
            "is_primarily_vague_statement": False,
            "is_primarily_off_topic": False,
            "correction_details_text": None,
            "reaction_to_solution_presentation": None,  # Adicionar chaves esperadas
            "objection_status_after_rebuttal": None,  # Adicionar chaves esperadas
        },
        closing_process_status="not_started",
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        pending_correction_details_for_proposal=None,
        applied_correction_details=None,
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,
        final_agent_message_text=None,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time(),
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        next_agent_action_command=None,
        action_parameters={},
    )


@pytest.fixture
def mock_llm_config() -> dict:
    """Fornece uma configuração mockada com uma instância de LLM."""
    mock_llm = AsyncMock(spec=BaseChatModel)
    return {
        "configurable": {
            "llm_strategy_instance": mock_llm,
        }
    }


# --- Testes ---


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_plans_spin_question(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Testa se o decidor proativo corretamente planeja uma pergunta SPIN
    quando o LLM mockado retorna essa decisão.
    """
    state = base_state_for_proactive_decider

    expected_action_params = AgentActionDetails(spin_type="NeedPayoff")
    mock_decision = ProactiveStepDecision(
        proactive_action_command="ASK_SPIN_QUESTION",
        proactive_action_parameters=expected_action_params,
        justification="User acknowledged, continuing SPIN.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    args, kwargs = mock_call_structured_llm.call_args
    assert kwargs.get("output_schema") == ProactiveStepDecision
    assert "current_goal_type_before_initiative" in kwargs.get("prompt_values", {})
    assert (
        kwargs.get("prompt_values")["current_goal_type_before_initiative"]
        == "INVESTIGATING_NEEDS"
    )

    assert delta.get("next_agent_action_command") == "ASK_SPIN_QUESTION"
    assert delta.get("action_parameters") == expected_action_params
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_plans_no_action(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Testa se o decidor proativo corretamente não planeja nenhuma ação
    quando o LLM mockado retorna uma decisão de não agir.
    """
    state = base_state_for_proactive_decider

    mock_decision = ProactiveStepDecision(
        proactive_action_command=None,
        proactive_action_parameters={},
        justification="No clear proactive step beneficial now.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    # Se o LLM decide não agir, o erro específico é "LLM proactive decider returned no action."
    # ou None se a chamada foi bem sucedida mas sem ação.
    # O código atual define o erro como "LLM proactive decider returned no action."
    # e depois o limpa se a chamada LLM foi bem-sucedida.
    # Vamos verificar se o erro é None, pois uma decisão de "não fazer nada" não é um erro de processamento.
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_handles_llm_failure(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Testa o comportamento do decidor quando a chamada ao _call_structured_llm falha (retorna None).
    """
    state = base_state_for_proactive_decider
    mock_call_structured_llm.return_value = None  # Simula falha na chamada LLM

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    assert "LLM proactive step decision failed or was unparsable." in (
        delta.get("last_processing_error") or ""
    )


@pytest.mark.asyncio
async def test_proactive_decider_handles_missing_llm_in_config(
    base_state_for_proactive_decider: RichConversationState,
):
    """
    Testa o comportamento se nenhuma instância de LLM for fornecida na configuração.
    """
    state = base_state_for_proactive_decider
    empty_config = {"configurable": {}}

    delta = await proactive_step_decider_node(state, empty_config)

    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    assert "LLM/helper for proactive step decision unavailable." in (
        delta.get("last_processing_error") or ""
    )
