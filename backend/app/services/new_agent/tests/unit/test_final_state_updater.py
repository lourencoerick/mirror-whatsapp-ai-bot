# tests/unit/test_final_state_updater.py

import pytest
import time
from uuid import uuid4
from typing import Dict, Any, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from app.services.new_agent.components.final_state_updater import (
    finalize_turn_state_node,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    PendingAgentAction,
    AgentActionDetails,
    AgentActionType,
    CustomerQuestionEntry,
)

import copy


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


@pytest.fixture
def base_state_for_finalizer() -> RichConversationState:
    """Provides a base RichConversationState for finalizer tests."""
    fallback_text = "Consulte nosso site: finalizer.test"
    question_text_new = "Qual a política de devolução?"
    question_text_answered = "Qual o horário de funcionamento?"

    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={  # Perfil mínimo necessário
            "company_name": "Finalizer Test Inc.",
            "fallback_contact_info": fallback_text,
            # Adicionar outros campos se a função os usar implicitamente
            "language": "pt-br",
            "sales_tone": "neutro",
        },
        agent_config={},
        messages=[  # Histórico mínimo
            HumanMessage(content="Oi"),
            AIMessage(content="Olá!"),
        ],
        current_user_input_text="Input irrelevante para este teste",
        current_turn_number=2,  # Turno que está sendo finalizado
        current_agent_goal={"goal_type": "IDLE", "goal_details": {}},  # Exemplo
        last_agent_action=None,  # Será preenchido pelo nó
        user_interruptions_queue=[],
        customer_profile_dynamic={  # Perfil mínimo
            "identified_needs": [],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
            "last_discerned_intent": None,
        },
        customer_question_log=[  # Log com perguntas em diferentes estados
            CustomerQuestionEntry(
                original_question_text=question_text_new,
                extracted_question_core=question_text_new,
                turn_asked=2,  # Perguntado neste turno
                status="newly_asked",
                agent_direct_response_summary=None,
                repetition_of_turn=None,
                similarity_vector=None,
            ),
            CustomerQuestionEntry(
                original_question_text=question_text_answered,
                extracted_question_core=question_text_answered,
                turn_asked=1,  # Perguntado no turno anterior
                status="answered_satisfactorily",  # Já respondida
                agent_direct_response_summary="Das 9h às 18h",
                repetition_of_turn=None,
                similarity_vector=None,
            ),
        ],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        # Campos que o finalizer usa para determinar a ação e resposta:
        next_agent_action_command=None,  # Será definido por cada teste
        action_parameters={},  # Será definido por cada teste
        last_agent_generation_text=None,  # Será definido por cada teste
        final_agent_message_text=None,  # Será definido por cada teste (ou usará o generation_text)
        # Outros campos
        conversation_summary_for_llm=None,
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
    )
    return state


# --- Testes Unitários para Atualização de Status de Perguntas ---


@pytest.mark.asyncio
async def test_finalizer_updates_question_to_satisfactory(base_state_for_finalizer):
    """
    Testa se o status da pergunta 'newly_asked' é atualizado para
    'answered_satisfactorily' quando a ação é ANSWER_DIRECT_QUESTION
    e a resposta NÃO contém o texto de fallback.
    """
    state = base_state_for_finalizer
    question_to_answer = "Qual a política de devolução?"
    answer_text = "Nossa política permite devoluções em até 30 dias."
    fallback_text = state["company_profile"]["fallback_contact_info"]

    # Simular estado ANTES do finalizer rodar
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": question_to_answer}
    state["last_agent_generation_text"] = answer_text  # Resposta gerada
    state["final_agent_message_text"] = answer_text  # Mensagem final formatada

    # Garantir que o texto de fallback NÃO está na resposta
    assert fallback_text.lower() not in answer_text.lower()

    # Executar o nó
    from loguru import logger

    delta = await finalize_turn_state_node(state, {})
    logger.debug(f"delta {delta}")

    # Verificar o delta
    assert "customer_question_log" in delta
    updated_log = delta["customer_question_log"]

    # Encontrar a pergunta atualizada no log retornado
    updated_entry = find_question_in_log(updated_log, question_to_answer)

    assert updated_entry is not None, "A pergunta deveria estar no log atualizado"
    assert (
        updated_entry.get("status") == "answered_satisfactorily"
    ), "Status deveria ser 'answered_satisfactorily'"
    assert (
        updated_entry.get("turn_asked") == 2
    )  # Garantir que atualizou a entrada correta

    # Verificar que a outra pergunta não foi modificada
    other_entry = find_question_in_log(updated_log, "Qual o horário de funcionamento?")
    assert (
        other_entry is not None
        and other_entry.get("status") == "answered_satisfactorily"
    )


@pytest.mark.asyncio
async def test_finalizer_updates_question_to_fallback(base_state_for_finalizer):
    """
    Testa se o status da pergunta 'newly_asked' é atualizado para
    'answered_with_fallback' quando a ação é ANSWER_DIRECT_QUESTION
    e a resposta CONTÉM o texto de fallback.
    """
    state = base_state_for_finalizer
    question_to_answer = "Qual a política de devolução?"
    fallback_text = state["company_profile"]["fallback_contact_info"]
    answer_text = (
        f"Não tenho certeza sobre isso. {fallback_text}"  # Resposta com fallback
    )

    # Simular estado ANTES do finalizer rodar
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": question_to_answer}
    state["last_agent_generation_text"] = answer_text
    state["final_agent_message_text"] = answer_text

    # Garantir que o texto de fallback ESTÁ na resposta
    assert fallback_text.lower() in answer_text.lower()

    # Executar o nó
    delta = await finalize_turn_state_node(state, {})

    # Verificar o delta
    assert "customer_question_log" in delta
    updated_log = delta["customer_question_log"]
    updated_entry = find_question_in_log(updated_log, question_to_answer)

    assert updated_entry is not None, "A pergunta deveria estar no log atualizado"
    assert (
        updated_entry.get("status") == "answered_with_fallback"
    ), "Status deveria ser 'answered_with_fallback'"
    assert updated_entry.get("turn_asked") == 2


@pytest.mark.asyncio
async def test_finalizer_does_not_update_if_no_matching_newly_asked_question(
    base_state_for_finalizer,
):
    """
    Testa se o log não é modificado se a pergunta respondida não
    corresponde a nenhuma pergunta 'newly_asked' no log.
    """
    state = base_state_for_finalizer
    question_answered = "Pergunta que não está no log como newly_asked"
    answer_text = "Resposta qualquer."

    # Simular estado
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": question_answered}
    state["last_agent_generation_text"] = answer_text
    state["final_agent_message_text"] = answer_text

    original_log = copy.deepcopy(state["customer_question_log"])

    # Executar o nó
    delta = await finalize_turn_state_node(state, {})

    # Verificar o delta
    assert (
        "customer_question_log" not in delta
    ), "Log não deveria ter sido modificado no delta"
    # Ou verificar se o log no estado não mudou (depende se o nó retorna o log mesmo sem mudanças)
    # Para ser seguro, vamos assumir que ele pode retornar o log inalterado
    assert delta.get("customer_question_log", original_log) == original_log


@pytest.mark.asyncio
async def test_finalizer_does_not_update_if_question_already_answered(
    base_state_for_finalizer,
):
    """
    Testa se o log não é modificado se a pergunta respondida já tinha
    um status diferente de 'newly_asked'.
    """
    state = base_state_for_finalizer
    question_answered = (
        "Qual o horário de funcionamento?"  # Já está como 'answered_satisfactorily'
    )
    answer_text = "Repetindo: 9h às 18h."

    # Simular estado
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": question_answered}
    state["last_agent_generation_text"] = answer_text
    state["final_agent_message_text"] = answer_text

    original_log = copy.deepcopy(state["customer_question_log"])

    # Executar o nó
    delta = await finalize_turn_state_node(state, {})

    # Verificar o delta
    assert (
        "customer_question_log" not in delta
    ), "Log não deveria ter sido modificado no delta"
    assert delta.get("customer_question_log", original_log) == original_log


@pytest.mark.asyncio
async def test_finalizer_does_not_update_question_log_for_other_actions(
    base_state_for_finalizer,
):
    """
    Testa se o log de perguntas não é modificado quando a ação executada
    não é ANSWER_DIRECT_QUESTION.
    """
    state = base_state_for_finalizer
    rebuttal_text = "Refutando objeção X."

    # Simular estado com outra ação
    state["next_agent_action_command"] = "GENERATE_REBUTTAL"
    state["action_parameters"] = {"objection_text_to_address": "Objeção X"}
    state["last_agent_generation_text"] = rebuttal_text
    state["final_agent_message_text"] = rebuttal_text
    # Adicionar objeção ao perfil para o teste de objeção funcionar
    state["customer_profile_dynamic"]["identified_objections"] = [
        {
            "text": "Objeção X",
            "status": "active",
            "rebuttal_attempts": 0,
            "source_turn": 2,
        }
    ]

    original_log = copy.deepcopy(state["customer_question_log"])

    # Executar o nó
    delta = await finalize_turn_state_node(state, {})

    # Verificar o delta - log de perguntas não deve estar presente ou deve ser igual
    assert (
        "customer_question_log" not in delta
        or delta.get("customer_question_log") == original_log
    )
    # Verificar que a lógica da objeção rodou (opcional, mas bom)
    assert "customer_profile_dynamic" in delta
    assert (
        delta["customer_profile_dynamic"]["identified_objections"][0]["status"]
        == "addressing"
    )


# Helper function (pode ser movida para utils de teste)
def find_question_in_log(
    log: List[Dict[str, Any]], question_text: str
) -> Optional[Dict[str, Any]]:
    """Finds the first occurrence of a question by its core text (case-insensitive)."""
    if not log:
        return None
    q_lower = question_text.lower()
    for entry in log:
        # Usar .get com default para evitar KeyError
        core_text = entry.get("extracted_question_core", "")
        if core_text and core_text.lower() == q_lower:
            return entry
    return None
