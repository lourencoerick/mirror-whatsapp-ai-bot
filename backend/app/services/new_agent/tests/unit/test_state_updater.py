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
    ReactionToPresentation,
    ObjectionAfterRebuttalStatus,
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
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
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
    )


@pytest.fixture
def mock_analysis_obj_resolved() -> UserInputAnalysisOutput:
    """Analysis: objection was handled and appears resolved."""
    return UserInputAnalysisOutput(
        overall_intent="PositiveFeedback",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            original_objection_text_handled="O preço é alto.",
            status="appears_resolved",
            new_objection_text=None,
        ),
    )


@pytest.fixture
def mock_analysis_obj_persists() -> UserInputAnalysisOutput:
    return UserInputAnalysisOutput(
        overall_intent="ExpressingObjection",
        extracted_questions=[],
        extracted_objections=[],  # <<< MUDANÇA: Assumir que o InputProcessor não extrai a mesma objeção aqui
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="ignored_agent_action"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            original_objection_text_handled="O preço é alto.",  # A objeção original
            status="still_persists",
            new_objection_text=None,  # Ou poderia ser "Mas ainda acho caro." se o LLM identificasse a reformulação
        ),
    )


@pytest.fixture
def mock_analysis_obj_new_raised_after_rebuttal() -> UserInputAnalysisOutput:
    """Analysis: a new objection was raised after a rebuttal to an old one."""
    return UserInputAnalysisOutput(
        overall_intent="ExpressingObjection",
        extracted_objections=[
            ExtractedObjection(objection_text="E sobre o tempo de contrato?")
        ],  # A nova objeção
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="ignored_agent_action"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            original_objection_text_handled="O preço é alto.",
            status="new_objection_raised",
            new_objection_text="E sobre o tempo de contrato?",
        ),
    )


@pytest.fixture
def mock_analysis_reaction_new_obj_to_presentation() -> UserInputAnalysisOutput:
    """Analysis: user raises a new objection to a solution presentation."""
    return UserInputAnalysisOutput(
        overall_intent="ExpressingObjection",
        extracted_objections=[
            ExtractedObjection(objection_text="Isso não tem a feature X que preciso.")
        ],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="new_objection_to_solution",
            details="Isso não tem a feature X que preciso.",
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
    )


@pytest.fixture
def mock_analysis_reaction_positive_to_presentation() -> UserInputAnalysisOutput:
    """Analysis: user shows positive interest after solution presentation."""
    return UserInputAnalysisOutput(
        overall_intent="PositiveFeedbackToProposal",  # Ou RequestForNextStepInPurchase
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="acknowledged_action"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="positive_interest", details="Gostei! Parece bom."
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
    )


@pytest.fixture
def mock_analysis_confirming_close() -> UserInputAnalysisOutput:
    """Analysis result for user confirming the closing initiation."""
    return UserInputAnalysisOutput(
        overall_intent="ConfirmingCloseAttempt",  # <<< New Intent
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"  # Example
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
    )


@pytest.fixture
def mock_analysis_rejecting_close() -> UserInputAnalysisOutput:
    """Analysis result for user rejecting the closing initiation."""
    return UserInputAnalysisOutput(
        overall_intent="RejectingCloseAttempt",  # <<< New Intent
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"  # Example
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
    )


@pytest.fixture
def mock_analysis_requesting_correction() -> UserInputAnalysisOutput:
    """Analysis result for user requesting correction during closing."""
    return UserInputAnalysisOutput(
        overall_intent="RequestingOrderCorrection",  # <<< New Intent
        extracted_questions=[
            ExtractedQuestionAnalysis(
                question_text="O endereço está errado.", is_repetition=False
            )
        ],  # Example
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"  # Example
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
    )


# tests/unit/test_state_updater.py
# At the end of the fixtures section


@pytest.fixture
def mock_analysis_confirming_close() -> UserInputAnalysisOutput:
    """Analysis result for user confirming the closing initiation."""
    return UserInputAnalysisOutput(
        overall_intent="ConfirmingCloseAttempt",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
        correction_details_text=None,
    )


@pytest.fixture
def mock_analysis_rejecting_close() -> UserInputAnalysisOutput:
    """Analysis result for user rejecting the closing initiation."""
    return UserInputAnalysisOutput(
        overall_intent="RejectingCloseAttempt",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
        correction_details_text=None,
    )


@pytest.fixture
def mock_analysis_requesting_correction() -> UserInputAnalysisOutput:
    """Analysis result for user requesting correction during closing."""
    return UserInputAnalysisOutput(
        overall_intent="RequestingOrderCorrection",
        extracted_questions=[
            ExtractedQuestionAnalysis(
                question_text="O endereço está errado.", is_repetition=False
            )
        ],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
        correction_details_text=None,
    )


@pytest.fixture
def mock_analysis_providing_correction() -> UserInputAnalysisOutput:
    """Analysis result for user providing correction details."""
    correction_text = "O CEP correto é 99999-000"
    return UserInputAnalysisOutput(
        overall_intent="ProvidingCorrectionDetails",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
        correction_details_text=correction_text,  # Include the text
    )


@pytest.fixture
def mock_analysis_final_confirmation() -> UserInputAnalysisOutput:
    """Analysis result for user giving final confirmation."""
    return UserInputAnalysisOutput(
        overall_intent="FinalOrderConfirmation",
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="answered_clearly"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
        correction_details_text=None,
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
    assert "State update failed: Invalid " in delta["last_processing_error"]
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

    assert "customer_profile_dynamic" in delta
    final_dynamic_profile = delta["customer_profile_dynamic"]
    initial_objections = state["customer_profile_dynamic"]["identified_objections"]
    assert (
        final_dynamic_profile.get("identified_objections") == initial_objections
    )  # Lista deve ser a mesma
    assert (
        final_dynamic_profile.get("last_discerned_intent")
        == mock_analysis_duplicate_objection.overall_intent
    )  # Intent deve ser atualizado

    # A fila de interrupções também não deve mudar neste cenário específico
    assert "user_interruptions_queue" not in delta  # Ou verificar se é igual à inicial
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


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_objection_resolved(
    mock_log_event, base_state, mock_analysis_obj_resolved
):
    """Tests that an objection is marked as resolved and removed from interrupt queue."""
    state = base_state
    state["current_turn_number"] = 3
    original_objection_text = "O preço é alto."
    # Simular objeção ativa no perfil e na fila
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=original_objection_text,
            status="addressing",
            rebuttal_attempts=1,
            source_turn=2,
        )
    ]
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="objection",
            text=original_objection_text,
            status="pending_resolution",
            turn_detected=2,
        )
    ]
    state["user_input_analysis_result"] = mock_analysis_obj_resolved.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert len(dynamic_profile["identified_objections"]) == 1
    assert (
        dynamic_profile["identified_objections"][0]["text"] == original_objection_text
    )
    assert dynamic_profile["identified_objections"][0]["status"] == "resolved"

    assert "user_interruptions_queue" in delta
    assert (
        len(delta["user_interruptions_queue"]) == 0
    )  # Objeção resolvida removida da fila
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_objection_persists(
    mock_log_event, base_state, mock_analysis_obj_persists
):
    """
    Tests that a persisting objection is marked active and added back to the
    interrupt queue, but its attempt count is NOT incremented by StateUpdater.
    """
    state = base_state
    state["current_turn_number"] = 3
    original_objection_text = "O preço é alto."
    initial_attempts = 1  # Attempts before this turn's input
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=original_objection_text,
            status="addressing",  # Status before processing user's persistent response
            rebuttal_attempts=initial_attempts,
            source_turn=2,
        )
    ]
    state["user_interruptions_queue"] = []
    state["user_input_analysis_result"] = mock_analysis_obj_persists.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert len(dynamic_profile["identified_objections"]) == 1
    updated_objection = dynamic_profile["identified_objections"][0]
    assert updated_objection["text"] == original_objection_text
    assert (
        updated_objection["status"] == "active"
    )  # Updated to active because it persists

    # --- FIX: Assert that attempts remain unchanged by StateUpdater ---
    assert (
        updated_objection["rebuttal_attempts"] == initial_attempts
    )  # Should NOT be incremented here
    # --- END FIX ---

    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "objection"
    assert interrupt_queue[0]["text"] == original_objection_text
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_new_objection_after_rebuttal(
    mock_log_event, base_state, mock_analysis_obj_new_raised_after_rebuttal
):
    """Tests handling of a new objection raised after a rebuttal to an old one."""
    state = base_state
    state["current_turn_number"] = 3
    original_objection_text = "O preço é alto."
    new_objection_text = "E sobre o tempo de contrato?"
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=original_objection_text,
            status="addressing",
            rebuttal_attempts=1,
            source_turn=2,
        )
    ]
    state["user_input_analysis_result"] = (
        mock_analysis_obj_new_raised_after_rebuttal.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    # Deve ter a original (marcada como ignored) e a nova (marcada como active)
    assert len(dynamic_profile["identified_objections"]) == 2

    original_obj_entry = next(
        o
        for o in dynamic_profile["identified_objections"]
        if o["text"] == original_objection_text
    )
    new_obj_entry = next(
        o
        for o in dynamic_profile["identified_objections"]
        if o["text"] == new_objection_text
    )

    assert original_obj_entry["status"] == "ignored"
    assert new_obj_entry["status"] == "active"
    assert new_obj_entry["source_turn"] == 4  # next_turn_number

    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    # Apenas a nova objeção ativa deve estar na fila
    assert len(interrupt_queue) == 1
    assert interrupt_queue[0]["type"] == "objection"
    assert interrupt_queue[0]["text"] == new_objection_text
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_positive_reaction_to_presentation(
    mock_log_event, base_state, mock_analysis_reaction_positive_to_presentation
):
    """Tests handling of a positive reaction to presentation (no major state changes expected here from StateUpdater)."""
    state = base_state
    state["current_turn_number"] = 2
    state["user_input_analysis_result"] = (
        mock_analysis_reaction_positive_to_presentation.model_dump()
    )

    delta = await update_conversation_state_node(state, {})
    assert delta.get("current_turn_number") == 3
    mock_log_event.assert_not_called()

    # CORREÇÃO:
    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert not dynamic_profile.get("identified_objections", [])
    assert not dynamic_profile.get("identified_needs", [])
    assert not dynamic_profile.get("identified_pain_points", [])
    assert dynamic_profile.get("last_discerned_intent") == "PositiveFeedbackToProposal"

    assert "user_interruptions_queue" not in delta


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_stores_last_discerned_intent(mock_log_event, base_state):
    """Tests if last_discerned_intent is stored in dynamic_profile."""
    state = base_state
    test_intent = "RequestForNextStepInPurchase"
    analysis = UserInputAnalysisOutput(
        overall_intent=test_intent,
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"
        ),
        reaction_to_solution_presentation=ReactionToPresentation(
            reaction_type="not_applicable"
        ),
        objection_status_after_rebuttal=ObjectionAfterRebuttalStatus(
            status="not_applicable"
        ),
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
    )
    state["user_input_analysis_result"] = analysis.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert dynamic_profile.get("last_discerned_intent") == test_intent
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_handles_reaction_new_objection_to_presentation(
    mock_log_event, base_state, mock_analysis_reaction_new_obj_to_presentation
):
    """Tests adding a new objection from reaction_to_solution_presentation."""
    state = base_state
    state["current_turn_number"] = 2
    state["user_input_analysis_result"] = (
        mock_analysis_reaction_new_obj_to_presentation.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert len(dynamic_profile.get("identified_objections", [])) == 1
    obj_entry = dynamic_profile["identified_objections"][0]
    assert obj_entry.get("text") == "Isso não tem a feature X que preciso."
    assert obj_entry.get("status") == "active"
    assert obj_entry.get("related_to_proposal") is True
    assert obj_entry.get("source_turn") == 3  # next_turn_number

    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    assert len(interrupt_queue) == 1  # A objeção extraída em extracted_objections
    assert interrupt_queue[0].get("type") == "objection"
    assert interrupt_queue[0].get("text") == "Isso não tem a feature X que preciso."
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_handles_objection_status_new_raised(
    mock_log_event, base_state, mock_analysis_obj_new_raised_after_rebuttal
):
    """Tests handling when a new objection is raised after a rebuttal."""
    state = base_state
    state["current_turn_number"] = 3
    original_objection_text = "O preço é alto."
    new_objection_text = (
        mock_analysis_obj_new_raised_after_rebuttal.objection_status_after_rebuttal.new_objection_text
    )

    # Simular a objeção original no perfil
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=original_objection_text,
            status="addressing",
            rebuttal_attempts=1,
            source_turn=2,
        )
    ]
    state["user_input_analysis_result"] = (
        mock_analysis_obj_new_raised_after_rebuttal.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert "customer_profile_dynamic" in delta
    dynamic_profile = delta["customer_profile_dynamic"]
    assert len(dynamic_profile.get("identified_objections", [])) == 2  # Original + Nova

    original_obj_updated = next(
        o
        for o in dynamic_profile["identified_objections"]
        if o.get("text") == original_objection_text
    )
    new_obj_added = next(
        o
        for o in dynamic_profile["identified_objections"]
        if o.get("text") == new_objection_text
    )

    assert original_obj_updated.get("status") == "ignored"  # Original é ignorada
    assert new_obj_added.get("status") == "active"
    assert new_obj_added.get("source_turn") == 4  # next_turn_number

    assert "user_interruptions_queue" in delta
    interrupt_queue = delta["user_interruptions_queue"]
    # Apenas a NOVA objeção ativa deve estar na fila (a original foi ignorada)
    # E a nova objeção também foi extraída em `extracted_objections` e adicionada à fila por essa via.
    # A lógica de consolidação da fila deve evitar duplicatas.
    active_objections_in_queue = [
        inter for inter in interrupt_queue if inter.get("type") == "objection"
    ]
    assert len(active_objections_in_queue) == 1
    assert active_objections_in_queue[0].get("text") == new_objection_text
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_awaiting_confirmation(
    mock_log_event, base_state, mock_analysis_confirming_close
):
    """Tests closing_status becomes awaiting_confirmation."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"  # Status before user confirmation
    # Simulate last action was INITIATE_CLOSING
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = mock_analysis_confirming_close.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "awaiting_confirmation"
    assert "customer_profile_dynamic" in delta  # Because intent changed
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "ConfirmingCloseAttempt"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_confirmation_rejected(
    mock_log_event, base_state, mock_analysis_rejecting_close
):
    """Tests closing_status becomes confirmation_rejected."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = mock_analysis_rejecting_close.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "confirmation_rejected"
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "RejectingCloseAttempt"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_needs_correction(
    mock_log_event, base_state, mock_analysis_requesting_correction
):
    """Tests closing_status becomes needs_correction."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = (
        mock_analysis_requesting_correction.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "needs_correction"
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "RequestingOrderCorrection"
    )
    # Check if the question about correction was added to interrupt queue
    assert "user_interruptions_queue" in delta
    assert len(delta["user_interruptions_queue"]) == 1
    assert delta["user_interruptions_queue"][0]["type"] == "direct_question"
    assert delta["user_interruptions_queue"][0]["text"] == "O endereço está errado."
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_closing_status_no_change_if_last_action_not_initiate(
    mock_log_event, base_state, mock_analysis_confirming_close
):
    """Tests closing_status doesn't change if last action wasn't INITIATE_CLOSING."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "not_started"  # Initial status
    # Simulate last action was something else
    state["last_agent_action"] = PendingAgentAction(
        action_type="ASK_SPIN_QUESTION",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = (
        mock_analysis_confirming_close.model_dump()
    )  # User confirms, but irrelevant now

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    # closing_process_status should NOT be in the delta as it didn't change
    assert "closing_process_status" not in delta
    assert "customer_profile_dynamic" in delta  # Intent changed
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "ConfirmingCloseAttempt"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_closing_status_no_change_if_intent_irrelevant(
    mock_log_event, base_state, mock_analysis_new_question
):
    """Tests closing_status doesn't change if intent is irrelevant, even after INITIATE_CLOSING."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    # User asks a question instead of confirming/rejecting
    state["user_input_analysis_result"] = mock_analysis_new_question.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    # closing_process_status should NOT be in the delta
    assert "closing_process_status" not in delta
    assert "customer_profile_dynamic" in delta  # Intent changed
    assert delta["customer_profile_dynamic"]["last_discerned_intent"] == "Questioning"
    # Check question was added to queue
    assert "user_interruptions_queue" in delta
    assert len(delta["user_interruptions_queue"]) == 1
    assert delta["user_interruptions_queue"][0]["type"] == "direct_question"
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_awaiting_confirmation(
    mock_log_event, base_state, mock_analysis_confirming_close
):
    """Tests closing_status becomes awaiting_confirmation after INITIATE_CLOSING."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"  # Status before user confirmation
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = mock_analysis_confirming_close.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "awaiting_confirmation"
    assert "customer_profile_dynamic" in delta  # Because intent changed
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "ConfirmingCloseAttempt"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_confirmation_rejected(
    mock_log_event, base_state, mock_analysis_rejecting_close
):
    """Tests closing_status becomes confirmation_rejected after INITIATE_CLOSING."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = mock_analysis_rejecting_close.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "confirmation_rejected"
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "RejectingCloseAttempt"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_needs_correction_after_initiate(
    mock_log_event, base_state, mock_analysis_requesting_correction
):
    """Tests closing_status becomes needs_correction after INITIATE_CLOSING."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "attempt_made"
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = (
        mock_analysis_requesting_correction.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "needs_correction"
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "RequestingOrderCorrection"
    )
    assert "user_interruptions_queue" in delta  # Check question added
    assert any(
        q["type"] == "direct_question" and q["text"] == "O endereço está errado."
        for q in delta["user_interruptions_queue"]
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_needs_correction_after_confirm(
    mock_log_event, base_state, mock_analysis_requesting_correction
):
    """Tests closing_status becomes needs_correction after CONFIRM_ORDER_DETAILS."""
    state = base_state
    state["current_turn_number"] = 5
    state["closing_process_status"] = (
        "awaiting_confirmation"  # Status before correction request
    )
    state["last_agent_action"] = PendingAgentAction(
        action_type="CONFIRM_ORDER_DETAILS",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = (
        mock_analysis_requesting_correction.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 6
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "needs_correction"
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "RequestingOrderCorrection"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_awaiting_confirmation_after_correction(
    mock_log_event, base_state, mock_analysis_providing_correction
):
    """Tests closing_status becomes awaiting_confirmation after user provides correction details."""
    state = base_state
    state["current_turn_number"] = 7
    state["closing_process_status"] = (
        "needs_correction"  # Status before user provides correction
    )
    state["last_agent_action"] = PendingAgentAction(
        action_type="HANDLE_CLOSING_CORRECTION",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = (
        mock_analysis_providing_correction.model_dump()
    )

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 8
    assert "closing_process_status" in delta
    assert (
        delta["closing_process_status"] == "awaiting_confirmation"
    )  # Back to awaiting confirmation
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "ProvidingCorrectionDetails"
    )
    # We are not asserting changes to active_proposal here yet
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_sets_confirmed_success(
    mock_log_event, base_state, mock_analysis_final_confirmation
):
    """Tests closing_status becomes confirmed_success after final confirmation."""
    state = base_state
    state["current_turn_number"] = 9
    state["closing_process_status"] = (
        "awaiting_confirmation"  # Status before final confirmation
    )
    state["last_agent_action"] = PendingAgentAction(
        action_type="CONFIRM_ORDER_DETAILS",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = mock_analysis_final_confirmation.model_dump()

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 10
    assert "closing_process_status" in delta
    assert delta["closing_process_status"] == "confirmed_success"
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "FinalOrderConfirmation"
    )
    mock_log_event.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.state_updater._log_missing_information_event",
    new_callable=AsyncMock,
)
async def test_state_updater_closing_status_no_change_if_last_action_not_closing(
    mock_log_event, base_state, mock_analysis_confirming_close
):
    """Tests closing_status doesn't change if last action wasn't a closing one."""
    state = base_state
    state["current_turn_number"] = 3
    state["closing_process_status"] = "not_started"  # Initial status
    state["last_agent_action"] = PendingAgentAction(
        action_type="ASK_SPIN_QUESTION",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["user_input_analysis_result"] = (
        mock_analysis_confirming_close.model_dump()
    )  # User confirms, but irrelevant now

    delta = await update_conversation_state_node(state, {})

    assert delta.get("current_turn_number") == 4
    assert "closing_process_status" not in delta  # Status should not change
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["last_discerned_intent"]
        == "ConfirmingCloseAttempt"
    )
    mock_log_event.assert_not_called()
