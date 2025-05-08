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
            "language": "pt-br",
            "sales_tone": "amigável",
            "business_description": "Empresa de Testes",
            "key_selling_points": [],
            "communication_guidelines": [],
            "fallback_contact_info": "site.com",
            "address": None,
            "opening_hours": None,
        },
        agent_config={},
        messages=[],
        current_user_input_text="User input",
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
        current_turn_extracted_questions=[],
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
        next_agent_action_command=None,
        action_parameters={},
    )
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
