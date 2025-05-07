# tests/unit/test_input_processor.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock  # AsyncMock para funções async
from uuid import uuid4
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Importar as funções e classes a serem testadas
from app.services.new_agent.components.input_processor import (
    _format_recent_chat_history,
    _call_structured_llm,  # Mais difícil de testar unitariamente sem um LLM real ou mock complexo
    initial_input_extraction_sub_step,
    check_single_repetition_with_llm,
    analyze_question_repetitions_sub_step,
    process_user_input_node,
)
from app.services.new_agent.schemas.input_analysis import (
    InitialUserInputAnalysis,
    UserInputAnalysisOutput,
    ExtractedQuestionAnalysis,
    InitiallyExtractedQuestion,
    SingleRepetitionCheckOutput,
    SimplifiedCustomerQuestionStatusType,
    PendingAgentActionResponseAnalysis,  # Adicionar se não estiver já
    ExtractedObjection,  # Adicionar
    ExtractedNeedOrPain,  # Adicionar
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    CustomerQuestionEntry,
    PendingAgentAction,
)

from langchain_core.language_models import BaseChatModel

RECENT_HISTORY_LIMIT = 5


# Mock para BaseChatModel se necessário para tipagem
class MockLLM(MagicMock):
    # Simular o método with_structured_output se for usado
    def with_structured_output(self, schema, **kwargs):
        # Retornar um mock que tem um método ainvoke
        structured_llm_mock = AsyncMock()
        # Configurar o que o ainvoke do structured_llm_mock deve retornar
        # Isso dependerá do teste específico
        return structured_llm_mock


@pytest.fixture
def mock_llm_fast():
    # Cria um mock mais completo para BaseChatModel
    llm = MockLLM(spec=BaseChatModel)  # Usar spec para simular a interface

    # Se você for usar with_structured_output, o mock precisa ser mais esperto.
    # Por agora, vamos focar em mockar as funções que chamam o LLM.
    return llm


@pytest.fixture
def minimal_rich_conversation_state():
    """Fixture to provide a minimal valid RichConversationState for tests."""
    # Criar um estado mínimo necessário para process_user_input_node rodar
    return RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={},  # Mock
        agent_config={},  # Mock
        messages=[],  # Será preenchido nos testes
        current_user_input_text="",  # Será preenchido nos testes
        current_turn_number=1,
        current_agent_goal={
            "goal_type": "IDLE",
            "previous_goal_if_interrupted": None,
            "goal_details": None,
        },
        last_agent_action=None,  # Será preenchido nos testes se necessário
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {
                "product": None,
                "agent": None,
                "company": None,
                "last_assessed_turn": None,
            },
        },
        customer_question_log=[],  # Será preenchido nos testes
        current_turn_extracted_questions=[],  # Será preenchido pelo StateUpdater, não aqui
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
    )


# --- Testes para _format_recent_chat_history ---


def test_format_recent_chat_history_empty_list():
    """
    Testa o comportamento quando a lista de mensagens está vazia.
    """
    messages = []
    expected = "Nenhum histórico de conversa recente."
    assert _format_recent_chat_history(messages) == expected
    assert _format_recent_chat_history(messages, limit=3) == expected


def test_format_recent_chat_history_single_message_in_state():
    """
    Testa quando há apenas uma mensagem na lista (a atual do usuário).
    O histórico para o prompt deve estar vazio.
    """
    messages = [HumanMessage(content="Olá, este é o meu primeiro input")]
    # A função pega [-(limit+1):-1]. Se limit=5, pega [-6:-1]. Se len=1, isso é vazio.
    expected = "Esta é a primeira mensagem da conversa."
    assert _format_recent_chat_history(messages, limit=5) == expected


def test_format_recent_chat_history_two_messages():
    """
    Testa com duas mensagens (uma do usuário, uma do agente anterior).
    A mensagem atual do usuário (a última) não deve entrar no histórico formatado.
    """
    messages = [
        HumanMessage(content="Oi"),  # Histórico
        AIMessage(content="Olá! Como posso ajudar?"),  # Atual (não entra no format)
    ]
    expected = "Usuário: Oi"  # Apenas a primeira mensagem entra no histórico do prompt
    assert _format_recent_chat_history(messages, limit=5) == expected


def test_format_recent_chat_history_multiple_messages_within_limit():
    """
    Testa com várias mensagens, todas dentro do limite padrão.
    A última mensagem (atual do usuário) é excluída.
    """
    messages = [
        HumanMessage(content="Qual o preço do produto X?"),
        AIMessage(content="O produto X custa $10."),
        HumanMessage(content="E tem a funcionalidade Y?"),  # Atual (não entra)
    ]
    expected = "Usuário: Qual o preço do produto X?\nAgente: O produto X custa $10."
    assert (
        _format_recent_chat_history(messages, limit=5) == expected
    )  # limit=5 é o padrão


def test_format_recent_chat_history_exceeding_limit():
    """
    Testa quando o número de mensagens excede o limite especificado.
    Apenas as mensagens dentro do limite (excluindo a última) devem ser incluídas.
    """
    messages = [
        HumanMessage(content="Msg 1 - User"),
        AIMessage(content="Msg 2 - AI"),
        HumanMessage(content="Msg 3 - User"),  # Deve ser incluída (limite 2)
        AIMessage(content="Msg 4 - AI"),  # Deve ser incluída (limite 2)
        HumanMessage(content="Msg 5 - User"),  # Atual (não entra)
    ]
    # Queremos as últimas 2 mensagens ANTES da última.
    # O slice é [-(limit+1):-1] = [-3:-1] que pega messages[2] e messages[3]
    expected = "Usuário: Msg 3 - User\nAgente: Msg 4 - AI"
    assert _format_recent_chat_history(messages, limit=2) == expected


def test_format_recent_chat_history_with_system_message_if_present():
    """
    Testa se uma mensagem do sistema no histórico recente é formatada (embora incomum).
    """
    messages = [
        SystemMessage(content="Instrução inicial."),  # Histórico
        HumanMessage(content="Ok, entendi."),  # Histórico
        AIMessage(content="Perfeito."),  # Histórico
        HumanMessage(content="Minha pergunta agora."),  # Atual (não entra)
    ]
    expected = "Sistema: Instrução inicial.\nUsuário: Ok, entendi.\nAgente: Perfeito."
    assert _format_recent_chat_history(messages, limit=5) == expected


def test_format_recent_chat_history_default_limit():
    """
    Testa se o limite padrão (5) é aplicado corretamente.
    """
    messages = [
        HumanMessage(content="1"),
        AIMessage(content="2"),
        HumanMessage(content="3"),
        AIMessage(content="4"),
        HumanMessage(content="5"),
        AIMessage(content="6"),  # Limite 5 pega daqui pra frente (antes da última)
        HumanMessage(content="7"),
        AIMessage(content="8"),
        HumanMessage(content="9"),
        AIMessage(content="10"),
        HumanMessage(content="11"),  # Atual (não entra)
    ]
    # Esperado: 5 últimas trocas ANTES da última mensagem.
    # Slice: [-(5+1):-1] = [-6:-1] -> pega messages[5] a messages[9]
    expected = "Agente: 6\n" "Usuário: 7\n" "Agente: 8\n" "Usuário: 9\n" "Agente: 10"
    assert _format_recent_chat_history(messages) == expected  # Usa limite padrão 5


# --- Testes para check_single_repetition_with_llm ---


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_check_single_repetition_is_repetition(
    mock_call_structured_llm, mock_llm_fast
):
    """
    Testa o caso onde o LLM (mockado) indica que é uma repetição.
    """
    # Configura o mock para retornar o objeto Pydantic esperado
    mock_call_structured_llm.return_value = SingleRepetitionCheckOutput(
        is_semantic_repetition=True
    )

    new_q = "Quanto custa o plano?"
    log_q = "Qual o valor do plano?"

    is_rep = await check_single_repetition_with_llm(new_q, log_q, mock_llm_fast)

    assert is_rep is True
    # Verifica se a função auxiliar foi chamada com os argumentos corretos
    mock_call_structured_llm.assert_called_once()
    call_args, call_kwargs = mock_call_structured_llm.call_args
    assert call_kwargs["llm"] == mock_llm_fast
    assert call_kwargs["output_schema"] == SingleRepetitionCheckOutput
    assert call_kwargs["prompt_values"]["new_question_text"] == new_q
    assert call_kwargs["prompt_values"]["logged_question_core_text"] == log_q


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_check_single_repetition_is_not_repetition(
    mock_call_structured_llm, mock_llm_fast
):
    """
    Testa o caso onde o LLM (mockado) indica que NÃO é uma repetição.
    """
    mock_call_structured_llm.return_value = SingleRepetitionCheckOutput(
        is_semantic_repetition=False
    )

    new_q = "Tem a cor azul?"
    log_q = "Qual o valor do plano?"

    is_rep = await check_single_repetition_with_llm(new_q, log_q, mock_llm_fast)

    assert is_rep is False
    mock_call_structured_llm.assert_called_once()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_check_single_repetition_llm_call_fails(
    mock_call_structured_llm, mock_llm_fast
):
    """
    Testa o caso onde a chamada ao LLM (mockada) falha (retorna None).
    O comportamento esperado é retornar False (não é repetição).
    """
    mock_call_structured_llm.return_value = None  # Simula falha

    new_q = "Quanto custa?"
    log_q = "Qual o preço?"

    is_rep = await check_single_repetition_with_llm(new_q, log_q, mock_llm_fast)

    assert is_rep is False  # Default em caso de falha
    mock_call_structured_llm.assert_called_once()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor._call_structured_llm",
    new_callable=AsyncMock,
)
async def test_check_single_repetition_empty_logged_question(
    mock_call_structured_llm, mock_llm_fast
):
    """
    Testa o caso onde a pergunta do log está vazia. Não deve chamar o LLM.
    """
    new_q = "Quanto custa?"
    log_q = ""  # Logged question vazia

    is_rep = await check_single_repetition_with_llm(new_q, log_q, mock_llm_fast)

    assert is_rep is False
    mock_call_structured_llm.assert_not_called()  # Verifica que o LLM não foi chamado


# --- Testes para analyze_question_repetitions_sub_step ---


@pytest.mark.asyncio
async def test_analyze_repetitions_no_initial_questions_to_analyze(mock_llm_fast):
    """
    Testa o caso onde não há perguntas iniciais para analisar.
    """
    result = await analyze_question_repetitions_sub_step(
        initially_extracted_questions=[],
        customer_question_log=[],
        llm_fast=mock_llm_fast,
        current_turn_number=1,
    )
    assert result == []


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor.check_single_repetition_with_llm",
    new_callable=AsyncMock,
)
async def test_analyze_repetitions_no_log_means_no_repetitions(
    mock_check_repetition, mock_llm_fast
):
    """
    Testa se, com um log de perguntas vazio, nenhuma pergunta é marcada como repetição.
    """
    mock_check_repetition.return_value = (
        False  # Simula que o LLM nunca encontra repetição
    )

    initial_questions = [
        InitiallyExtractedQuestion(question_text="Qual o seu nome?"),
        InitiallyExtractedQuestion(question_text="Quanto custa o produto A?"),
    ]
    customer_log = []  # Log vazio

    result = await analyze_question_repetitions_sub_step(
        initially_extracted_questions=initial_questions,
        customer_question_log=customer_log,
        llm_fast=mock_llm_fast,
        current_turn_number=1,
    )

    assert len(result) == 2
    for analyzed_q in result:
        assert analyzed_q.is_repetition is False
        assert analyzed_q.status_of_original_answer is None
        assert analyzed_q.original_question_turn is None
        assert analyzed_q.original_question_core_text is None

    # Verifica se check_single_repetition_with_llm não foi chamado, pois o log está vazio
    mock_check_repetition.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor.check_single_repetition_with_llm",
    new_callable=AsyncMock,
)
async def test_analyze_repetitions_one_repetition_found(
    mock_check_repetition, mock_llm_fast
):
    """
    Testa um cenário com uma repetição encontrada no log.
    """
    initial_questions = [
        InitiallyExtractedQuestion(
            question_text="Qual o preço do plano X?"
        ),  # Repetição
        InitiallyExtractedQuestion(question_text="Como funciona o suporte?"),  # Nova
    ]
    customer_log = [
        CustomerQuestionEntry(
            original_question_text="Quanto é o plano X?",
            extracted_question_core="Qual o preço do plano X?",  # Match com a primeira nova pergunta
            turn_asked=1,
            status="answered_with_fallback",  # Status da resposta do agente à pergunta original
            agent_direct_response_summary="Não tenho essa info agora.",
            repetition_of_turn=None,
            similarity_vector=None,
        ),
        CustomerQuestionEntry(
            original_question_text="Outra pergunta antiga",
            extracted_question_core="Outra pergunta antiga",
            turn_asked=2,
            status="answered_satisfactorily",
            agent_direct_response_summary="Sim, claro.",
            repetition_of_turn=None,
            similarity_vector=None,
        ),
    ]

    # Configurar o mock para simular o comportamento do LLM de repetição
    # Ele será chamado para cada nova pergunta vs cada pergunta do log (até encontrar match)
    async def side_effect_check_repetition(
        new_question_text, logged_question_core_text, llm_fast
    ):
        if (
            new_question_text == "Qual o preço do plano X?"
            and logged_question_core_text == "Qual o preço do plano X?"
        ):
            return True  # É uma repetição
        return False  # Não é repetição para outros pares

    mock_check_repetition.side_effect = side_effect_check_repetition

    result = await analyze_question_repetitions_sub_step(
        initially_extracted_questions=initial_questions,
        customer_question_log=customer_log,
        llm_fast=mock_llm_fast,
        current_turn_number=3,  # Turno atual da análise
    )

    assert len(result) == 2

    # Verificar a pergunta repetida
    assert result[0].question_text == "Qual o preço do plano X?"
    assert result[0].is_repetition is True
    assert (
        result[0].status_of_original_answer == "answered_with_fallback"
    )  # Mapeado do log_entry.status
    assert result[0].original_question_turn == 1
    assert result[0].original_question_core_text == "Qual o preço do plano X?"

    # Verificar a pergunta nova
    assert result[1].question_text == "Como funciona o suporte?"
    assert result[1].is_repetition is False
    assert result[1].status_of_original_answer is None
    assert result[1].original_question_turn is None
    assert result[1].original_question_core_text is None

    # Verificar quantas vezes o mock foi chamado.
    # Para "Qual o preço do plano X?":
    #   - Compara com "Outra pergunta antiga" (log[1]) -> False
    #   - Compara com "Qual o preço do plano X?" (log[0]) -> True (para aqui)
    # Para "Como funciona o suporte?":
    #   - Compara com "Outra pergunta antiga" (log[1]) -> False
    #   - Compara com "Qual o preço do plano X?" (log[0]) -> False
    # Total de 4 chamadas
    assert mock_check_repetition.call_count == (
        2 + 2
    )  # 2 para a primeira (match), 2 para a segunda (no match)


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor.check_single_repetition_with_llm",
    new_callable=AsyncMock,
)
async def test_analyze_repetitions_maps_status_correctly(
    mock_check_repetition, mock_llm_fast
):
    """
    Testa o mapeamento de diferentes CustomerQuestionStatusType para SimplifiedCustomerQuestionStatusType.
    """
    initial_questions = [InitiallyExtractedQuestion(question_text="Pergunta repetida")]

    # Mock check_single_repetition_with_llm para sempre retornar True
    mock_check_repetition.return_value = True

    log_entry_satisfied = CustomerQuestionEntry(
        extracted_question_core="Pergunta repetida",
        turn_asked=1,
        status="answered_satisfactorily",
        original_question_text="",
        agent_direct_response_summary=None,
        repetition_of_turn=None,
        similarity_vector=None,
    )
    log_entry_fallback = CustomerQuestionEntry(
        extracted_question_core="Pergunta repetida",
        turn_asked=2,
        status="answered_with_fallback",
        original_question_text="",
        agent_direct_response_summary=None,
        repetition_of_turn=None,
        similarity_vector=None,
    )
    log_entry_newly_asked_in_log = (
        CustomerQuestionEntry(  # Status que mapeia para unknown
            extracted_question_core="Pergunta repetida",
            turn_asked=3,
            status="newly_asked",
            original_question_text="",
            agent_direct_response_summary=None,
            repetition_of_turn=None,
            similarity_vector=None,
        )
    )

    # Teste com status "answered_satisfactorily"
    result_satisfied = await analyze_question_repetitions_sub_step(
        initial_questions, [log_entry_satisfied], mock_llm_fast, 4
    )
    assert result_satisfied[0].status_of_original_answer == "answered_satisfactorily"

    # Teste com status "answered_with_fallback"
    result_fallback = await analyze_question_repetitions_sub_step(
        initial_questions, [log_entry_fallback], mock_llm_fast, 4
    )
    assert result_fallback[0].status_of_original_answer == "answered_with_fallback"

    # Teste com status que deve mapear para "unknown_previous_status"
    result_unknown = await analyze_question_repetitions_sub_step(
        initial_questions, [log_entry_newly_asked_in_log], mock_llm_fast, 4
    )
    assert result_unknown[0].status_of_original_answer == "unknown_previous_status"


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor.check_single_repetition_with_llm",
    new_callable=AsyncMock,
)
async def test_analyze_repetitions_uses_most_recent_log_match(
    mock_check_repetition, mock_llm_fast
):
    """
    Testa se a função usa o status da correspondência MAIS RECENTE no log,
    caso uma pergunta tenha sido feita e respondida de formas diferentes anteriormente.
    """
    initial_questions = [InitiallyExtractedQuestion(question_text="Qual o status?")]

    # Mock check_single_repetition_with_llm para sempre retornar True
    mock_check_repetition.return_value = True

    customer_log = [
        CustomerQuestionEntry(  # Entrada mais antiga
            extracted_question_core="Qual o status?",
            turn_asked=1,
            status="answered_with_fallback",
            original_question_text="",
            agent_direct_response_summary=None,
            repetition_of_turn=None,
            similarity_vector=None,
        ),
        CustomerQuestionEntry(  # Entrada mais recente com o mesmo texto
            extracted_question_core="Qual o status?",
            turn_asked=3,
            status="answered_satisfactorily",
            original_question_text="",
            agent_direct_response_summary=None,
            repetition_of_turn=None,
            similarity_vector=None,
        ),
    ]
    # O log é ordenado internamente pela função do mais recente para o mais antigo.
    # Então, a entrada do turno 3 deve ser encontrada primeiro.

    result = await analyze_question_repetitions_sub_step(
        initial_questions, customer_log, mock_llm_fast, 4  # Turno atual
    )

    assert len(result) == 1
    assert result[0].is_repetition is True
    assert (
        result[0].original_question_turn == 3
    )  # Deve pegar o turno da entrada mais recente
    assert (
        result[0].status_of_original_answer == "answered_satisfactorily"
    )  # Status da entrada mais recente


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor.initial_input_extraction_sub_step",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.input_processor.analyze_question_repetitions_sub_step",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.input_processor._format_recent_chat_history"
)  # Mockar também o formatador
async def test_process_user_input_node_success_flow(
    mock_format_history,  # Mock injetado
    mock_analyze_repetitions,  # Mock injetado
    mock_initial_extraction,  # Mock injetado
    mock_llm_fast,  # Fixture
    minimal_rich_conversation_state,  # Fixture
):
    """
    Testa o fluxo de sucesso do nó principal, mockando as sub-etapas.
    """
    # --- Configuração dos Mocks ---
    # 1. Mock para _format_recent_chat_history
    mock_format_history.return_value = "Histórico Formatado Mock"

    # 2. Mock para initial_input_extraction_sub_step
    mock_initial_result = InitialUserInputAnalysis(
        overall_intent="Questioning",
        initially_extracted_questions=[
            InitiallyExtractedQuestion(question_text="Qual o preço?")
        ],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
    )
    mock_initial_extraction.return_value = mock_initial_result

    # 3. Mock para analyze_question_repetitions_sub_step
    mock_repetition_result = [
        ExtractedQuestionAnalysis(
            question_text="Qual o preço?",
            is_repetition=False,
            status_of_original_answer=None,
            original_question_turn=None,
            original_question_core_text=None,
        )
    ]
    mock_analyze_repetitions.return_value = mock_repetition_result

    # --- Preparação do Estado e Configuração ---
    test_state = minimal_rich_conversation_state
    test_state["current_user_input_text"] = "Qual o preço?"
    test_state["messages"] = [HumanMessage(content="Qual o preço?")]
    test_state["current_turn_number"] = 5  # Exemplo
    test_state["customer_question_log"] = []  # Exemplo de log vazio
    test_state["last_agent_action"] = PendingAgentAction(  # Exemplo de ação anterior
        action_type="GENERATE_GREETING",
        details={},
        action_generation_text="Olá, bem-vindo!",
        attempts=1,
    )

    test_config = {"configurable": {"llm_fast_instance": mock_llm_fast}}

    # --- Execução ---
    result_dict = await process_user_input_node(test_state, test_config)

    # --- Asserts ---
    # Verificar se as funções mockadas foram chamadas corretamente
    mock_format_history.assert_called_once_with(
        test_state["messages"], limit=RECENT_HISTORY_LIMIT
    )

    mock_initial_extraction.assert_called_once_with(
        last_user_message_text=test_state["current_user_input_text"],
        last_agent_action_text=test_state["last_agent_action"][
            "action_generation_text"
        ],
        recent_chat_history_str="Histórico Formatado Mock",
        llm_fast=mock_llm_fast,
    )

    mock_analyze_repetitions.assert_called_once_with(
        initially_extracted_questions=mock_initial_result.initially_extracted_questions,
        customer_question_log=test_state["customer_question_log"],
        llm_fast=mock_llm_fast,
        current_turn_number=test_state["current_turn_number"],
    )

    # Verificar o resultado retornado
    assert "user_input_analysis_result" in result_dict
    assert "last_processing_error" not in result_dict
    # assert result_dict["last_processing_error"] is None  # Espera sucesso

    # Validar o conteúdo do resultado (opcional, mas bom)
    final_analysis = UserInputAnalysisOutput.model_validate(
        result_dict["user_input_analysis_result"]
    )
    assert final_analysis.overall_intent == "Questioning"
    assert len(final_analysis.extracted_questions) == 1
    assert final_analysis.extracted_questions[0].question_text == "Qual o preço?"
    assert final_analysis.extracted_questions[0].is_repetition is False


@pytest.mark.asyncio
async def test_process_user_input_node_no_llm_in_config(
    minimal_rich_conversation_state,
):
    """
    Testa o caso onde o llm_fast não está na configuração.
    """
    test_state = minimal_rich_conversation_state
    test_state["current_user_input_text"] = "Olá"
    test_config = {"configurable": {}}  # Sem llm_fast_instance

    result_dict = await process_user_input_node(test_state, test_config)

    assert result_dict.get("user_input_analysis_result") is None
    assert "LLM for input processing unavailable" in result_dict.get(
        "last_processing_error", ""
    )


@pytest.mark.asyncio
async def test_process_user_input_node_no_input_text(
    minimal_rich_conversation_state, mock_llm_fast
):
    """
    Testa o caso onde current_user_input_text está vazio no estado.
    """
    test_state = minimal_rich_conversation_state
    test_state["current_user_input_text"] = ""  # Input vazio
    test_config = {"configurable": {"llm_fast_instance": mock_llm_fast}}

    result_dict = await process_user_input_node(test_state, test_config)

    assert result_dict.get("user_input_analysis_result") is None
    assert (
        result_dict.get("last_processing_error") is None
    )  # Não é um erro, apenas skip


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.input_processor.initial_input_extraction_sub_step",
    new_callable=AsyncMock,
)
@patch("app.services.new_agent.components.input_processor._format_recent_chat_history")
async def test_process_user_input_node_initial_extraction_fails(
    mock_format_history,
    mock_initial_extraction,
    mock_llm_fast,
    minimal_rich_conversation_state,
):
    """
    Testa o caso onde a primeira sub-etapa (extração inicial) falha.
    """
    mock_format_history.return_value = "Histórico"
    mock_initial_extraction.return_value = None  # Simula falha

    test_state = minimal_rich_conversation_state
    test_state["current_user_input_text"] = "Pergunta?"
    test_state["messages"] = [HumanMessage(content="Pergunta?")]
    test_config = {"configurable": {"llm_fast_instance": mock_llm_fast}}

    result_dict = await process_user_input_node(test_state, test_config)

    assert result_dict.get("user_input_analysis_result") is None
    assert "Initial input extraction LLM call failed" in result_dict.get(
        "last_processing_error", ""
    )
