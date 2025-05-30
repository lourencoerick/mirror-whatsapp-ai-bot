# tests/unit/test_response_generator.py

import pytest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from uuid import uuid4
from typing import Dict, Any

# Importar a função a ser testada e definições/schemas
from app.services.new_agent.components.response_generator import (
    response_generator_node,
    PROMPT_GENERATE_REBUTTAL,  # Importar prompts para verificar tipo
    PROMPT_ASK_CLARIFYING_QUESTION,
    PROMPT_ACKNOWLEDGE_AND_TRANSITION,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    AgentActionType,
    AgentActionDetails,
    SpinQuestionType,
    AgentGoal,
)
from app.services.new_agent.schemas.input_analysis import (
    UserInputAnalysisOutput,
)  # Apenas para exemplo de estado
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate  # Para verificar tipo do prompt


# Mock para LLM
class MockLLM(MagicMock):
    pass


@pytest.fixture
def mock_llm_primary():
    return MockLLM(spec=BaseChatModel)


# Fixture para estado base (pode ser importado/compartilhado)
@pytest.fixture
def base_state_for_generator() -> RichConversationState:
    """Provides a base RichConversationState for generator tests."""
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        # Perfil mínimo para _prepare_common_prompt_context
        company_profile={
            "company_name": "TestGen Co",
            "language": "pt-br",
            "sales_tone": "amigável",
            "fallback_contact_info": "Fallback default",
        },
        agent_config={},
        messages=[],
        current_user_input_text="Input",
        current_turn_number=2,
        current_agent_goal={"goal_type": "IDLE"},
        last_agent_action=None,
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        next_agent_action_command=None,  # Será definido por cada teste
        action_parameters={},  # Será definido por cada teste
    )
    return state


# --- Testes ---


@pytest.mark.asyncio
# Mockar a função auxiliar que chama o LLM
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
# Mockar a função auxiliar que prepara o contexto comum
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_spin(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa se o prompt SPIN correto é selecionado e chamado."""
    state = base_state_for_generator
    action: AgentActionType = "ASK_SPIN_QUESTION"
    params: AgentActionDetails = {"spin_type": "Problem"}
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    # Configurar mocks
    common_context_mock = {
        "company_name": "Test",
        "language": "pt",
        "sales_tone": "test",
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Qual o maior problema que você enfrenta com X?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    # Executar
    delta = await response_generator_node(state, config)

    # Verificar
    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    # Verificar se o prompt correto foi passado (pelo tipo e talvez conteúdo)
    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    # Verificar se o prompt contém identificadores do prompt SPIN
    assert "'{spin_type}'" in call_kwargs["prompt"].messages[0].prompt.template

    # Verificar se os valores corretos foram passados para o LLM
    expected_prompt_values = {**common_context_mock, **{"spin_type": "Problem"}}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    # Verificar o resultado retornado pelo nó
    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_answer_question(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa se o prompt ANSWER_DIRECT_QUESTION correto é selecionado."""
    state = base_state_for_generator
    action: AgentActionType = "ANSWER_DIRECT_QUESTION"
    question_text = "Qual o horário?"
    params: AgentActionDetails = {
        "question_to_answer_text": question_text,
        "question_to_answer_status": "newly_asked",
        "combined_spin_question_type": None,  # Explicitamente None para este teste
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params
    state["retrieved_knowledge_for_next_action"] = "RAG Context: Abrimos às 9h."

    # Mocking _prepare_common_prompt_context output accurately
    # Based on base_state_for_generator and _prepare_common_prompt_context logic
    common_context_mock = {
        "company_name": "TestGen Co",
        "language": "pt-br",
        "sales_tone": "amigável",
        "fallback_text": "Fallback default",
        "business_description": "N/A",  # Default from _prepare_common_prompt_context
        "offering_summary": "N/A",  # Default
        "key_selling_points": "N/A",  # Default
        "delivery_options_info": "Opções de delivery/pickup não especificadas.",  # Default
        "company_address_info": "",  # Default
        "opening_hours_info": "",  # Default
        "communication_guidelines": "N/A",  # Default
        "company_main_link_fallback": "nosso site.",  # Default
        "formatting_instructions": ANY,
        "chat_history": "Histórico indisponível.",  # Assuming fallback if input_processor not fully mocked
        "last_user_message": "Input",  # From base_state_for_generator
        "rag_context": "RAG Context: Abrimos às 9h.",  # From state
        "current_datetime": ANY,
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Nosso horário é das 9h às 18h."
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    assert "'{question_to_answer}'" in call_kwargs["prompt"].messages[0].prompt.template

    expected_specific_values = {
        "question_to_answer": question_text,
        "repetition_context_instructions": "",  # For newly_asked status
        "combined_spin_question_type_for_prompt": "None",  # Explicitly "None" string
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}

    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
async def test_generator_no_action_command(base_state_for_generator, mock_llm_primary):
    """Testa o comportamento quando nenhum comando de ação é fornecido."""
    state = base_state_for_generator
    state["next_agent_action_command"] = None  # Sem comando
    state["action_parameters"] = {}

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    assert delta.get("last_agent_generation_text") is None
    assert delta.get("last_processing_error") is None  # Não é erro, apenas skip


@pytest.mark.asyncio
async def test_generator_unknown_action_command(
    base_state_for_generator, mock_llm_primary
):
    """Testa o comportamento com um comando de ação não mapeado."""
    state = base_state_for_generator
    action: Any = "INVENTED_ACTION"  # Comando inválido/não mapeado
    state["next_agent_action_command"] = action
    state["action_parameters"] = {}

    # Mock _prepare_common_prompt_context para retornar o fallback_text
    with patch(
        "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
    ) as mock_prep:
        mock_prep.return_value = {"fallback_text": "Fallback por comando desconhecido."}
        config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
        delta = await response_generator_node(state, config)

    assert (
        delta.get("last_agent_generation_text") == "Fallback por comando desconhecido."
    )
    assert "No prompt for action INVENTED_ACTION" in delta.get(
        "last_processing_error", ""
    )


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_llm_call_fails(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa o tratamento de erro quando a chamada LLM falha."""
    state = base_state_for_generator
    action: AgentActionType = "ASK_SPIN_QUESTION"
    params: AgentActionDetails = {"spin_type": "Problem"}
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {"fallback_text": "Fallback por falha LLM."}
    mock_prepare_context.return_value = common_context_mock
    mock_call_llm.return_value = None  # Simula falha ou resposta vazia

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once()
    mock_call_llm.assert_called_once()  # Verifica que a chamada foi tentada

    assert delta.get("last_agent_generation_text") == "Fallback por falha LLM."
    assert "LLM generation failed or empty for ASK_SPIN_QUESTION" in delta.get(
        "last_processing_error", ""
    )


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_rebuttal(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa se o prompt GENERATE_REBUTTAL correto é selecionado."""
    state = base_state_for_generator
    action: AgentActionType = "GENERATE_REBUTTAL"
    params: AgentActionDetails = {"objection_text_to_address": "É muito caro."}
    state["next_agent_action_command"] = action
    state["action_parameters"] = params
    state["retrieved_knowledge_for_next_action"] = (
        "RAG: Oferecemos parcelamento."  # Simular RAG
    )

    common_context_mock = {
        "company_name": "Test",
        "rag_context": "RAG: Oferecemos parcelamento.",
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Entendo a preocupação com o preço. Oferecemos opções de parcelamento para facilitar. Isso ajudaria?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert (
        call_kwargs["prompt"] == PROMPT_GENERATE_REBUTTAL
    )  # Verificar se é o objeto de prompt correto

    expected_prompt_values = {
        **common_context_mock,
        **{"objection_text": "É muito caro."},
    }
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_clarifying_question(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa se o prompt ASK_CLARIFYING_QUESTION correto é selecionado."""
    state = base_state_for_generator
    action: AgentActionType = "ASK_CLARIFYING_QUESTION"
    clarification_context_from_planner = (
        "Isso parece confuso e preciso de mais detalhes."
    )

    # Planner should put the context for clarification into action_parameters["context"]
    params: AgentActionDetails = {"context": clarification_context_from_planner}
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    # current_agent_goal is less relevant now for vague_statement_text if planner provides context
    state["current_agent_goal"] = AgentGoal(
        goal_type="CLARIFYING_USER_INPUT",  # Goal that led to this action
        goal_details={
            "clarification_type": "vague",
            "text": "Original vague user text",
        },  # Original text
        previous_goal_if_interrupted=None,
    )

    common_context_mock = {
        "company_name": "TestGen Co",
        "language": "pt-br",
        "sales_tone": "amigável",
        "fallback_text": "Fallback default",
        "business_description": "N/A",
        "offering_summary": "N/A",
        "key_selling_points": "N/A",
        "delivery_options_info": "Opções de delivery/pickup não especificadas.",
        "company_address_info": "",
        "opening_hours_info": "",
        "communication_guidelines": "N/A",
        "company_main_link_fallback": "nosso site.",
        "formatting_instructions": ANY,
        "chat_history": "Histórico indisponível.",
        "last_user_message": "Input",
        "rag_context": "Nenhum contexto adicional disponível.",
        "current_datetime": ANY,
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Poderia me dizer o que especificamente pareceu confuso?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert call_kwargs["prompt"] == PROMPT_ASK_CLARIFYING_QUESTION

    expected_specific_values = {
        "vague_statement_text": clarification_context_from_planner,  # Comes from action_params["context"]
        "last_action_context": clarification_context_from_planner,  # Also from action_params["context"]
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_ack_transition(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa se o prompt ACKNOWLEDGE_AND_TRANSITION correto é selecionado."""
    state = base_state_for_generator
    action: AgentActionType = "ACKNOWLEDGE_AND_TRANSITION"
    off_topic_text = "Falando nisso, viu o jogo?"
    # O planner agora passa 'interrupted_goal_type_hint'
    interrupted_goal_hint = "INVESTIGATING_NEEDS"

    params: AgentActionDetails = {
        "off_topic_text": off_topic_text,
        "interrupted_goal_type_hint": interrupted_goal_hint,  # Novo parâmetro
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    # common_context_mock precisa ser mais completo para evitar mismatches
    common_context_mock = {
        "company_name": "TestGen Co",
        "language": "pt-br",
        "sales_tone": "amigável",
        "fallback_text": "Fallback default",
        "business_description": "N/A",
        "offering_summary": "N/A",
        "key_selling_points": "N/A",
        "delivery_options_info": "Opções de delivery/pickup não especificadas.",
        "company_address_info": "",
        "opening_hours_info": "",
        "communication_guidelines": "N/A",
        "company_main_link_fallback": "nosso site.",
        "formatting_instructions": ANY,
        "chat_history": "Histórico indisponível.",
        "last_user_message": "Input",
        "rag_context": "Nenhum contexto adicional disponível.",
        "current_datetime": ANY,
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = (
        "Entendido sobre o jogo. Retomando nossa conversa sobre suas necessidades..."
    )
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert call_kwargs["prompt"] == PROMPT_ACKNOWLEDGE_AND_TRANSITION

    # <<< CORRECTED expected_specific_values >>>
    expected_specific_values = {
        "off_topic_text": off_topic_text,
        "interrupted_goal_type_hint_text": interrupted_goal_hint,  # Deve ser este agora
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_initiate_closing_no_details(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests prompt selection and parameter preparation for INITIATE_CLOSING without proposal details."""
    state = base_state_for_generator
    action: AgentActionType = "INITIATE_CLOSING"
    params: AgentActionDetails = {}  # No product/price details provided by Planner
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {"language": "pt-br", "sales_tone": "eficiente"}  # Example
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Perfeito! Gostaria de prosseguir com este pedido?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    assert (
        "Gere a mensagem para iniciar o fechamento"
        in call_kwargs["prompt"].messages[0].prompt.template
    )

    # Check specific values passed to the prompt
    expected_specific_values = {
        "product_name_price_info": "este pedido",  # Default when no details
        "product_name_fallback": "este pedido",  # Default when no details
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_initiate_closing_with_details(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests prompt selection and parameter preparation for INITIATE_CLOSING with proposal details."""
    state = base_state_for_generator
    action: AgentActionType = "INITIATE_CLOSING"
    params: AgentActionDetails = {  # Planner provided details
        "product_name": "Plano Premium",
        "price": 99.90,
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {"language": "pt-br", "sales_tone": "eficiente"}
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Perfeito! Gostaria então de prosseguir com o pedido do *Plano Premium* (R$99.90)?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    assert (
        "Gere a mensagem para iniciar o fechamento"
        in call_kwargs["prompt"].messages[0].prompt.template
    )

    # Check specific values passed to the prompt
    expected_specific_values = {
        "product_name_price_info": "o *Plano Premium* (R$99.90)",  # Formatted string
        "product_name_fallback": "o *Plano Premium*",  # Fallback uses name
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_confirm_details(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests prompt selection and parameter preparation for CONFIRM_ORDER_DETAILS."""
    state = base_state_for_generator
    action: AgentActionType = "CONFIRM_ORDER_DETAILS"
    params: AgentActionDetails = {  # Planner provided details
        "product_name": "Plano Avançado",
        "price": 299.00,
        "price_info": "/mês",
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {"language": "pt-br", "sales_tone": "eficiente"}
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Ótimo! Só para confirmar, estamos prosseguindo com o *Plano Avançado* pelo valor de R$299.00/mês. Correto?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    assert (
        "Gere a mensagem de confirmação dos detalhes"
        in call_kwargs["prompt"].messages[0].prompt.template
    )

    # Check specific values passed to the prompt
    expected_specific_values = {
        "product_name": "Plano Avançado",
        "price_info": "R$299.00/mês",  # Formatted string
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_confirm_details_handles_missing_price_info(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests CONFIRM_ORDER_DETAILS handles missing price or price_info."""
    state = base_state_for_generator
    action: AgentActionType = "CONFIRM_ORDER_DETAILS"
    params: AgentActionDetails = {  # Missing price_info
        "product_name": "Consulta Avulsa",
        "price": 500.00,
        # "price_info": None # Missing
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {"language": "pt-br", "sales_tone": "eficiente"}
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Ok! Confirmando então: *Consulta Avulsa* pelo valor de R$500.00. Podemos prosseguir?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    # Check specific values passed to the prompt
    expected_specific_values = {
        "product_name": "Consulta Avulsa",
        "price_info": "R$500.00",  # Formatted string without suffix
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_process_order(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests prompt selection and parameters for PROCESS_ORDER_CONFIRMATION."""
    state = base_state_for_generator
    action: AgentActionType = "PROCESS_ORDER_CONFIRMATION"
    product_name_confirmed = "Plano Super Completo"
    params: AgentActionDetails = {"product_name": product_name_confirmed}
    state["next_agent_action_command"] = action
    state["action_parameters"] = params
    # Simulate active_proposal which might contain the product_url
    state["active_proposal"] = {
        "product_name": product_name_confirmed,
        "product_url": "https://example.com/checkout/super-completo",
        "price": 199.99,  # Other fields as per ProposedSolution
        "key_benefits_highlighted": [],
        "turn_proposed": 1,
        "status": "accepted",  # or proposed
        "quantity": None,
        "price_info": None,
    }

    common_context_mock = {
        "company_name": "TestGen Co",
        "language": "pt-br",
        "sales_tone": "confiante",
        "fallback_text": "Fallback default",
        "business_description": "N/A",
        "offering_summary": "N/A",
        "key_selling_points": "N/A",
        "delivery_options_info": "Opções de delivery/pickup não especificadas.",
        "company_address_info": "",
        "opening_hours_info": "",
        "communication_guidelines": "N/A",
        "company_main_link_fallback": "https://example.com/fallback-link",  # Important for this test
        "formatting_instructions": ANY,
        "chat_history": "Histórico indisponível.",
        "last_user_message": "Input",
        "rag_context": "Nenhum contexto adicional disponível.",
        "current_datetime": ANY,
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = f"Excelente! Seu pedido para o *{product_name_confirmed}* foi processado com sucesso. Para finalizar, acesse: https://example.com/checkout/super-completo"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    # <<< CORRECTED ASSERTION for prompt content >>>
    assert (
        "Gere APENAS a mensagem de confirmação do pedido e o link para finalização da compra"  # More specific to this prompt
        in call_kwargs["prompt"].messages[0].prompt.template
    )

    expected_specific_values = {
        "product_name": product_name_confirmed,
        "product_link_or_fallback": "https://example.com/checkout/super-completo",  # From active_proposal
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_farewell_rejection(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests prompt selection and parameters for GENERATE_FAREWELL after rejection."""
    state = base_state_for_generator
    action: AgentActionType = "GENERATE_FAREWELL"
    params: AgentActionDetails = {  # Planner provided reason
        "reason": "Closing attempt rejected"
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {
        "language": "pt-br",
        "sales_tone": "compreensivo",
        "fallback_text": "site.com/contato",  # Example fallback from common context
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Entendo perfeitamente. Agradeço seu tempo e, se mudar de ideia ou tiver dúvidas, pode me chamar! Tenha um ótimo dia."
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    # Check for identifier in the correct prompt
    assert (
        "Gere a mensagem de despedida"
        in call_kwargs["prompt"].messages[0].prompt.template
    )

    # Check specific values passed to the prompt
    expected_specific_values = {
        "reason": "Closing attempt rejected",
        "fallback_contact_info": "site.com/contato",  # Check if fallback is passed
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.response_generator._call_llm_for_generation",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.response_generator._prepare_common_prompt_context"
)
async def test_generator_selects_correct_prompt_for_farewell_impasse(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Tests prompt selection and parameters for GENERATE_FAREWELL after impasse."""
    state = base_state_for_generator
    action: AgentActionType = "GENERATE_FAREWELL"
    params: AgentActionDetails = {  # Planner provided reason
        "reason": "Impasse on objection: Preço"
    }
    state["next_agent_action_command"] = action
    state["action_parameters"] = params

    common_context_mock = {
        "language": "pt-br",
        "sales_tone": "compreensivo",
        "fallback_text": "site.com/contato",
    }
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Compreendo que não chegamos a um acordo sobre o preço. Agradeço sua honestidade e tempo. Se precisar de algo mais, é só chamar. Tenha um bom dia!"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}
    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    assert (
        "Gere a mensagem de despedida"
        in call_kwargs["prompt"].messages[0].prompt.template
    )

    expected_specific_values = {
        "reason": "Impasse on objection: Preço",
        "fallback_contact_info": "site.com/contato",
    }
    expected_prompt_values = {**common_context_mock, **expected_specific_values}
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None
