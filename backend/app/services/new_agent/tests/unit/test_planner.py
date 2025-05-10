# tests/unit/test_planner.py

import pytest
import copy
from uuid import uuid4
from typing import Dict, Any, Optional, List
import time

# Importar a função a ser testada e as definições/schemas necessários
from app.services.new_agent.components.planner import (
    goal_and_action_planner_node,
    _get_next_spin_type,
    MAX_SPIN_QUESTIONS_PER_CYCLE,
    MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION,
)

from app.services.new_agent.state_definition import (
    RichConversationState,
    UserInterruption,
    AgentGoal,
    AgentGoalType,
    AgentActionType,
    AgentActionDetails,
    SpinQuestionType,
    PendingAgentAction,
    IdentifiedNeedEntry,
    IdentifiedObjectionEntry,
    IdentifiedPainPointEntry,
    DynamicCustomerProfile,
    ProposedSolution,
    TriggerEventType,
)

from app.services.new_agent.schemas.input_analysis import (
    UserInputAnalysisOutput,
    PendingAgentActionResponseAnalysis,
)

# --- Fixtures ---


@pytest.fixture
def base_state_for_planner() -> RichConversationState:
    """Provides a base RichConversationState for planner tests."""
    initial_goal = AgentGoal(
        goal_type="IDLE",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    # Criar um UserInputAnalysisOutput mínimo para o estado base
    base_user_input_analysis = UserInputAnalysisOutput(
        overall_intent="StatingInformationOrOpinion",  # Um default genérico
        analysis_of_response_to_agent_action=PendingAgentActionResponseAnalysis(
            user_response_to_agent_action="not_applicable"  # Default
        ),
        extracted_questions=[],
        extracted_objections=[],
        extracted_needs_or_pains=[],
        is_primarily_vague_statement=False,
        is_primarily_off_topic=False,
        correction_details_text=None,
        reaction_to_solution_presentation=None,
        objection_status_after_rebuttal=None,
    )

    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={  # Adicionar todos os campos esperados por CompanyProfileSchema ou mockar
            "company_name": "Test Co",
            "business_description": "Test business description",
            "offering_overview": [
                {
                    "name": "Produto Genérico Adequado",
                    "short_description": "Resolve tudo",
                    "details_url": None,  # Adicionar campos opcionais se o schema os tiver
                    "price_info": None,
                    "category": None,
                }
            ],
            "key_selling_points": ["Ponto de venda 1", "Ponto de venda 2"],
            "communication_guidelines": ["Ser amigável", "Ser direto"],
            "language": "pt-br",
            "sales_tone": "amigável",
            "fallback_contact_info": "contato@testco.com",
            "address": "Rua Teste, 123",
            "opening_hours": "9h-18h",
            "target_audience": "Pequenas e médias empresas",  # Adicionar se usado
            "delivery_options": "Correios e Transportadora",  # Adicionar se usado
        },
        agent_config={  # Adicionar agent_config aqui, mesmo que vazio, ou com defaults
            "max_follow_up_attempts": 3,  # Exemplo de configuração
        },
        messages=[],
        current_user_input_text="User input inicial",  # Um valor não-None
        current_turn_number=1,
        current_agent_goal=initial_goal,
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
            "last_discerned_intent": None,
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],  # Geralmente gerenciado pelo StateUpdater
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,
        final_agent_message_text=None,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time(),
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=base_user_input_analysis.model_dump(),  # Usar o dump do Pydantic
        next_agent_action_command=None,
        action_parameters={},
        # Novos campos para follow-up
        follow_up_scheduled=False,
        follow_up_attempt_count=0,
        last_message_from_agent_timestamp=None,
        trigger_event="user_message",  # Default para user_message se current_user_input_text existe
    )
    # Ajustar trigger_event se current_user_input_text for None no setup de um teste específico
    if state["current_user_input_text"] is None:
        state["trigger_event"] = None  # Ou um trigger_event específico se for o caso

    return state


# --- Testes ---


@pytest.mark.asyncio
async def test_planner_initial_idle_state_moves_to_greeting(
    base_state_for_planner,
):
    """
    Testa se, partindo de um estado IDLE e sem interrupções,
    o planner define o objetivo para GREETING e planeja a ação GENERATE_GREETING.
    """
    state = base_state_for_planner
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "GREETING"
    assert delta["next_agent_action_command"] == "GENERATE_GREETING"
    assert delta["action_parameters"] == {}
    assert delta["current_agent_goal"]["goal_details"] == {}
    assert "user_interruptions_queue" not in delta
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
async def test_planner_handles_direct_question_interruption(base_state_for_planner):
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    state["current_agent_goal"] = original_goal
    question_text = "Qual o preço?"
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="direct_question",
            text=question_text,
            status="pending_resolution",
            turn_detected=1,
        )
    ]
    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    # --- Corrected Assertion ---
    # _get_goal_for_interruption maps direct_question to CLARIFYING_USER_INPUT
    assert delta["current_agent_goal"]["goal_type"] == "CLARIFYING_USER_INPUT"
    # --- End Correction ---
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    assert delta["current_agent_goal"]["goal_details"]["text"] == question_text
    assert (
        delta["current_agent_goal"]["goal_details"]["clarification_type"] == "question"
    )

    assert delta["next_agent_action_command"] == "ANSWER_DIRECT_QUESTION"
    assert delta["action_parameters"]["question_to_answer_text"] == question_text
    assert "user_interruptions_queue" in delta
    assert len(delta["user_interruptions_queue"]) == 0


@pytest.mark.asyncio
async def test_planner_handles_objection_interruption(base_state_for_planner):
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    state["current_agent_goal"] = original_goal
    objection_text = "É muito caro!"
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="objection",
            text=objection_text,
            status="pending_resolution",
            turn_detected=2,
        )
    ]
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=objection_text,
            status="active",
            rebuttal_attempts=0,
            source_turn=2,
        )
    ]

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "HANDLING_OBJECTION"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    assert (
        delta["current_agent_goal"]["goal_details"]["original_objection_text"]
        == objection_text
    )

    assert delta["next_agent_action_command"] == "GENERATE_REBUTTAL"
    assert delta["action_parameters"]["objection_text_to_address"] == objection_text
    assert "user_interruptions_queue" in delta
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
        goal_details={
            "spin_questions_asked_this_cycle": 0,
            "last_spin_type_asked": "Situation",
        },
    )
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Problem"
    assert delta["current_agent_goal"]["goal_details"] == {
        "spin_questions_asked_this_cycle": 1,
        "last_spin_type_asked": "Problem",
    }


@pytest.mark.asyncio
async def test_planner_resumes_previous_goal_and_plans_action(
    base_state_for_planner,
):
    """
    Tests if the planner resumes the previous goal (INVESTIGATING_NEEDS)
    and immediately plans the next action (ASK_SPIN_QUESTION - Situation)
    in the same cycle.
    """
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    state["current_agent_goal"] = AgentGoal(
        goal_type="CLARIFYING_USER_INPUT",
        previous_goal_if_interrupted=original_goal,
        goal_details={"text": "Alguma pergunta", "clarification_type": "question"},
    )
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] is None
    assert delta.get("next_agent_action_command") == "ASK_SPIN_QUESTION"
    assert delta.get("action_parameters", {}).get("spin_type") == "Situation"
    assert delta["current_agent_goal"]["goal_details"] == {
        "spin_questions_asked_this_cycle": 1,
        "last_spin_type_asked": "Situation",
    }


@pytest.mark.asyncio
async def test_planner_handles_vague_statement_interruption(base_state_for_planner):
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    state["current_agent_goal"] = original_goal
    vague_text = "Não sei bem..."
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="vague_statement",
            text=vague_text,
            status="pending_resolution",
            turn_detected=1,
        )
    ]
    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "CLARIFYING_USER_INPUT"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    assert delta["current_agent_goal"]["goal_details"]["text"] == vague_text
    assert delta["current_agent_goal"]["goal_details"]["clarification_type"] == "vague"
    assert delta["next_agent_action_command"] == "ASK_CLARIFYING_QUESTION"
    assert "user_interruptions_queue" in delta
    assert len(delta["user_interruptions_queue"]) == 0


@pytest.mark.asyncio
async def test_planner_handles_off_topic_interruption(base_state_for_planner):
    state = base_state_for_planner
    original_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    state["current_agent_goal"] = original_goal
    off_topic_text = "Viu o jogo ontem?"
    state["user_interruptions_queue"] = [
        UserInterruption(
            type="off_topic_comment",
            text=off_topic_text,
            status="pending_resolution",
            turn_detected=1,
        )
    ]
    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ACKNOWLEDGE_AND_TRANSITION"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] == original_goal
    assert delta["current_agent_goal"]["goal_details"]["reason"] == "Handling off-topic"
    assert delta["current_agent_goal"]["goal_details"]["text"] == off_topic_text
    assert delta["next_agent_action_command"] == "ACKNOWLEDGE_AND_TRANSITION"
    assert "user_interruptions_queue" in delta
    assert len(delta["user_interruptions_queue"]) == 0


@pytest.mark.asyncio
async def test_planner_ignores_unknown_interruption_and_plans_greeting(
    base_state_for_planner,
):
    """
    Tests that an unknown interruption type is ignored and the planner proceeds
    based on the current goal (IDLE -> GREETING).
    """
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="IDLE", previous_goal_if_interrupted=None, goal_details={}
    )
    unknown_interruption = UserInterruption(
        type="unknown_interruption_type",  # type: ignore
        text="?",
        status="pending_resolution",
        turn_detected=1,
    )
    state["user_interruptions_queue"] = [unknown_interruption]

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "GREETING"
    assert delta["next_agent_action_command"] == "GENERATE_GREETING"
    assert delta["action_parameters"] == {}
    assert "user_interruptions_queue" not in delta


@pytest.mark.asyncio
async def test_planner_resumes_presenting_solution_and_plans_action(
    base_state_for_planner,
):
    """
    Tests if the planner resumes PRESENTING_SOLUTION after an objection
    is resolved and immediately plans PRESENT_SOLUTION_OFFER.
    """
    state = base_state_for_planner
    previous_sales_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    objection_text_handled = "Preço alto"

    state["current_agent_goal"] = AgentGoal(
        goal_type="HANDLING_OBJECTION",
        previous_goal_if_interrupted=previous_sales_goal,
        goal_details={"original_objection_text": objection_text_handled},
    )
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=objection_text_handled,
            status="resolved",
            rebuttal_attempts=1,
            source_turn=2,
        )
    ]
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert delta["current_agent_goal"]["previous_goal_if_interrupted"] is None
    assert delta.get("next_agent_action_command") == "PRESENT_SOLUTION_OFFER"
    assert "product_name_to_present" in delta.get("action_parameters", {})
    assert "key_benefit_to_highlight" in delta.get("action_parameters", {})
    assert "presenting_product" in delta["current_agent_goal"]["goal_details"]
    assert "main_benefit_focus" in delta["current_agent_goal"]["goal_details"]


@pytest.mark.asyncio
async def test_planner_continues_spin_sequence_from_situation_to_problem(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 0,
            "last_spin_type_asked": "Situation",
        },
        previous_goal_if_interrupted=None,
    )
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"
    assert delta["next_agent_action_command"] == "ASK_SPIN_QUESTION"
    assert delta["action_parameters"]["spin_type"] == "Problem"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 1
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
            "spin_questions_asked_this_cycle": 1,
            "last_spin_type_asked": "Problem",
        },
        previous_goal_if_interrupted=None,
    )
    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["action_parameters"]["spin_type"] == "Implication"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 2
    )


@pytest.mark.asyncio
async def test_planner_continues_spin_sequence_implication_to_needpayoff(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 2,
            "last_spin_type_asked": "Implication",
        },
        previous_goal_if_interrupted=None,
    )
    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["action_parameters"]["spin_type"] == "NeedPayoff"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 3
    )


@pytest.mark.asyncio
async def test_planner_spin_sequence_needpayoff_to_problem_if_not_exiting(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 3,
            "last_spin_type_asked": "NeedPayoff",
        },
        previous_goal_if_interrupted=None,
    )
    state["customer_profile_dynamic"]["identified_needs"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["action_parameters"]["spin_type"] == "Problem"
    assert (
        delta["current_agent_goal"]["goal_details"]["spin_questions_asked_this_cycle"]
        == 4
    )


@pytest.mark.asyncio
async def test_planner_exits_spin_after_max_questions(base_state_for_planner):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": MAX_SPIN_QUESTIONS_PER_CYCLE,
            "last_spin_type_asked": "NeedPayoff",
        },
        previous_goal_if_interrupted=None,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert delta["next_agent_action_command"] == "PRESENT_SOLUTION_OFFER"
    assert "product_name_to_present" in delta["action_parameters"]
    assert "key_benefit_to_highlight" in delta["action_parameters"]


@pytest.mark.asyncio
async def test_planner_exits_spin_if_strong_need_identified_after_needpayoff(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "spin_questions_asked_this_cycle": 3,
            "last_spin_type_asked": "NeedPayoff",
        },
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

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert delta["next_agent_action_command"] == "PRESENT_SOLUTION_OFFER"
    assert (
        delta["action_parameters"]["key_benefit_to_highlight"]
        == "o seu desafio em relação a 'Preciso de mais velocidade'"
    )
    assert "product_name_to_present" in delta["action_parameters"]


@pytest.mark.asyncio
async def test_planner_plans_presentation_if_presenting_solution_and_did_not_just_present(
    base_state_for_planner,
):
    """
    Tests if the planner plans PRESENT_SOLUTION_OFFER when the goal is
    PRESENTING_SOLUTION but the last action wasn't the presentation itself.
    """
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        goal_details={"presenting_product": "Produto X"},
        previous_goal_if_interrupted=None,
    )
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = PendingAgentAction(
        action_type="ANSWER_DIRECT_QUESTION",
        details={},
        action_generation_text="Sim.",
        attempts=1,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "PRESENTING_SOLUTION"
    assert delta.get("next_agent_action_command") == "PRESENT_SOLUTION_OFFER"
    assert "product_name_to_present" in delta.get("action_parameters", {})
    assert "key_benefit_to_highlight" in delta.get("action_parameters", {})
    assert "presenting_product" in delta["current_agent_goal"]["goal_details"]
    assert "main_benefit_focus" in delta["current_agent_goal"]["goal_details"]


@pytest.mark.asyncio
async def test_planner_retries_rebuttal_if_objection_persists_below_limit(
    base_state_for_planner,
):
    state = base_state_for_planner
    previous_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    objection_text = "Ainda não estou convencido do valor."
    attempts_done = 1

    state["current_agent_goal"] = AgentGoal(
        goal_type="HANDLING_OBJECTION",
        previous_goal_if_interrupted=previous_goal,
        goal_details={"original_objection_text": objection_text},
    )
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=objection_text,
            status="active",
            rebuttal_attempts=attempts_done,
            source_turn=2,
        )
    ]
    state["user_interruptions_queue"] = []
    assert MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION > attempts_done

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "HANDLING_OBJECTION"
    assert delta["next_agent_action_command"] == "GENERATE_REBUTTAL"
    assert delta["action_parameters"]["objection_text_to_address"] == objection_text


@pytest.mark.asyncio
async def test_planner_generates_farewell_if_objection_persists_at_limit(
    base_state_for_planner,
):
    """
    Tests if the planner transitions to ENDING_CONVERSATION and plans
    GENERATE_FAREWELL when max rebuttal attempts are reached.
    """
    state = base_state_for_planner
    previous_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        previous_goal_if_interrupted=None,
        goal_details={},
    )
    objection_text = "Realmente não vejo como isso se encaixa."
    attempts_done = MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION

    state["current_agent_goal"] = AgentGoal(
        goal_type="HANDLING_OBJECTION",
        previous_goal_if_interrupted=previous_goal,
        goal_details={"original_objection_text": objection_text},
    )
    state["customer_profile_dynamic"]["identified_objections"] = [
        IdentifiedObjectionEntry(
            text=objection_text,
            status="active",
            rebuttal_attempts=attempts_done,
            source_turn=2,
        )
    ]
    state["user_interruptions_queue"] = []

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ENDING_CONVERSATION"
    assert (
        "Impasse on objection" in delta["current_agent_goal"]["goal_details"]["reason"]
    )
    assert delta["next_agent_action_command"] == "GENERATE_FAREWELL"
    assert "reason" in delta["action_parameters"]
    assert "Impasse sobre a objeção" in delta["action_parameters"]["reason"]


@pytest.mark.asyncio
async def test_planner_initiates_closing_after_presentation_with_buying_signal(
    base_state_for_planner,
):
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        goal_details={"presenting_product": "Produto Top"},
        previous_goal_if_interrupted=None,
    )
    state["last_agent_action"] = PendingAgentAction(
        action_type="ANSWER_DIRECT_QUESTION",
        details={},
        action_generation_text="Sim.",
        attempts=1,
    )
    state["user_interruptions_queue"] = []
    state["customer_profile_dynamic"][
        "last_discerned_intent"
    ] = "RequestForNextStepInPurchase"
    state["customer_profile_dynamic"]["identified_objections"] = []
    proposal = ProposedSolution(
        product_name="Produto Top",
        price=100.0,
        turn_proposed=1,
        status="proposed",
        key_benefits_highlighted=[],
        quantity=None,
        price_info=None,
    )
    state["active_proposal"] = proposal

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ATTEMPTING_CLOSE"
    assert delta["current_agent_goal"]["goal_details"] == {
        "closing_step": "initial_attempt"
    }
    assert delta.get("next_agent_action_command") == "INITIATE_CLOSING"
    assert (
        delta.get("action_parameters", {}).get("product_name")
        == proposal["product_name"]
    )
    assert delta.get("action_parameters", {}).get("price") == proposal["price"]


@pytest.mark.asyncio
async def test_planner_initiates_closing_when_goal_is_attempting_close_not_started(
    base_state_for_planner,
):
    """Tests planning INITIATE_CLOSING when goal=ATTEMPTING_CLOSE and status=not_started."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="ATTEMPTING_CLOSE",
        goal_details={},
        previous_goal_if_interrupted=None,
    )
    state["closing_process_status"] = "not_started"
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = None
    state["active_proposal"] = ProposedSolution(
        product_name="Produto Close",
        price=50.0,
        turn_proposed=1,
        status="proposed",
        key_benefits_highlighted=[],
        quantity=None,
        price_info=None,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ATTEMPTING_CLOSE"
    assert delta["current_agent_goal"]["goal_details"] == {
        "closing_step": "initial_attempt"
    }
    assert delta["next_agent_action_command"] == "INITIATE_CLOSING"
    assert delta["action_parameters"].get("product_name") == "Produto Close"
    assert delta["action_parameters"].get("price") == 50.0


@pytest.mark.asyncio
async def test_planner_confirms_details_when_awaiting_confirmation(
    base_state_for_planner,
):
    """Tests planning CONFIRM_ORDER_DETAILS when status=awaiting_confirmation."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="ATTEMPTING_CLOSE",
        goal_details={"closing_step": "initial_attempt"},
        previous_goal_if_interrupted=None,
    )
    state["closing_process_status"] = "awaiting_confirmation"
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["active_proposal"] = ProposedSolution(
        product_name="Produto Confirm",
        price=123.45,
        price_info="/ano",
        turn_proposed=2,
        status="proposed",
        key_benefits_highlighted=[],
        quantity=None,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ATTEMPTING_CLOSE"
    assert delta["next_agent_action_command"] == "CONFIRM_ORDER_DETAILS"
    assert delta["action_parameters"].get("product_name") == "Produto Confirm"
    assert delta["action_parameters"].get("price") == 123.45
    assert delta["action_parameters"].get("price_info") == "/ano"


@pytest.mark.asyncio
async def test_planner_handles_correction_when_needs_correction(base_state_for_planner):
    """Tests planning HANDLE_CLOSING_CORRECTION when status=needs_correction."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="ATTEMPTING_CLOSE",
        goal_details={"closing_step": "awaiting_confirmation"},
        previous_goal_if_interrupted=None,
    )
    state["closing_process_status"] = "needs_correction"
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = PendingAgentAction(
        action_type="CONFIRM_ORDER_DETAILS",
        details={},
        action_generation_text="...",
        attempts=1,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ATTEMPTING_CLOSE"
    assert delta["next_agent_action_command"] == "HANDLE_CLOSING_CORRECTION"
    assert "context" in delta["action_parameters"]


@pytest.mark.asyncio
async def test_planner_ends_conversation_when_rejected(base_state_for_planner):
    """Tests transitioning to ENDING_CONVERSATION when status=confirmation_rejected."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="ATTEMPTING_CLOSE",
        goal_details={"closing_step": "initial_attempt"},
        previous_goal_if_interrupted=None,
    )
    state["closing_process_status"] = "confirmation_rejected"
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ENDING_CONVERSATION"
    assert delta["current_agent_goal"]["goal_details"] == {
        "reason": "Closing attempt rejected"
    }
    assert delta["next_agent_action_command"] == "GENERATE_FAREWELL"


@pytest.mark.asyncio
async def test_planner_waits_when_closing_status_is_attempt_made(
    base_state_for_planner,
):
    """Tests no action is planned when status=attempt_made (waiting for user)."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="ATTEMPTING_CLOSE",
        goal_details={"closing_step": "initial_attempt"},
        previous_goal_if_interrupted=None,
    )
    state["closing_process_status"] = "attempt_made"
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = PendingAgentAction(
        action_type="INITIATE_CLOSING",
        details={},
        action_generation_text="...",
        attempts=1,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ATTEMPTING_CLOSE"
    assert delta.get("next_agent_action_command") is None
    assert delta.get("action_parameters") == {}


@pytest.mark.asyncio
async def test_planner_processes_order_when_confirmed_success(base_state_for_planner):
    """Tests planning PROCESS_ORDER_CONFIRMATION when status=confirmed_success."""
    state = base_state_for_planner
    state["current_agent_goal"] = AgentGoal(
        goal_type="ATTEMPTING_CLOSE",
        goal_details={"closing_step": "confirming_details"},
        previous_goal_if_interrupted=None,
    )
    state["closing_process_status"] = "confirmed_success"
    state["user_interruptions_queue"] = []
    state["last_agent_action"] = PendingAgentAction(
        action_type="CONFIRM_ORDER_DETAILS",
        details={},
        action_generation_text="...",
        attempts=1,
    )
    state["active_proposal"] = ProposedSolution(
        product_name="Produto Final",
        price=999,
        turn_proposed=2,
        status="proposed",
        key_benefits_highlighted=[],
        quantity=None,
        price_info=None,
    )

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ATTEMPTING_CLOSE"
    assert delta["next_agent_action_command"] == "PROCESS_ORDER_CONFIRMATION"
    assert delta["action_parameters"].get("product_name") == "Produto Final"


# --- Teste para _get_next_spin_type (função auxiliar) ---
def test_get_next_spin_type_sequence():
    assert _get_next_spin_type(None) == "Situation"
    assert _get_next_spin_type("Situation") == "Problem"
    assert _get_next_spin_type("Problem") == "Implication"
    assert _get_next_spin_type("Implication") == "NeedPayoff"
    assert _get_next_spin_type("NeedPayoff") == "Problem"
    assert _get_next_spin_type("UnknownType") == "Situation"  # type: ignore


# Novos testes para adicionar em app/services/new_agent/tests/unit/test_planner.py


@pytest.mark.asyncio
async def test_planner_handles_follow_up_timeout_and_plans_decide_proactive_step(
    base_state_for_planner,
):
    """
    Testa se o Planner, ao receber trigger_event='follow_up_timeout' e follow_up_scheduled=True,
    planeja DECIDE_PROACTIVE_STEP e incrementa follow_up_attempt_count.
    """
    state = base_state_for_planner
    state["trigger_event"] = "follow_up_timeout"
    state["follow_up_scheduled"] = True
    state["follow_up_attempt_count"] = 0  # Primeira tentativa de follow-up
    # Simular uma configuração de agente para max_follow_up_attempts
    state["agent_config"] = {"max_follow_up_attempts": 3}

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta  # Deve manter o goal atual
    assert (
        delta["current_agent_goal"]["goal_type"]
        == state["current_agent_goal"]["goal_type"]
    )  # Goal não deve mudar aqui

    assert delta.get("next_agent_action_command") == "DECIDE_PROACTIVE_STEP"
    assert delta.get("action_parameters") == {
        "trigger_source": "follow_up_timeout",
        "current_follow_up_attempts": 0,  # Passa a contagem *antes* do incremento para o decidor
    }
    assert delta.get("trigger_event") is None  # Evento deve ser consumido/limpo
    assert (
        delta.get("follow_up_attempt_count") == 1
    )  # Contagem incrementada no estado para o próximo turno
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
async def test_planner_handles_follow_up_timeout_max_attempts_reached(
    base_state_for_planner,
):
    """
    Testa se o Planner, ao receber trigger_event='follow_up_timeout' e o máximo de
    tentativas de follow-up ter sido atingido, planeja GENERATE_FAREWELL.
    """
    state = base_state_for_planner
    state["trigger_event"] = "follow_up_timeout"
    state["follow_up_scheduled"] = True
    max_attempts = 2
    state["follow_up_attempt_count"] = max_attempts  # Máximo de tentativas já atingido
    state["agent_config"] = {"max_follow_up_attempts": max_attempts}

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "ENDING_CONVERSATION"
    assert (
        "Inatividade do usuário"
        in delta["current_agent_goal"]["goal_details"]["reason"]
    )

    assert delta.get("next_agent_action_command") == "GENERATE_FAREWELL"
    assert "Inatividade prolongada do usuário" in delta.get(
        "action_parameters", {}
    ).get("reason", "")

    assert delta.get("trigger_event") is None
    assert delta.get("follow_up_scheduled") is False  # Deve desagendar
    assert (
        delta.get("follow_up_attempt_count") == max_attempts
    )  # Mantém a contagem final
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
async def test_planner_ignores_follow_up_timeout_if_not_scheduled(
    base_state_for_planner,
):
    """
    Testa se o Planner ignora trigger_event='follow_up_timeout' se follow_up_scheduled=False,
    e prossegue com a lógica normal (que para IDLE/GREETING é GENERATE_GREETING).
    """
    state = base_state_for_planner  # Goal inicial é IDLE
    state["trigger_event"] = "follow_up_timeout"
    state["follow_up_scheduled"] = False  # Follow-up não está agendado
    state["follow_up_attempt_count"] = 0
    state["agent_config"] = {"max_follow_up_attempts": 3}

    original_trigger_event = state["trigger_event"]
    delta = await goal_and_action_planner_node(state, {})

    # Deve seguir a lógica normal para IDLE -> GREETING
    assert "current_agent_goal" in delta
    assert delta["current_agent_goal"]["goal_type"] == "GREETING"
    assert delta.get("next_agent_action_command") == "GENERATE_GREETING"
    assert delta.get("trigger_event", original_trigger_event) == original_trigger_event
    assert delta.get("follow_up_attempt_count", 0) == 0  # Não foi incrementado


@pytest.mark.asyncio
async def test_planner_proactive_step_after_minimal_user_response_to_answered_question(
    base_state_for_planner,
):
    """
    Testa se o Planner, após responder a uma pergunta do usuário e receber uma
    resposta mínima, planeja DECIDE_PROACTIVE_STEP.
    """
    state = base_state_for_planner

    # Configuração inicial: Agente estava investigando necessidades.
    previous_goal_investigating = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        goal_details={
            "last_spin_type_asked": "Problem",
            "spin_questions_asked_this_cycle": 1,
        },
        previous_goal_if_interrupted=None,
    )

    # Estado ANTES da chamada ao Planner que queremos testar:
    # O agente acabou de responder a uma pergunta (que era uma interrupção).
    # O goal atual é o resultado da retomada após a interrupção (CLARIFYING_USER_INPUT) ter sido "concluída".
    # Ou seja, o Planner já teria retomado INVESTIGATING_NEEDS.
    state["current_agent_goal"] = previous_goal_investigating  # Goal retomado

    state["last_agent_action"] = (
        {  # Agente acabou de responder a uma pergunta no turno anterior
            "action_type": "ANSWER_DIRECT_QUESTION",
            "details": {
                "question_to_answer_text": "Qual o seu email?"
            },  # Pergunta que foi respondida
            "action_generation_text": "Nosso email é contato@empresa.com.",
            "attempts": 1,
        }
    )
    # Usuário deu uma resposta mínima à resposta do agente.
    state["current_user_input_text"] = "vlw"
    state["user_input_analysis_result"] = {
        "analysis_of_response_to_agent_action": {
            "user_response_to_agent_action": "acknowledged_action"  # Resposta mínima
        },
        "overall_intent": "RespondingToAgent",  # ou "Acknowledgement"
        "extracted_questions": [],
        "extracted_objections": [],
        "extracted_needs_or_pains": [],
        "is_primarily_vague_statement": True,
        "is_primarily_off_topic": False,
        "correction_details_text": None,
        "reaction_to_solution_presentation": None,
        "objection_status_after_rebuttal": None,
    }
    state["trigger_event"] = "user_message"
    state["follow_up_scheduled"] = False
    state["follow_up_attempt_count"] = 0
    state["user_interruptions_queue"] = []  # Nenhuma interrupção nova

    delta = await goal_and_action_planner_node(state, {})

    assert "current_agent_goal" in delta
    # O goal deve permanecer INVESTIGATING_NEEDS, mas o Planner deve decidir ser proativo.
    assert delta["current_agent_goal"]["goal_type"] == "INVESTIGATING_NEEDS"

    assert delta.get("next_agent_action_command") == "DECIDE_PROACTIVE_STEP"
    assert delta.get("action_parameters") == {
        "trigger_source": "user_response_or_stagnation",
        "current_follow_up_attempts": 0,
    }
    assert delta.get("last_processing_error") is None
    assert "trigger_event" not in delta
    assert delta.get("follow_up_attempt_count", 0) == 0
