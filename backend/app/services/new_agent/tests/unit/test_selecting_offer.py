# tests/unit/test_offer_selector.py

import pytest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from uuid import uuid4
from typing import Dict, Any, List, Optional
from langchain_core.language_models import BaseChatModel


# Import the node function and schemas
from app.services.new_agent.components.offer_selector import (
    select_offer_node,
    _format_available_offerings_for_prompt,  # Helper, might test separately or implicitly
    _format_identified_needs_pains_for_prompt,  # Helper
)
from app.services.new_agent.schemas.offer_selection_output import (
    OfferSelectionOutput,
    SelectedOffer,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    DynamicCustomerProfile,
)
from app.api.schemas.company_profile import (
    CompanyProfileSchema,
    OfferingInfo,
)  # For creating company_profile


# Mock for LLM
class MockLLM(MagicMock):
    pass


@pytest.fixture
def mock_llm_strategy():
    return MockLLM(spec=BaseChatModel)


@pytest.fixture
def base_state_for_offer_selector() -> RichConversationState:
    """Provides a base RichConversationState for offer selector tests."""
    profile_dict = {
        "company_name": "Selector Test Co",
        "language": "pt-br",
        "sales_tone": "consultivo",
        "offering_overview": [  # Sample offerings
            OfferingInfo(
                name="Produto Básico",
                short_description="Para necessidades simples.",
                key_features=["Fácil de usar"],
                price_info="R$50",
            ),
            OfferingInfo(
                name="Produto Avançado",
                short_description="Para usuários experientes.",
                key_features=["Muitos recursos", "Alta performance"],
                price_info="R$200",
            ),
            OfferingInfo(
                name="Serviço Premium",
                short_description="Consultoria especializada.",
                key_features=["Suporte VIP"],
                price_info="R$500/hora",
            ),
        ],
        "business_description": "Vendemos soluções.",
        "fallback_contact_info": "contato@selector.co",
        # Add other fields if _prepare_common_prompt_context (used by _call_structured_llm indirectly) needs them
    }
    # Ensure all required fields for CompanyProfileSchema are present or provide defaults
    # For simplicity, we'll assume profile_dict is sufficient for what select_offer_node directly uses.

    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile=profile_dict,  # type: ignore # Using dict for fixture simplicity
        agent_config={},
        messages=[
            {"type": "human", "content": "Olá, preciso de ajuda."}
        ],  # Basic history
        current_user_input_text="Estou procurando algo para performance.",
        current_turn_number=3,
        current_agent_goal={
            "goal_type": "PRESENTING_SOLUTION",
            "goal_details": {"status": "awaiting_offer_selection"},
        },
        customer_profile_dynamic=DynamicCustomerProfile(
            identified_needs=[
                {
                    "text": "Preciso de alta performance",
                    "status": "active",
                    "priority": 1,
                    "source_turn": 2,
                }
            ],
            identified_pain_points=[],
            identified_objections=[],
            certainty_levels={
                "product": None,
                "agent": None,
                "company": None,
                "last_assessed_turn": None,
            },
            last_discerned_intent="ExpressingNeedOrPain",
        ),
        # ... other fields can use defaults or be None for these tests
        last_agent_action=None,
        user_interruptions_queue=[],
        customer_question_log=[],
        current_turn_extracted_questions=None,
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,
        final_agent_message_text=None,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        offer_selection_result=None,
        next_agent_action_command=None,
        action_parameters={},
        suggested_goal_type=None,
        suggested_goal_details=None,
        follow_up_scheduled=None,
        follow_up_attempt_count=None,
        last_message_from_agent_timestamp=None,
        trigger_event=None,
    )
    return state


# --- Test Cases ---


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.offer_selector._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_select_offer_node_successfully_selects_offer(
    mock_call_structured_llm: AsyncMock,
    base_state_for_offer_selector: RichConversationState,
    mock_llm_strategy: BaseChatModel,
):
    """
    Tests successful offer selection.
    """
    state = base_state_for_offer_selector
    config = {"configurable": {"llm_strategy_instance": mock_llm_strategy}}

    # Mock the LLM's structured output
    expected_selected_offer = SelectedOffer(
        product_name="Produto Avançado",
        reason_for_selection="O cliente mencionou necessidade de performance.",
        confidence_score=0.9,
        key_benefit_to_highlight="alta performance e muitos recursos",
    )
    mock_llm_output = OfferSelectionOutput(
        selected_offer=expected_selected_offer,
        no_suitable_offer_found=False,
        overall_justification="Produto Avançado é o mais adequado.",
    )
    mock_call_structured_llm.return_value = mock_llm_output

    delta = await select_offer_node(state, config)

    mock_call_structured_llm.assert_called_once()
    call_args, call_kwargs = mock_call_structured_llm.call_args
    assert call_kwargs["llm"] == mock_llm_strategy
    assert call_kwargs["output_schema"] == OfferSelectionOutput
    assert (
        "Estou procurando algo para performance."
        in call_kwargs["prompt_values"]["last_user_message"]
    )
    assert (
        "Produto Avançado"
        in call_kwargs["prompt_values"]["available_offerings_formatted_list"]
    )

    assert delta["last_processing_error"] is None
    assert delta["offer_selection_result"] is not None
    result_obj = OfferSelectionOutput.model_validate(delta["offer_selection_result"])
    assert result_obj.selected_offer is not None
    assert result_obj.selected_offer.product_name == "Produto Avançado"
    assert (
        result_obj.selected_offer.reason_for_selection
        == "O cliente mencionou necessidade de performance."
    )
    assert result_obj.no_suitable_offer_found is False


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.offer_selector._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_select_offer_node_no_suitable_offer_found(
    mock_call_structured_llm: AsyncMock,
    base_state_for_offer_selector: RichConversationState,
    mock_llm_strategy: BaseChatModel,
):
    """
    Tests the case where the LLM determines no offer is suitable.
    """
    state = base_state_for_offer_selector
    state["current_user_input_text"] = (
        "Preciso de algo para jardinagem exótica."  # Unmatched need
    )
    state["customer_profile_dynamic"]["identified_needs"] = [
        {
            "text": "jardinagem exótica",
            "status": "active",
            "priority": 1,
            "source_turn": 2,
        }
    ]
    config = {"configurable": {"llm_strategy_instance": mock_llm_strategy}}

    mock_llm_output = OfferSelectionOutput(
        selected_offer=None,
        no_suitable_offer_found=True,
        alternative_suggestions_if_no_match=[
            "Talvez o Produto Básico para tarefas gerais?"
        ],
        overall_justification="Nenhuma oferta específica para jardinagem exótica.",
    )
    mock_call_structured_llm.return_value = mock_llm_output

    delta = await select_offer_node(state, config)

    mock_call_structured_llm.assert_called_once()
    assert delta["last_processing_error"] is None
    result_obj = OfferSelectionOutput.model_validate(delta["offer_selection_result"])
    assert result_obj.selected_offer is None
    assert result_obj.no_suitable_offer_found is True
    assert result_obj.alternative_suggestions_if_no_match == [
        "Talvez o Produto Básico para tarefas gerais?"
    ]


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.offer_selector._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_select_offer_node_clarification_needed(
    mock_call_structured_llm: AsyncMock,
    base_state_for_offer_selector: RichConversationState,
    mock_llm_strategy: BaseChatModel,
):
    """
    Tests the case where the LLM suggests clarifying questions.
    """
    state = base_state_for_offer_selector
    state["current_user_input_text"] = "Quero uma solução."  # Very vague
    state["customer_profile_dynamic"]["identified_needs"] = []
    config = {"configurable": {"llm_strategy_instance": mock_llm_strategy}}

    mock_llm_output = OfferSelectionOutput(
        selected_offer=None,
        no_suitable_offer_found=False,  # Not explicitly "no offer", but needs more info
        clarifying_questions_to_ask=[
            "Para qual tipo de problema você busca uma solução?",
            "Você tem algum orçamento em mente?",
        ],
        overall_justification="Input do usuário muito vago para selecionar uma oferta.",
    )
    mock_call_structured_llm.return_value = mock_llm_output

    delta = await select_offer_node(state, config)

    mock_call_structured_llm.assert_called_once()
    assert delta["last_processing_error"] is None
    result_obj = OfferSelectionOutput.model_validate(delta["offer_selection_result"])
    assert result_obj.selected_offer is None
    assert result_obj.clarifying_questions_to_ask == [
        "Para qual tipo de problema você busca uma solução?",
        "Você tem algum orçamento em mente?",
    ]


@pytest.mark.asyncio
async def test_select_offer_node_no_offers_in_profile(
    base_state_for_offer_selector: RichConversationState,
    mock_llm_strategy: BaseChatModel,  # LLM mock not strictly needed as it shouldn't be called
):
    """
    Tests behavior when company_profile has no offerings.
    It should not call the LLM.
    """
    state = base_state_for_offer_selector
    state["company_profile"]["offering_overview"] = []  # No offerings
    config = {"configurable": {"llm_strategy_instance": mock_llm_strategy}}

    # We don't need to mock _call_structured_llm here, as it shouldn't be called.
    # If it is, the test will fail due to unfulfilled mock or by not having a return value.
    with patch(
        "app.services.new_agent.components.offer_selector._call_structured_llm",
        new_callable=AsyncMock,
    ) as mock_llm_call_check:
        mock_llm_call_check.side_effect = AssertionError(
            "_call_structured_llm was called unexpectedly"
        )  # Fail if called

        delta = await select_offer_node(state, config)

        assert delta["last_processing_error"] is None
        result_obj = OfferSelectionOutput.model_validate(
            delta["offer_selection_result"]
        )
        assert result_obj.selected_offer is None
        assert result_obj.no_suitable_offer_found is True
        assert (
            result_obj.overall_justification
            == "Não há ofertas configuradas no perfil da empresa para seleção."
        )
        mock_llm_call_check.assert_not_called()  # Verify LLM was not called


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.offer_selector._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_select_offer_node_llm_call_fails(
    mock_call_structured_llm: AsyncMock,
    base_state_for_offer_selector: RichConversationState,
    mock_llm_strategy: BaseChatModel,
):
    """
    Tests error handling when the LLM call itself fails.
    """
    state = base_state_for_offer_selector
    config = {"configurable": {"llm_strategy_instance": mock_llm_strategy}}

    mock_call_structured_llm.return_value = None  # Simulate LLM call failure

    delta = await select_offer_node(state, config)

    mock_call_structured_llm.assert_called_once()
    assert "Offer selection LLM call failed" in delta["last_processing_error"]  # type: ignore
    result_obj = OfferSelectionOutput.model_validate(delta["offer_selection_result"])
    assert result_obj.selected_offer is None
    assert result_obj.no_suitable_offer_found is True  # Fallback to no offer
    assert (
        result_obj.overall_justification
        == "Erro interno ao tentar selecionar uma oferta."
    )


# --- Tests for helper functions (optional, but good practice) ---


def test_format_available_offerings_for_prompt_empty():
    assert (
        _format_available_offerings_for_prompt([])
        == "Nenhuma oferta disponível no momento."
    )


def test_format_available_offerings_for_prompt_with_data():
    offerings = [
        OfferingInfo(
            name="Super Câmera",
            short_description="Tira fotos incríveis.",
            key_features=["Zoom 50x", "4K"],
            price_info="R$2500",
        ),
        OfferingInfo(
            name="Curso de Fotografia",
            short_description="Aprenda a fotografar.",
            key_features=["Online", "Certificado"],
            price_info="R$300",
        ),
    ]
    formatted_string = _format_available_offerings_for_prompt(offerings)
    assert "Super Câmera" in formatted_string
    assert "Zoom 50x" in formatted_string
    assert "R$2500" in formatted_string
    assert "Curso de Fotografia" in formatted_string
    assert "Online" in formatted_string
    assert "R$300" in formatted_string


def test_format_identified_needs_pains_for_prompt_empty():
    profile = DynamicCustomerProfile(
        identified_needs=[],
        identified_pain_points=[],
        identified_objections=[],
        certainty_levels={},
        last_discerned_intent=None,
    )
    assert (
        _format_identified_needs_pains_for_prompt(profile)
        == "Nenhuma necessidade ou dor específica identificada ainda."
    )


def test_format_identified_needs_pains_for_prompt_with_needs():
    profile = DynamicCustomerProfile(
        identified_needs=[
            {
                "text": "Preciso de algo rápido",
                "status": "active",
                "priority": 1,
                "source_turn": 1,
            }
        ],
        identified_pain_points=[
            {
                "text": "Meu sistema atual é lento",
                "status": "confirmed_by_user",
                "source_turn": 1,
            }
        ],
        identified_objections=[],
        certainty_levels={},
        last_discerned_intent=None,
    )
    formatted_string = _format_identified_needs_pains_for_prompt(profile)
    assert "Necessidades:" in formatted_string
    assert "- Preciso de algo rápido (Status: active)" in formatted_string
    assert "Dores/Problemas:" in formatted_string
    assert "- Meu sistema atual é lento (Status: confirmed_by_user)" in formatted_string
