# backend/app/services/ai_reply/new_agent/tests/unit/test_proactive_step_decider_node.py

import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
import time

from langchain_core.language_models import BaseChatModel

from app.services.new_agent.components.proactive_step_decider import (
    proactive_step_decider_node,
    PROMPT_DETERMINE_PROACTIVE_STEP,  # Keep if you want to inspect the prompt object itself
    _format_state_for_proactive_prompt,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    AgentGoal,
    AgentActionType,
    AgentActionDetails,
    AgentGoalType,  # Added for ProactiveStepDecision
    TriggerEventType,  # Added for state setup
)
from app.services.new_agent.schemas.proactive_step_output import ProactiveStepDecision
from app.services.new_agent.components.planner import (
    MAX_SPIN_QUESTIONS_PER_CYCLE,
)  # For prompt context

# --- Fixtures ---


@pytest.fixture
def base_state_for_proactive_decider() -> RichConversationState:
    """Provides a base RichConversationState for proactive decider tests."""
    # Ensure all fields from RichConversationState are present
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "Proactive Co",
            "language": "pt-br",
            "sales_tone": "amigável",
            "business_description": "Vendemos soluções proativas.",
            "offering_overview": [],
            "key_selling_points": [],
            "communication_guidelines": [],
            "fallback_contact_info": "fallback@proactive.co",
            "address": None,
            "opening_hours": None,
            "target_audience": None,
            "delivery_options": None,
            "company_main_link_fallback": "http://proactive.co",
            "specific_faq": [],
            "privacy_policy_link": None,
            "social_media_links": {},
        },
        agent_config={
            "max_follow_up_attempts": 3,
            "agent_name": "ProAgent",
            "agent_role": "Proactive Seller",
            "temperature_fast_llm": 0.1,
            "temperature_strategy_llm": 0.1,
            "temperature_primary_llm": 0.1,
            "model_fast_llm": "test-model",
            "model_strategy_llm": "test-model-strategy",
            "model_primary_llm": "test-model-primary",
            "embedding_model": "test-embedding",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.5,
        },
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
            "certainty_levels": {
                "product": None,
                "agent": None,
                "company": None,
                "last_assessed_turn": None,
            },
        },
        user_input_analysis_result={  # Ensure this matches UserInputAnalysisOutput structure
            "overall_intent": "RespondingToAgent",
            "analysis_of_response_to_agent_action": {
                "user_response_to_agent_action": "acknowledged_action"
            },
            "extracted_questions": [],
            "extracted_objections": [],
            "extracted_needs_or_pains": [],
            "is_primarily_vague_statement": False,
            "is_primarily_off_topic": False,
            "correction_details_text": None,
            "reaction_to_solution_presentation": {
                "reaction_type": "not_applicable",
                "details": None,
            },
            "objection_status_after_rebuttal": {
                "original_objection_text_handled": None,
                "status": "not_applicable",
                "new_objection_text": None,
            },
        },
        closing_process_status="not_started",
        customer_question_log=[],
        current_turn_extracted_questions=None,  # Can be None
        active_proposal=None,
        # pending_correction_details_for_proposal=None, # Removed as not in latest RichConversationState
        # applied_correction_details=None, # Removed as not in latest RichConversationState
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
        # Follow-up fields
        follow_up_scheduled=False,
        follow_up_attempt_count=0,
        last_message_from_agent_timestamp=None,
        trigger_event="user_message",  # Default
        # Proactive suggestion fields
        suggested_goal_type=None,
        suggested_goal_details=None,
    )
    return state


@pytest.fixture
def mock_llm_config() -> dict:
    """Provides a mocked configuration with an LLM instance."""
    mock_llm = AsyncMock(spec=BaseChatModel)
    return {
        "configurable": {
            "llm_strategy_instance": mock_llm,
            # Add other instances if your node tries to fall back
            "llm_primary_instance": mock_llm,
        }
    }


# --- Test Cases ---


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_direct_action_ask_spin(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Tests if the decider correctly plans a direct action (ASK_SPIN_QUESTION)
    when the LLM mock returns this decision.
    Note: This tests the decider's ability to output a direct command, even if
    ASK_SPIN_QUESTION might typically be a goal suggestion. The prompt guides this.
    """
    state = base_state_for_proactive_decider
    # Simulate that the planner decided to trigger proactive step
    state["action_parameters"] = {
        "trigger_source": "user_response_or_stagnation",
        "current_follow_up_attempts": 0,
    }

    expected_action_params = AgentActionDetails(spin_type="NeedPayoff")
    mock_decision = ProactiveStepDecision(
        proactive_action_command="ASK_SPIN_QUESTION",  # LLM decides to directly command this
        proactive_action_parameters=expected_action_params,
        justification="User acknowledged, continuing SPIN directly.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    called_args, called_kwargs = mock_call_structured_llm.call_args
    assert called_kwargs.get("output_schema") == ProactiveStepDecision

    # Check some key values passed to the prompt
    prompt_values = called_kwargs.get("prompt_values", {})
    assert "formatted_state_context" in prompt_values
    assert (
        prompt_values.get("current_goal_type_before_initiative")
        == "INVESTIGATING_NEEDS"
    )
    assert prompt_values.get("trigger_source") == "user_response_or_stagnation"

    assert delta.get("next_agent_action_command") == "ASK_SPIN_QUESTION"
    assert delta.get("action_parameters") == expected_action_params
    assert delta.get("last_processing_error") is None
    assert delta.get("suggested_goal_type") is None
    assert delta.get("suggested_goal_details") == {}


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_suggests_goal_investigating_needs(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Tests if the decider correctly suggests a new goal (INVESTIGATING_NEEDS)
    when the LLM mock returns this decision.
    """
    state = base_state_for_proactive_decider
    state["action_parameters"] = {
        "trigger_source": "user_response_or_stagnation",
        "current_follow_up_attempts": 0,
    }

    expected_goal_details = {"spin_type_to_ask_next": "Situation"}
    mock_decision = ProactiveStepDecision(
        proactive_action_command=None,
        proactive_action_parameters={},
        suggested_next_goal_type="INVESTIGATING_NEEDS",
        suggested_next_goal_details=expected_goal_details,
        justification="Conversation stalled, restarting need investigation.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    assert delta.get("next_agent_action_command") == "REPLAN_WITH_SUGGESTED_GOAL"
    assert delta.get("action_parameters") == {}  # Should be empty when suggesting goal
    assert delta.get("suggested_goal_type") == "INVESTIGATING_NEEDS"
    assert delta.get("suggested_goal_details") == expected_goal_details
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_direct_action_send_follow_up(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Tests if the decider correctly plans SEND_FOLLOW_UP_MESSAGE for a timeout.
    """
    state = base_state_for_proactive_decider
    # Simulate trigger from planner for follow-up
    state["action_parameters"] = {
        "trigger_source": "follow_up_timeout",
        "current_follow_up_attempts": 0,  # First attempt
    }
    # agent_config should provide max_follow_up_attempts
    state["agent_config"]["max_follow_up_attempts"] = 3

    expected_action_params = AgentActionDetails(
        current_follow_up_attempts=0,  # This is passed to response_generator
        max_follow_up_attempts_total=3,
        # context_goal_type and context_last_agent_message would be filled by prompt
    )
    mock_decision = ProactiveStepDecision(
        proactive_action_command="SEND_FOLLOW_UP_MESSAGE",
        proactive_action_parameters=expected_action_params,  # LLM would fill this based on its prompt
        justification="User inactive, sending follow-up 1 of 3.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    prompt_values = mock_call_structured_llm.call_args.kwargs.get("prompt_values", {})
    assert prompt_values.get("trigger_source") == "follow_up_timeout"
    assert prompt_values.get("current_follow_up_attempts") == 0
    assert prompt_values.get("max_follow_up_attempts_total") == 3

    assert delta.get("next_agent_action_command") == "SEND_FOLLOW_UP_MESSAGE"
    # The node adds these to action_parameters if the command is SEND_FOLLOW_UP_MESSAGE
    assert delta.get("action_parameters", {}).get("current_follow_up_attempts") == 0
    assert delta.get("action_parameters", {}).get("max_follow_up_attempts_total") == 3
    assert delta.get("last_processing_error") is None
    assert delta.get("suggested_goal_type") is None


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_direct_action_farewell_max_follow_ups(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    """
    Tests if the decider correctly plans GENERATE_FAREWELL when max follow-ups reached.
    """
    state = base_state_for_proactive_decider
    max_attempts = 2
    state["action_parameters"] = {
        "trigger_source": "follow_up_timeout",
        "current_follow_up_attempts": max_attempts,  # Max attempts reached
    }
    state["agent_config"]["max_follow_up_attempts"] = max_attempts

    expected_action_params = AgentActionDetails(
        reason="Inatividade do usuário após múltiplas tentativas de follow-up."
    )
    mock_decision = ProactiveStepDecision(
        proactive_action_command="GENERATE_FAREWELL",
        proactive_action_parameters=expected_action_params,
        justification="Max follow-ups reached.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    prompt_values = mock_call_structured_llm.call_args.kwargs.get("prompt_values", {})
    assert prompt_values.get("trigger_source") == "follow_up_timeout"
    assert prompt_values.get("current_follow_up_attempts") == max_attempts
    assert prompt_values.get("max_follow_up_attempts_total") == max_attempts

    assert delta.get("next_agent_action_command") == "GENERATE_FAREWELL"
    assert delta.get("action_parameters") == expected_action_params
    assert delta.get("last_processing_error") is None
    assert delta.get("suggested_goal_type") is None


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_plans_no_action_when_llm_suggests_none(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    state = base_state_for_proactive_decider
    state["action_parameters"] = {
        "trigger_source": "user_response_or_stagnation",
        "current_follow_up_attempts": 0,
    }

    mock_decision = ProactiveStepDecision(
        proactive_action_command=None,
        suggested_next_goal_type=None,  # Explicitly None
        justification="No clear proactive step beneficial now.",
    )
    mock_call_structured_llm.return_value = mock_decision

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    assert delta.get("suggested_goal_type") is None
    assert delta.get("suggested_goal_details") == {}
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch("app.services.new_agent.components.proactive_step_decider._call_structured_llm")
async def test_proactive_decider_handles_llm_failure_gracefully(
    mock_call_structured_llm: AsyncMock,
    base_state_for_proactive_decider: RichConversationState,
    mock_llm_config: dict,
):
    state = base_state_for_proactive_decider
    state["action_parameters"] = {
        "trigger_source": "user_response_or_stagnation",
        "current_follow_up_attempts": 0,
    }
    mock_call_structured_llm.return_value = None

    delta = await proactive_step_decider_node(state, mock_llm_config)

    mock_call_structured_llm.assert_called_once()
    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    assert delta.get("suggested_goal_type") is None
    assert delta.get("suggested_goal_details") == {}
    assert "LLM proactive step decision failed or was unparsable." in (
        delta.get("last_processing_error") or ""
    )


@pytest.mark.asyncio
async def test_proactive_decider_handles_missing_llm_in_config_gracefully(
    base_state_for_proactive_decider: RichConversationState,
):
    state = base_state_for_proactive_decider
    state["action_parameters"] = {
        "trigger_source": "user_response_or_stagnation",
        "current_follow_up_attempts": 0,
    }
    empty_config = {"configurable": {}}  # No LLM instance

    delta = await proactive_step_decider_node(state, empty_config)

    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}
    assert delta.get("suggested_goal_type") is None
    assert delta.get("suggested_goal_details") == {}
    assert "LLM/helper for proactive step decision unavailable." in (
        delta.get("last_processing_error") or ""
    )
