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
    params: AgentActionDetails = {"question_to_answer_text": "Qual o horário?"}
    state["next_agent_action_command"] = action
    state["action_parameters"] = params
    state["retrieved_knowledge_for_next_action"] = (
        "RAG Context: Abrimos às 9h."  # Simular RAG
    )

    common_context_mock = {
        "company_name": "Test",
        "language": "pt",
        "sales_tone": "test",
        "rag_context": "RAG Context: Abrimos às 9h.",
    }
    mock_prepare_context.return_value = (
        common_context_mock  # Mock deve incluir rag_context
    )
    expected_llm_response = "Nosso horário é das 9h às 18h."
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert isinstance(call_kwargs["prompt"], ChatPromptTemplate)
    assert "'{question_to_answer}'" in call_kwargs["prompt"].messages[0].prompt.template

    expected_prompt_values = {
        **common_context_mock,
        **{"question_to_answer": "Qual o horário?"},
    }
    # Remover rag_context duplicado se _prepare_common_prompt_context já o inclui
    if "rag_context" in common_context_mock:
        expected_prompt_values["rag_context"] = common_context_mock["rag_context"]

    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None


# Adicionar testes similares para:
# - GENERATE_REBUTTAL
# - ASK_CLARIFYING_QUESTION
# - ACKNOWLEDGE_AND_TRANSITION


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
    params: AgentActionDetails = {}  # Parâmetros podem estar vazios, texto vem do goal
    state["next_agent_action_command"] = action
    state["action_parameters"] = params
    # Simular o texto vago no goal_details
    state["current_agent_goal"] = AgentGoal(
        goal_type="CLARIFYING_USER_INPUT",
        goal_details={"text": "Isso parece confuso."},
        previous_goal_if_interrupted=None,
    )

    common_context_mock = {"company_name": "Test"}
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Poderia me dizer o que especificamente pareceu confuso?"
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert call_kwargs["prompt"] == PROMPT_ASK_CLARIFYING_QUESTION

    expected_prompt_values = {
        **common_context_mock,
        **{"vague_statement_text": "Isso parece confuso."},
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
async def test_generator_selects_correct_prompt_for_ack_transition(
    mock_prepare_context, mock_call_llm, base_state_for_generator, mock_llm_primary
):
    """Testa se o prompt ACKNOWLEDGE_AND_TRANSITION correto é selecionado."""
    state = base_state_for_generator
    action: AgentActionType = "ACKNOWLEDGE_AND_TRANSITION"
    params: AgentActionDetails = {}  # Parâmetros vazios, contexto vem do goal
    state["next_agent_action_command"] = action
    state["action_parameters"] = params
    # Simular o goal atual e o anterior
    previous_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={"topic": "desafios atuais"},
        previous_goal_if_interrupted=None,
    )
    state["current_agent_goal"] = AgentGoal(
        goal_type="ACKNOWLEDGE_AND_TRANSITION",  # Ou o goal temporário definido pelo planner
        goal_details={"text": "Falando nisso, viu o jogo?"},  # Texto off-topic
        previous_goal_if_interrupted=previous_goal,
    )

    common_context_mock = {"company_name": "Test"}
    mock_prepare_context.return_value = common_context_mock
    expected_llm_response = "Entendido. Voltando aos desafios atuais que mencionou..."
    mock_call_llm.return_value = expected_llm_response

    config = {"configurable": {"llm_primary_instance": mock_llm_primary}}

    delta = await response_generator_node(state, config)

    mock_prepare_context.assert_called_once_with(state)
    mock_call_llm.assert_called_once()
    call_args, call_kwargs = mock_call_llm.call_args

    assert call_kwargs["prompt"] == PROMPT_ACKNOWLEDGE_AND_TRANSITION

    expected_prompt_values = {
        **common_context_mock,
        **{
            "off_topic_text": "Falando nisso, viu o jogo?",
            "previous_goal_topic": "desafios atuais",  # Extraído do previous_goal
        },
    }
    assert call_kwargs["prompt_values"] == expected_prompt_values
    assert call_kwargs["llm"] == mock_llm_primary

    assert delta.get("last_agent_generation_text") == expected_llm_response
    assert delta.get("last_processing_error") is None
