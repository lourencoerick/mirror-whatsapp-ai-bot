# tests/unit/test_output_formatter.py

import pytest
from uuid import uuid4

# Importar a função e o nó a serem testados
from app.services.new_agent.components.output_formatter import (
    _apply_whatsapp_formatting,
    output_formatter_node,
)
from app.services.new_agent.state_definition import RichConversationState

# --- Testes para _apply_whatsapp_formatting ---


def test_apply_formatting_none_input():
    """Tests handling of None input."""
    assert _apply_whatsapp_formatting(None) == ""  # type: ignore


def test_apply_formatting_empty_string():
    """Tests handling of an empty string."""
    assert _apply_whatsapp_formatting("") == ""


def test_apply_formatting_strips_whitespace():
    """Tests if leading/trailing whitespace is stripped."""
    assert _apply_whatsapp_formatting("  Hello World  \n") == "Hello World"


def test_apply_formatting_no_change_needed():
    """Tests text that doesn't need changes."""
    text = "This is *correctly* formatted."
    assert _apply_whatsapp_formatting(text) == text


def test_apply_formatting_internal_whitespace_preserved():
    """Tests if internal whitespace is preserved."""
    text = "Line 1\nLine 2\tTabbed"
    assert _apply_whatsapp_formatting(text) == text


# --- Testes para output_formatter_node ---


@pytest.fixture
def base_state_for_formatter() -> RichConversationState:
    """Provides a base state for formatter node tests."""
    return RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={},
        agent_config={},
        messages=[],
        current_user_input_text="",
        current_turn_number=1,
        current_agent_goal={"goal_type": "IDLE"},
        last_agent_action=None,
        user_interruptions_queue=[],
        customer_profile_dynamic={},
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,  # Will be set by tests
        final_agent_message_text=None,  # Should be set by the node
        conversation_summary_for_llm=None,
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        next_agent_action_command=None,
        action_parameters={},
    )


@pytest.mark.asyncio
async def test_output_formatter_node_formats_text(base_state_for_formatter):
    """Tests if the node correctly formats text from the state."""
    state = base_state_for_formatter
    raw_text = "  Raw response with extra space.   "
    expected_formatted_text = "Raw response with extra space."
    state["last_agent_generation_text"] = raw_text

    delta = await output_formatter_node(state, {})

    assert "final_agent_message_text" in delta
    assert delta["final_agent_message_text"] == expected_formatted_text


@pytest.mark.asyncio
async def test_output_formatter_node_no_text_to_format(base_state_for_formatter):
    """Tests node behavior when last_agent_generation_text is None."""
    state = base_state_for_formatter
    state["last_agent_generation_text"] = None

    delta = await output_formatter_node(state, {})

    assert "final_agent_message_text" in delta
    assert delta["final_agent_message_text"] == ""  # Should return empty string


@pytest.mark.asyncio
async def test_output_formatter_node_empty_text_to_format(base_state_for_formatter):
    """Tests node behavior when last_agent_generation_text is an empty string."""
    state = base_state_for_formatter
    state["last_agent_generation_text"] = ""

    delta = await output_formatter_node(state, {})

    assert "final_agent_message_text" in delta
    assert delta["final_agent_message_text"] == ""  # Should return empty string
