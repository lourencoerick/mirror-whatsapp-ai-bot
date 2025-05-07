# tests/unit/test_state_updater.py

import pytest
import time
import copy
from uuid import uuid4
from unittest.mock import (
    patch,
    AsyncMock,
)  # AsyncMock para mockar a função async de log

# Importar a função a ser testada e as definições/schemas necessários
from app.services.new_agent.components.state_updater import (
    update_conversation_state_node,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    CustomerQuestionEntry,
    UserInterruption,
    IdentifiedObjectionEntry,
    IdentifiedNeedEntry,
    IdentifiedPainPointEntry,
    DynamicCustomerProfile,
    CustomerQuestionStatusType,
    ObjectionStatusType,
    AgentGoal,  # Importar se necessário para criar estado inicial
    PendingAgentAction,  # Importar se necessário
)
from app.services.new_agent.schemas.input_analysis import (
    UserInputAnalysisOutput,
    ExtractedQuestionAnalysis,
    ExtractedObjection,
    ExtractedNeedOrPain,
    PendingAgentActionResponseAnalysis,
    SimplifiedCustomerQuestionStatusType,  # Usado na análise de entrada
)

# --- Fixtures ---


@pytest.fixture
def base_state() -> RichConversationState:
    """Provides a base, empty RichConversationState."""
    # Usar deepcopy para garantir que cada teste obtenha uma cópia fresca
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={"company_name": "Test Co"},
        agent_config={},
        messages=[],
        current_user_input_text="",
        current_turn_number=0,
        current_agent_goal={
            "goal_type": "IDLE",
            "previous_goal_if_interrupted": None,
            "goal_details": None,
        },
        last_agent_action=None,
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
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time(),
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        # Adicionar a chave que o nó espera encontrar
        user_input_analysis_result=None,
    )
    return copy.deepcopy(state)


@pytest.fixture
def mock_analysis_new_question() -> UserInputAnalysisOutput:
    """Analysis result for a simple new question."""
    return UserInputAnalysisOutput(
        overall_intent="Questioning",
        extracted_questions=[
            ExtractedQuestionAnalysis(
                question_text="Qual o horário de funcionamento?",
                is_repetition=False,
                status_of_original_answer=None,
                original_question_turn=None,
                original_question_core_text=None,
            )
        ],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_repeated_question_fallback() -> UserInputAnalysisOutput:
    """Analysis result for a repeated question where original answer was fallback."""
    return UserInputAnalysisOutput(
        overall_intent="Questioning",
        extracted_questions=[
            ExtractedQuestionAnalysis(
                question_text="Qual o preço exato do plano Pro?",
                is_repetition=True,
                status_of_original_answer="answered_with_fallback",  # <<< Importante
                original_question_turn=2,  # <<< Turno da pergunta original
                original_question_core_text="Qual o preço exato do plano Pro?",  # <<< Texto original
            )
        ],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="ignored_agent_action"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_new_objection_and_need() -> UserInputAnalysisOutput:
    """Analysis result with a new objection and a need."""
    return UserInputAnalysisOutput(
        overall_intent="ExpressingObjection",  # Ou poderia ser misto
        extracted_questions=[],
        extracted_objections=[
            ExtractedObjection(
                objection_text="Acho que é muito caro para meu orçamento atual."
            )
        ],
        extracted_needs_or_pains=[
            ExtractedNeedOrPain(
                text="Preciso de algo que me economize tempo.", type="need"
            )
        ],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_multiple_questions() -> UserInputAnalysisOutput:
    """Analysis with multiple questions: new, rep(fallback), rep(satisfactory)."""
    return UserInputAnalysisOutput(
        overall_intent="Questioning",
        extracted_questions=[
            ExtractedQuestionAnalysis(  # Repetição após Fallback
                question_text="Qual o preço exato do plano Pro?",
                is_repetition=True,
                status_of_original_answer="answered_with_fallback",
                original_question_turn=2,
                original_question_core_text="Qual o preço exato do plano Pro?",
            ),
            ExtractedQuestionAnalysis(  # Nova Pergunta
                question_text="Qual o prazo de entrega?",
                is_repetition=False,
                status_of_original_answer=None,
                original_question_turn=None,
                original_question_core_text=None,
            ),
            ExtractedQuestionAnalysis(  # Repetição após Satisfatória
                question_text="Como funciona o suporte?",
                is_repetition=True,
                status_of_original_answer="answered_satisfactorily",
                original_question_turn=3,
                original_question_core_text="Como funciona o suporte?",
            ),
        ],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="ignored_agent_action"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_multiple_needs_objections() -> UserInputAnalysisOutput:
    """Analysis with multiple needs and objections."""
    return UserInputAnalysisOutput(
        overall_intent="ExpressingObjection",  # Pode variar
        extracted_questions=[],
        extracted_objections=[
            ExtractedObjection(objection_text="O preço ainda me parece alto."),
            ExtractedObjection(
                objection_text="Não tenho certeza sobre o tempo de implementação."
            ),
        ],
        extracted_needs_or_pains=[
            ExtractedNeedOrPain(text="Preciso de relatórios melhores.", type="need"),
            ExtractedNeedOrPain(
                text="Gasto muito tempo com tarefas manuais.", type="pain_point"
            ),
        ],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_repeated_question_satisfactory() -> UserInputAnalysisOutput:
    """Analysis result for a repeated question where original answer was satisfactory."""
    return UserInputAnalysisOutput(
        overall_intent="Questioning",
        extracted_questions=[
            ExtractedQuestionAnalysis(
                question_text="Como funciona o suporte mesmo?",  # Repetição
                is_repetition=True,
                status_of_original_answer="answered_satisfactorily",  # <<< Importante
                original_question_turn=3,
                original_question_core_text="Como funciona o suporte?",
            )
        ],
        # ... outros campos vazios ...
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_duplicate_objection() -> UserInputAnalysisOutput:
    """Analysis containing an objection already present in the state."""
    return UserInputAnalysisOutput(
        overall_intent="ExpressingObjection",
        extracted_questions=[],
        extracted_objections=[
            ExtractedObjection(
                objection_text="O preço ainda me parece alto."
            )  # Objeção duplicada
        ],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_vague_statement() -> UserInputAnalysisOutput:
    """Analysis indicating a vague statement."""
    return UserInputAnalysisOutput(
        overall_intent="VagueOrUnclear",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=True,  # <<< Importante
        is_primarily_off_topic=False,
    )


@pytest.fixture
def mock_analysis_off_topic() -> UserInputAnalysisOutput:
    """Analysis indicating an off-topic comment."""
    return UserInputAnalysisOutput(
        overall_intent="OffTopic",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=True,  # <<< Importante
    )


# --- Testes ---


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_no_analysis_result(mock_log_event, base_state):
    """Test that the node handles the case where analysis result is missing."""
    state = base_state
    state["user_input_analysis_result"] = None  # Garantir que está None

    delta = await update_conversation_state_node(state, {})

    # Espera que o erro anterior seja limpo e o turno incrementado
    assert delta.get("last_processing_error") is None
    assert (
        delta.get("current_turn_number") == 1
    )  # Incrementa mesmo se não houver análise
    assert delta.get("customer_question_log") is None  # Nenhuma mudança no log
    assert delta.get("user_interruptions_queue") is None  # Nenhuma mudança na fila
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_invalid_analysis_result(mock_log_event, base_state):
    """Test that the node handles invalid analysis data."""
    state = base_state
    state["user_input_analysis_result"] = {
        "overall_intent": "Questioning",
        "invalid_field": "foo",
    }  # Dado inválido

    delta = await update_conversation_state_node(state, {})

    assert "last_processing_error" in delta
    assert (
        "State update failed: Invalid input analysis data"
        in delta["last_processing_error"]
    )
    assert (
        delta.get("current_turn_number") is None
    )  # Não deve incrementar turno se falhou na validação
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_new_question_added(
    mock_log_event, base_state, mock_analysis_new_question
):
    """Test adding a new question to the log and interruption queue."""
    state = base_state
    state["user_input_analysis_result"] = mock_analysis_new_question.model_dump()
    state["current_turn_number"] = 3  # Turno atual antes da atualização

    delta = await update_conversation_state_node(state, {})

    # Verificar delta
    assert delta.get("current_turn_number") == 4
    assert delta.get("last_processing_error") is None
    assert delta.get("user_input_analysis_result") is None  # Deve ser limpo

    # Verificar log de perguntas
    assert "customer_question_log" in delta
    new_log = delta["customer_question_log"]
    assert len(new_log) == 1
    assert new_log[0]["extracted_question_core"] == "Qual o horário de funcionamento?"
    assert (
        new_log[0]["turn_asked"] == 4
    )  # Adicionado no próximo turno (após processar o input do turno 3)
    assert new_log[0]["status"] == "newly_asked"

    # Verificar fila de interrupções
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "direct_question"
    assert interrupt_queue[0]["text"] == "Qual o horário de funcionamento?"
    assert interrupt_queue[0]["status"] == "pending_resolution"
    assert interrupt_queue[0]["turn_detected"] == 4

    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_repeated_question_updates_log_and_triggers_event(
    mock_log_event, base_state, mock_analysis_repeated_question_fallback
):
    """Test updating a repeated question in the log and triggering the missing info event."""
    state = base_state
    state["current_turn_number"] = 5
    # Adicionar a pergunta original ao log
    original_question = CustomerQuestionEntry(
        original_question_text="Quanto é o Pro?",
        extracted_question_core="Qual o preço exato do plano Pro?",  # Match com a análise
        turn_asked=2,  # Turno original da análise
        status="answered_with_fallback",  # Status original
        agent_direct_response_summary="Não sei.",
        repetition_of_turn=None,
        similarity_vector=None,
    )
    state["customer_question_log"] = [original_question]
    state["user_input_analysis_result"] = (
        mock_analysis_repeated_question_fallback.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    # Verificar delta
    assert delta.get("current_turn_number") == 6
    assert delta.get("last_processing_error") is None
    assert delta.get("user_input_analysis_result") is None

    # Verificar log de perguntas (deve ter atualizado a entrada existente)
    assert "customer_question_log" in delta
    updated_log = delta["customer_question_log"]
    assert len(updated_log) == 1  # Não adicionou nova, atualizou a existente
    assert updated_log[0]["turn_asked"] == 2  # Turno original mantido
    assert (
        updated_log[0]["extracted_question_core"] == "Qual o preço exato do plano Pro?"
    )
    # Status atualizado para indicar repetição após fallback
    assert updated_log[0]["status"] == "repetition_after_fallback"

    # Verificar fila de interrupções
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "direct_question"
    assert interrupt_queue[0]["text"] == "Qual o preço exato do plano Pro?"
    assert interrupt_queue[0]["status"] == "pending_resolution"
    assert interrupt_queue[0]["turn_detected"] == 6

    # Verificar se o evento de log foi chamado
    mock_log_event.assert_called_once_with(
        state["account_id"],
        state["conversation_id"],
        "Qual o preço exato do plano Pro?",  # O texto da pergunta repetida
    )


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_new_objection_and_need_added(
    mock_log_event, base_state, mock_analysis_new_objection_and_need
):
    """Test adding new objection and need to the dynamic profile and interruption queue."""
    state = base_state
    state["user_input_analysis_result"] = (
        mock_analysis_new_objection_and_need.model_dump()
    )
    state["current_turn_number"] = 1

    delta = await update_conversation_state_node(state, {})

    # Verificar delta
    assert delta.get("current_turn_number") == 2
    assert delta.get("last_processing_error") is None
    assert delta.get("user_input_analysis_result") is None

    # Verificar perfil dinâmico
    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert len(dynamic_profile["identified_objections"]) == 1
    assert (
        dynamic_profile["identified_objections"][0]["text"]
        == "Acho que é muito caro para meu orçamento atual."
    )
    assert dynamic_profile["identified_objections"][0]["status"] == "active"
    assert dynamic_profile["identified_objections"][0]["source_turn"] == 2

    assert len(dynamic_profile["identified_needs"]) == 1
    assert (
        dynamic_profile["identified_needs"][0]["text"]
        == "Preciso de algo que me economize tempo."
    )
    assert dynamic_profile["identified_needs"][0]["status"] == "active"
    assert dynamic_profile["identified_needs"][0]["source_turn"] == 2

    # Verificar fila de interrupções (apenas objeção é adicionada como interrupção por padrão)
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "objection"
    assert (
        interrupt_queue[0]["text"] == "Acho que é muito caro para meu orçamento atual."
    )
    assert interrupt_queue[0]["status"] == "pending_resolution"
    assert interrupt_queue[0]["turn_detected"] == 2

    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_multiple_question_types(
    mock_log_event, base_state, mock_analysis_multiple_questions
):
    """Tests handling of multiple questions with different repetition statuses."""
    state = base_state
    state["current_turn_number"] = 4
    # Log pré-existente com as perguntas originais
    state["customer_question_log"] = [
        CustomerQuestionEntry(  # Original da repetição fallback
            extracted_question_core="Qual o preço exato do plano Pro?",
            turn_asked=2,
            status="answered_with_fallback",
            original_question_text="",
            agent_direct_response_summary=None,
            repetition_of_turn=None,
            similarity_vector=None,
        ),
        CustomerQuestionEntry(  # Original da repetição satisfatória
            extracted_question_core="Como funciona o suporte?",
            turn_asked=3,
            status="answered_satisfactorily",
            original_question_text="",
            agent_direct_response_summary=None,
            repetition_of_turn=None,
            similarity_vector=None,
        ),
    ]
    state["user_input_analysis_result"] = mock_analysis_multiple_questions.model_dump()

    delta = await update_conversation_state_node(state, {})

    # Verificar delta básico
    assert delta.get("current_turn_number") == 5
    assert delta.get("last_processing_error") is None
    assert delta.get("user_input_analysis_result") is None

    # Verificar log de perguntas (deve ter 3 entradas: 2 atualizadas, 1 nova)
    assert "customer_question_log" in delta
    updated_log = delta["customer_question_log"]
    assert len(updated_log) == 3

    q_price = next(
        (q for q in updated_log if "preço" in q["extracted_question_core"]), None
    )
    q_delivery = next(
        (q for q in updated_log if "entrega" in q["extracted_question_core"]), None
    )
    q_support = next(
        (q for q in updated_log if "suporte" in q["extracted_question_core"]), None
    )

    assert q_price is not None
    assert q_price["turn_asked"] == 2  # Turno original mantido
    assert q_price["status"] == "repetition_after_fallback"  # Status atualizado

    assert q_delivery is not None
    assert q_delivery["turn_asked"] == 5  # Turno novo
    assert q_delivery["status"] == "newly_asked"  # Status novo

    assert q_support is not None
    assert q_support["turn_asked"] == 3  # Turno original mantido
    assert (
        q_support["status"] == "repetition_after_satisfactory_answer"
    )  # Status atualizado

    # Verificar fila de interrupções (todas as 3 devem estar lá)
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 3
    texts_in_queue = {
        item["text"] for item in interrupt_queue if item["type"] == "direct_question"
    }
    assert "Qual o preço exato do plano Pro?" in texts_in_queue
    assert "Qual o prazo de entrega?" in texts_in_queue
    assert "Como funciona o suporte?" in texts_in_queue
    for item in interrupt_queue:
        assert item["status"] == "pending_resolution"
        assert item["turn_detected"] == 5

    # Verificar evento de log (chamado apenas para a repetição após fallback)
    mock_log_event.assert_called_once_with(
        state["account_id"],
        state["conversation_id"],
        "Qual o preço exato do plano Pro?",
    )


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_multiple_needs_objections(
    mock_log_event, base_state, mock_analysis_multiple_needs_objections
):
    """Tests adding multiple needs and objections simultaneously."""
    state = base_state
    state["user_input_analysis_result"] = (
        mock_analysis_multiple_needs_objections.model_dump()
    )
    state["current_turn_number"] = 2

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 3
    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert len(dynamic_profile["identified_objections"]) == 2
    assert len(dynamic_profile["identified_needs"]) == 1
    assert len(dynamic_profile["identified_pain_points"]) == 1

    objection_texts = {o["text"] for o in dynamic_profile["identified_objections"]}
    assert "O preço ainda me parece alto." in objection_texts
    assert "Não tenho certeza sobre o tempo de implementação." in objection_texts

    assert (
        dynamic_profile["identified_needs"][0]["text"]
        == "Preciso de relatórios melhores."
    )
    assert (
        dynamic_profile["identified_pain_points"][0]["text"]
        == "Gasto muito tempo com tarefas manuais."
    )

    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    # Apenas objeções devem ir para a fila por padrão neste teste
    assert len(interrupt_queue) == 2
    interrupt_texts = {i["text"] for i in interrupt_queue if i["type"] == "objection"}
    assert "O preço ainda me parece alto." in interrupt_texts
    assert "Não tenho certeza sobre o tempo de implementação." in interrupt_texts

    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_repeated_question_satisfactory(
    mock_log_event, base_state, mock_analysis_repeated_question_satisfactory
):
    """Tests updating log for repetition after satisfactory answer."""
    state = base_state
    state["current_turn_number"] = 5
    # Adicionar a pergunta original ao log
    original_question = CustomerQuestionEntry(
        extracted_question_core="Como funciona o suporte?",
        turn_asked=3,
        status="answered_satisfactorily",  # <<< Status Original
        original_question_text="",
        agent_direct_response_summary=None,
        repetition_of_turn=None,
        similarity_vector=None,
    )
    state["customer_question_log"] = [original_question]
    state["user_input_analysis_result"] = (
        mock_analysis_repeated_question_satisfactory.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 6
    assert "customer_question_log" in delta
    updated_log = delta["customer_question_log"]
    assert len(updated_log) == 1
    assert updated_log[0]["turn_asked"] == 3
    # Status atualizado para indicar repetição após resposta satisfatória
    assert updated_log[0]["status"] == "repetition_after_satisfactory_answer"

    # Verificar fila de interrupções (ainda deve ser adicionada)
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "direct_question"
    assert interrupt_queue[0]["text"] == "Como funciona o suporte mesmo?"

    # Evento NÃO deve ser chamado
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_duplicate_objection_ignored(
    mock_log_event, base_state, mock_analysis_duplicate_objection
):
    """Tests that an already active objection is not added again."""
    state = base_state
    state["current_turn_number"] = 4
    # Adicionar a objeção pré-existente ao perfil dinâmico e à fila
    existing_objection_text = "O preço ainda me parece alto."
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=existing_objection_text,
            status="active",
            rebuttal_attempts=0,
            source_turn=2,
            related_to_proposal=None,
        )
    ]
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="objection",
            text=existing_objection_text,
            status="pending_resolution",
            turn_detected=2,
        )
    ]
    state["user_input_analysis_result"] = mock_analysis_duplicate_objection.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 5

    # Verificar perfil dinâmico - NÃO deve ter sido adicionado ao delta, pois não mudou
    assert "customer_profile_dynamic" not in delta
    # Verificar o estado completo (se pudéssemos) mostraria que a lista ainda tem 1 objeção

    # Verificar fila de interrupções - NÃO deve ter sido adicionado ao delta
    assert "user_interruptions_queue" not in delta
    # Verificar o estado completo (se pudéssemos) mostraria que a fila ainda tem 1 interrupção

    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_vague_statement_added_to_queue(
    mock_log_event, base_state, mock_analysis_vague_statement
):
    """Tests that a vague statement adds an interruption to the queue."""
    state = base_state
    state["current_turn_number"] = 1
    state["current_user_input_text"] = "Hmm, não sei..."  # Texto vago original
    state["user_input_analysis_result"] = mock_analysis_vague_statement.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 2
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "vague_statement"
    assert interrupt_queue[0]["text"] == "Hmm, não sei..."  # Texto completo da msg
    assert interrupt_queue[0]["status"] == "pending_resolution"
    assert interrupt_queue[0]["turn_detected"] == 2

    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_update_state_off_topic_added_to_queue(
    mock_log_event, base_state, mock_analysis_off_topic
):
    """Tests that an off-topic comment adds an interruption to the queue."""
    state = base_state
    state["current_turn_number"] = 3
    state["current_user_input_text"] = (
        "Falando em outra coisa, viu o jogo ontem?"  # Texto off-topic
    )
    state["user_input_analysis_result"] = mock_analysis_off_topic.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "off_topic_comment"
    assert interrupt_queue[0]["text"] == "Falando em outra coisa, viu o jogo ontem?"
    assert interrupt_queue[0]["status"] == "pending_resolution"
    assert interrupt_queue[0]["turn_detected"] == 4

    mock_log_event.assert_not_called()
