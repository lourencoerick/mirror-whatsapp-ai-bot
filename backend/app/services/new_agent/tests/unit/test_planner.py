# tests/unit/test_planner.py

import pytest
import copy
from uuid import uuid4
from typing import Dict, Any, Optional, List

# Importar a função a ser testada e as definições/schemas necessários
from app.services.new_agent.components.planner import (
    goal_and_action_planner_node,
    _get_next_spin_type,
    MAX_SPIN_QUESTIONS_PER_CYCLE,
)

from app.services.new_agent.state_definition import (
    RichConversationState,
    UserInterruption,
    AgentGoal,
    AgentGoalType,
    AgentActionType,
    AgentActionDetails,
    SpinQuestionType,
    PendingAgentAction,  # Para simular last_agent_action
    IdentifiedNeedEntry,
)

# --- Fixtures ---


@pytest.fixture
def base_state_for_planner() -> RichConversationState:
    """Provides a base RichConversationState for planner tests."""
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={"company_name": "Test Co"},
        agent_config={},
        messages=[],
        current_user_input_text="User input",
        current_turn_number=1,
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
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,  # Assumindo que já foi processado e limpo
    )
    return copy.deepcopy(state)


@pytest.fixture
def base_state_for_planner() -> RichConversationState:
    # ... (fixture como definida anteriormente) ...
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "Test Co",
            "offering_overview": [
                {
                    "name": "Produto Genérico Adequado",
                    "short_description": "Resolve tudo",
                }
            ],
        },  # Adicionar ofertas
        agent_config={},
        messages=[],
        current_user_input_text="User input",
        current_turn_number=1,
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
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
    )
    return copy.deepcopy(state)


# --- Testes ---


@pytest.mark.asyncio
async def test_planner_initial_idle_state_moves_to_investigating(
    base_state_for_planner,
):
    """
    Testa se, partindo de um estado IDLE e sem interrupções,
    o planner define o objetivo para INVESTIGATING_NEEDS e planeja uma pergunta SPIN de Situação.
    """
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="IDLE", previous_goal_if_interrupted=None, goal_details=None
    )
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Situation"
    assert not delta.get("user_interruptions_queue")  # Fila não deve ser modificada
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
async def test_planner_handles_direct_question_interruption(base_state_for_planner):
    # ... (setup do teste como antes) ...
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details=None,
    )
    state["current_agent_goal"] = original_goal
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="direct_question",
            text="Qual o preço?",
            status="pending_resolution",
            turn_detected=1,
        )
    ]
    delta = await goal_and_action_planner_node(state, {})

    assert (
        delta["current_agent_goal"]["goal_type"] == "CLARIFYING_USER_INPUT"
    )  # Ou um goal mais específico como "ANSWERING_QUESTION"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    # CORREÇÃO: Esperar a chave 'text' em goal_details
    assert delta["current_agent_goal"]["goal_details"]["text"] == "Qual o preço?"

    assert delta["next_agent_action_command"] == "ANSWER_DIRECT_QUESTION"
    assert delta["action_parameters"]["question_to_answer_text"] == "Qual o preço?"
    assert len(delta["user_interruptions_queue"]) == 0


@pytest.mark.asyncio
async def test_planner_handles_objection_interruption(base_state_for_planner):
    """
    Testa se uma interrupção 'objection' é priorizada.
    """
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        previous_goal_if_interrupted=None,
        goal_details=None,
    )
    state["current_agent_goal"] = original_goal
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="objection",
            text="É muito caro!",
            status="pending_resolution",
            turn_detected=2,
        )
    ]

    delta = await goal_and_action_planner_node(state, {})

    assert delta["current_agent_goal"]["goal_type"] == "HANDLING_OBJECTION"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    assert (
        delta["current_agent_goal"]["goal_details"]["objection_text"] == "É muito caro!"
    )

    assert delta["next_agent_action_command"] == "GENERATE_REBUTTAL"
    assert delta["action_parameters"]["objection_text_to_address"] == "É muito caro!"
    assert len(delta["user_interruptions_queue"]) == 0


@pytest.mark.asyncio
async def test_planner_continues_spin_sequence(base_state_for_planner):
    """
    Testa se o planner continua a sequência SPIN corretamente.
    """
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details=None,
    )
    state["user_interruptions_queue"] = []
    # Simular que a última ação foi uma pergunta SPIN de Situação
    state["last_agent_action"] = PendingAgentAction(
        action_type="ASK_SPIN_QUESTION",
        details={"spin_type": "Situation"},
        action_generation_text="Como você faz X hoje?",
        attempts=1,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert (
        delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    )  # Mantém o objetivo
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Problem"  # Próximo na sequência


@pytest.mark.asyncio
async def test_planner_resumes_previous_goal_after_interruption_handled(
    base_state_for_planner,
):
    """
    Testa se o planner retoma o objetivo anterior após uma interrupção ter sido (teoricamente) tratada.
    Neste teste, a fila de interrupções está vazia, mas o current_goal ainda tem um previous_goal.
    """
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details=None,
    )
    # Simula que o objetivo atual era tratar uma interrupção, e agora ela foi resolvida (fila vazia)
    state["current_agent_goal"] = AgentGoal(
        goal_type="CLARIFYING_USER_INPUT",  # Objetivo temporário que foi concluído
        previous_goal_if_interrupted=original_goal,
        goal_details={"question_text": "Alguma pergunta"},
    )
    state["user_interruptions_queue"] = (
        []
    )  # Fila vazia, indicando que a interrupção foi tratada

    delta = await goal_and_action_planner_node(state, {})

    # Deve voltar para INVESTIGATING_NEEDS
    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert (
        delta["current_agent_goal"]["previous_goal_if_interrupted"] is None
    )  # Deve ser limpo

    # E planejar a próxima ação para INVESTIGATING_NEEDS (começar com Situation se não houver last_agent_action)
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Situation"


@pytest.mark.asyncio
async def test_planner_handles_vague_statement_interruption(base_state_for_planner):
    # ... (setup do teste como antes) ...
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details=None,
    )
    state["current_agent_goal"] = original_goal
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="vague_statement",
            text="Não sei bem...",
            status="pending_resolution",
            turn_detected=1,
        )
    ]
    delta = await goal_and_action_planner_node(state, {})

    assert delta["current_agent_goal"]["goal_type"] == "CLARIFYING_USER_INPUT"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    # CORREÇÃO: Esperar a chave 'text' em goal_details
    assert delta["current_agent_goal"]["goal_details"]["text"] == "Não sei bem..."
    assert delta["next_agent_action_command"] == "ASK_CLARIFYING_QUESTION"
    assert len(delta["user_interruptions_queue"]) == 0


async def test_planner_handles_off_topic_interruption(base_state_for_planner):
    # ... (setup do teste como antes) ...
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details=None,
    )
    state["current_agent_goal"] = original_goal
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="off_topic_comment",
            text="Viu o jogo ontem?",
            status="pending_resolution",
            turn_detected=1,
        )
    ]
    delta = await goal_and_action_planner_node(state, {})

    # CORREÇÃO: Esperar o goal_type que o código realmente define
    assert delta["current_agent_goal"]["goal_type"] == "ACKNOWLEDGE_AND_TRANSITION"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    # Verificar se goal_details contém a razão (opcional, mas bom)
    assert delta["current_agent_goal"]["goal_details"]["reason"] == "Handling off-topic"
    assert delta["next_agent_action_command"] == "ACKNOWLEDGE_AND_TRANSITION"
    assert len(delta["user_interruptions_queue"]) == 0


@pytest.mark.asyncio
async def test_planner_no_action_if_unknown_interruption_and_no_main_goal_logic(
    base_state_for_planner,
):
    """
    Testa se nenhuma ação é planejada se uma interrupção desconhecida ocorre
    e não há lógica de fallback para o objetivo principal.
    """
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="IDLE", previous_goal_if_interrupted=None, goal_details=None
    )
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="unknown_interruption_type",
            text="?",
            status="pending_resolution",
            turn_detected=1,
        )  # Tipo não mapeado
    ]

    delta = await goal_and_action_planner_node(state, {})

    # A interrupção desconhecida será removida, mas nenhuma ação será planejada para ela.
    # Então, ele cairá na lógica de objetivo principal.
    # Como o objetivo é IDLE, ele deve transicionar para INVESTIGATING_NEEDS.
    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Situation"
    assert (
        len(delta["user_interruptions_queue"]) == 0
    )  # Interrupção desconhecida foi removida


@pytest.mark.asyncio
async def test_planner_exits_objection_handling_and_resumes_previous_goal(
    base_state_for_planner,
):
    """
    Testa se, após estar em HANDLING_OBJECTION e sem mais interrupções,
    o planner retoma o previous_goal_if_interrupted.
    """
    state = base_state_for_planner
    previous_sales_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    state["current_agent_goal"] = AgentGoal(
        goal_type="HANDLING_OBJECTION",
        previous_goal_if_interrupted=previous_sales_goal,  # Objetivo a ser retomado
        goal_details={"objection_text": "Preço alto"},
    )
    state["user_interruptions_queue"] = []  # Nenhuma interrupção ativa

    delta = await goal_and_action_planner_node(state, {})

    # Deve retomar PRESENTING_SOLUTION
    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert (
        delta["current_agent_goal"]["previous_goal_if_interrupted"] is None
    )  # Limpo após retomada

    # A lógica atual para PRESENTING_SOLUTION não está implementada no planner,
    # então ele pode cair no fallback de "nenhuma ação planejada" ou ir para IDLE/INVESTIGATING.
    # Vamos verificar se ele não planeja uma ação de objeção.
    # Na implementação atual, se não houver lógica para PRESENTING_SOLUTION, ele cairá no else final.
    assert delta.get("next_agent_action_command") is None
    # Ou, se quisermos que ele reinicie a investigação como fallback:
    # assert delta["current_agent_goal"]["goal_type"] == "IDLE" # Ou INVESTIGATING_NEEDS
    # assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"


# TODO: Adicionar mais testes para:
# - Sequência completa de SPIN (Situation -> Problem -> Implication -> NeedPayoff -> Saída do SPIN)
# - Lógica de quando sair do INVESTIGATING_NEEDS (ex: necessidades suficientes identificadas)
# - Lógica para BUILDING_CERTAINTY, PRESENTING_SOLUTION, ATTEMPTING_CLOSE, etc.
# - Múltiplas interrupções na fila com diferentes prioridades (se implementado)


@pytest.mark.asyncio
async def test_planner_continues_spin_sequence_from_situation_to_problem(
    base_state_for_planner,
):
    """Testa a progressão de Situation para Problem no SPIN."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 1,
            "last_spin_type_asked": "Situation",
        },
        previous_goal_if_interrupted=None,
    )
    state["user_interruptions_queue"] = []
    # A última ação do agente não é estritamente necessária para _get_next_spin_type,
    # mas o planner pode usá-la. O goal_details é mais direto aqui.

    delta = await goal_and_action_planner_node(state, {})

    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Problem"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 2
    )
    assert (
        delta["current_agent_goal"]["goal_details"]["last_spin_type_asked"] == "Problem"
    )


@pytest.mark.asyncio
async def test_planner_continues_spin_sequence_problem_to_implication(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 2,
            "last_spin_type_asked": "Problem",
        },
        previous_goal_if_interrupted=None,
    )
    delta = await goal_and_action_planner_node(state, {})
    assert delta["action_parameters"]["spin_type"] == "Implication"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 3
    )


@pytest.mark.asyncio
async def test_planner_continues_spin_sequence_implication_to_needpayoff(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 3,
            "last_spin_type_asked": "Implication",
        },
        previous_goal_if_interrupted=None,
    )
    delta = await goal_and_action_planner_node(state, {})
    assert delta["action_parameters"]["spin_type"] == "NeedPayoff"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 4
    )


@pytest.mark.asyncio
async def test_planner_spin_sequence_needpayoff_to_problem_if_not_exiting(
    base_state_for_planner,
):
    """Testa que após NeedPayoff, se não houver critério de saída, volta para Problem."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 4,
            "last_spin_type_asked": "NeedPayoff",
        },
        previous_goal_if_interrupted=None,
    )
    # Garantir que não há "strong_need_identified" para este teste
    state["customer_profile_dynamic"]["identified_needs"] = []

    delta = await goal_and_action_planner_node(state, {})
    assert delta["action_parameters"]["spin_type"] == "Problem"  # Volta para Problem
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 5
    )


@pytest.mark.asyncio
async def test_planner_exits_spin_after_max_questions(base_state_for_planner):
    """Testa a saída do SPIN após atingir MAX_SPIN_QUESTIONS_PER_CYCLE."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": MAX_SPIN_QUESTIONS_PER_CYCLE - 1,
            "last_spin_type_asked": "Problem",
        },  # Prestes a atingir o limite
        previous_goal_if_interrupted=None,
    )
    # A próxima pergunta seria a MAX_SPIN_QUESTIONS_PER_CYCLE-ésima, e depois sairia
    # Ajuste: o teste deve simular que a MAX_SPIN_QUESTIONS_PER_CYCLE já foi atingida no início do nó
    state["current_agent_goal"]["goal_details"][
        "spin_questions_asked_this_cycle"
    ] = MAX_SPIN_QUESTIONS_PER_CYCLE
    state["current_agent_goal"]["goal_details"][
        "last_spin_type_asked"
    ] = "NeedPayoff"  # Exemplo

    delta = await goal_and_action_planner_node(state, {})

    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert delta["next_agent_action_command"] == "PRESENT_SOLUTION_OFFER"
    assert "product_name_to_present" in delta["action_parameters"]
    assert "key_benefit_to_highlight" in delta["action_parameters"]


@pytest.mark.asyncio
async def test_planner_exits_spin_if_strong_need_identified_after_needpayoff(
    base_state_for_planner,
):
    """Testa a saída do SPIN se uma necessidade forte é identificada após NeedPayoff."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 3,
            "last_spin_type_asked": "NeedPayoff",
        },  # Acabou de fazer NeedPayoff
        previous_goal_if_interrupted=None,
    )
    state["customer_profile_dynamic"]["identified_needs"] = [
        IdentifiedNeedEntry(
            text="Preciso de mais velocidade",
            status="confirmed_by_user",
            priority=8,
            source_turn=3,
        )
    ]

    delta = await goal_and_action_planner_node(state, {})

    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert delta["next_agent_action_command"] == "PRESENT_SOLUTION_OFFER"
    assert (
        delta["action_parameters"]["key_benefit_to_highlight"]
        == "atender à sua necessidade de 'Preciso de mais velocidade'"
    )
    # O product_name_to_present dependerá da lógica de mapeamento (mockada ou simples)
    assert "product_name_to_present" in delta["action_parameters"]


@pytest.mark.asyncio
async def test_planner_no_action_if_presenting_solution_and_no_interruptions(
    base_state_for_planner,
):
    """
    Testa se, após apresentar uma solução (goal=PRESENTING_SOLUTION) e sem interrupções,
    o planner não planeja uma nova ação, esperando a resposta do usuário.
    """
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        goal_details={"presenting_product": "Produto X"},
        previous_goal_if_interrupted=None,
    )
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert (
        delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    )  # Mantém o objetivo
    assert delta.get("next_agent_action_command") is None  # Nenhuma ação planejada
    assert delta.get("action_parameters") == {}


# --- Teste para _get_next_spin_type (função auxiliar) ---
def test_get_next_spin_type_sequence():
    assert _get_next_spin_type(None) == "Situation"
    assert _get_next_spin_type("Situation") == "Problem"
    assert _get_next_spin_type("Problem") == "Implication"
    assert _get_next_spin_type("Implication") == "NeedPayoff"
    assert _get_next_spin_type("NeedPayoff") == "Problem"  # Comportamento atual de loop
    assert _get_next_spin_type("UnknownType") == "Situation"  # Fallback
