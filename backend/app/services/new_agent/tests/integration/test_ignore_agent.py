# backend/app/services/ai_reply/new_agent/test_ignore_agent.py

import asyncio
import copy
import os
import sys
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from loguru import logger

# Componentes locais
try:
    from app.database import AsyncSessionLocal
    from app.services.new_agent.components.final_state_updater import (
        finalize_turn_state_node,
    )
    from app.services.new_agent.components.input_processor import (
        process_user_input_node,
    )
    from app.services.new_agent.components.knowledge_retriever import (
        knowledge_retriever_node,
    )
    from app.services.new_agent.components.output_formatter import output_formatter_node
    from app.services.new_agent.components.planner import goal_and_action_planner_node
    from app.services.new_agent.components.response_generator import (
        response_generator_node,
    )
    from app.services.new_agent.components.state_updater import (
        update_conversation_state_node,
    )
    from app.services.new_agent.state_definition import (
        AgentGoal,
        PendingAgentAction,
        RichConversationState,
        UserInterruption,
    )

    # Importar funções de grafo de um local comum ou copiar
    try:
        from app.services.new_agent.graph_utils import (
            create_agent_graph_v2_complete,
            route_action,
        )

        logger.info("Imported graph functions from graph_utils.")
    except ImportError:
        logger.warning(
            "Could not import from graph_utils. Defining graph functions locally."
        )

        # Fallback definitions (copy from previous test)
        def route_action(
            state: RichConversationState,
        ) -> Literal["knowledge_retriever", "response_generator", "__end__"]:
            action_command = state.get("next_agent_action_command")
            logger.debug(f"[Router: route_action] Planned action: {action_command}")
            actions_requiring_rag = ["ANSWER_DIRECT_QUESTION", "GENERATE_REBUTTAL"]
            if action_command in actions_requiring_rag:
                return "knowledge_retriever"
            elif action_command:
                return "response_generator"
            else:
                return END

        def create_agent_graph_v2_complete(checkpointer):
            workflow = StateGraph(RichConversationState)
            nodes = [
                ("process_input", process_user_input_node),
                ("update_state", update_conversation_state_node),
                ("planner", goal_and_action_planner_node),
                ("knowledge_retriever", knowledge_retriever_node),
                ("response_generator", response_generator_node),
                ("output_formatter", output_formatter_node),
                ("finalize_turn_state", finalize_turn_state_node),
            ]
            for name, node_func in nodes:
                if not callable(node_func):
                    return None
                workflow.add_node(name, node_func)
            workflow.set_entry_point("process_input")
            workflow.add_edge("process_input", "update_state")
            workflow.add_edge("update_state", "planner")
            workflow.add_conditional_edges(
                "planner",
                route_action,
                {
                    "knowledge_retriever": "knowledge_retriever",
                    "response_generator": "response_generator",
                    END: END,
                },
            )
            workflow.add_edge("knowledge_retriever", "response_generator")
            workflow.add_edge("response_generator", "output_formatter")
            workflow.add_edge("output_formatter", "finalize_turn_state")
            workflow.add_edge("finalize_turn_state", END)
            logger.info(
                "Compiling New Agent Graph (v2 - Complete - Local Definition)..."
            )
            compiled_graph = workflow.compile(checkpointer=checkpointer)
            logger.info(
                "New Agent Graph (v2 - Complete - Local Definition) compiled successfully."
            )
            return compiled_graph

except ImportError as e:
    logger.error(
        f"Import error in test_ignore_agent.py: {e}. Ensure paths are correct."
    )
    # Fallback definitions
    AsyncSessionLocal = None
    finalize_turn_state_node = None
    process_user_input_node = None
    knowledge_retriever_node = None
    output_formatter_node = None
    goal_and_action_planner_node = None
    response_generator_node = None
    update_conversation_state_node = None
    AgentGoal = dict
    PendingAgentAction = dict
    RichConversationState = dict
    UserInterruption = dict
    create_agent_graph_v2_complete = lambda x: None
    route_action = lambda x: END


# Configuração
try:
    from app.config import get_settings

    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    logger.error("Could not import get_settings from app.config.")

    class MockSettings:
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
        AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

    def get_settings():
        return MockSettings()


# --- Fixture de Estado Base ---
@pytest.fixture
def base_state_ignore_agent() -> RichConversationState:
    """Provides a base state where the agent just asked a question."""
    initial_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={
            "spin_questions_asked_this_cycle": 2,
            "last_spin_type_asked": "Implication",
        },
    )
    last_ai_message = "Considerando esse problema, qual seria o impacto financeiro disso para sua operação?"  # Example Implication question
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "IgnoreTest Inc.",
            "language": "pt-br",
            "sales_tone": "direto",
            "fallback_contact_info": "ignore.com/faq",
            "business_description": "Testando ignorar.",
            "offering_overview": [
                {"name": "Produto Ignorado", "short_description": "Detalhes"}
            ],
            "key_selling_points": [],
            "address": None,
            "opening_hours": None,
            "communication_guidelines": [],
        },
        agent_config={},
        messages=[
            HumanMessage(content="Tenho um problema X."),
            AIMessage(content=last_ai_message),
        ],
        current_user_input_text="",  # To be filled by test
        current_turn_number=2,
        current_agent_goal=initial_goal,
        last_agent_action=PendingAgentAction(
            action_type="ASK_SPIN_QUESTION",
            details={"spin_type": "Implication"},
            action_generation_text=last_ai_message,
            attempts=1,
        ),
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
            "last_discerned_intent": None,
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=last_ai_message,
        final_agent_message_text=last_ai_message,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time(),
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        next_agent_action_command=None,
        action_parameters={},
    )
    return state


# --- Teste de Integração ---
@pytest.mark.asyncio
async def test_ignore_agent_question_and_change_topic(base_state_ignore_agent):
    """
    Tests handling when the user ignores the agent's question and introduces
    an off-topic comment. Expects the agent to acknowledge and transition back.
    """
    test_name = "Integration Test - Ignore Agent Question"
    logger.info(f"--- Starting {test_name} ---")
    log_file_name = f"{test_name.lower().replace(' ', '_').replace('-', '_')}.log"
    # logger.add(log_file_name, rotation="1 MB", level="DEBUG", backtrace=True, diagnose=True) # Optional

    # --- Configurar LLM ---
    llm_fast_real: Optional[AzureChatOpenAI] = None
    llm_primary_real: Optional[AzureChatOpenAI] = None
    try:
        if not SETTINGS_AVAILABLE:
            raise ValueError("Settings missing")
        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError("Credentials missing")
        llm_instance = AzureChatOpenAI(
            azure_deployment="gpt-4o",
            temperature=0,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            max_retries=2,
            request_timeout=60,
        )
        llm_fast_real = llm_instance
        llm_primary_real = llm_instance
        logger.info(f"Using REAL AzureChatOpenAI model: gpt-4o")
    except Exception as e:
        logger.warning(f"Failed to initialize AzureChatOpenAI: {e}. Skipping test.")
        pytest.skip("Real LLM not available.")

    # --- Configurar Checkpointer ---
    db_file = "integration_test_ignore_agent_memory.sqlite"
    if os.path.exists(db_file):
        os.remove(db_file)
    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:

        # --- Criar Grafo ---
        if not callable(create_agent_graph_v2_complete):
            pytest.fail("create_agent_graph_v2_complete not available.")
        graph_app = create_agent_graph_v2_complete(checkpointer=checkpointer)
        if graph_app is None:
            pytest.fail("Failed to create graph application.")

        # --- Configuração do Teste ---
        base_configurable_items = {
            "llm_fast_instance": llm_fast_real,
            "llm_primary_instance": llm_primary_real,
            "db_session_factory": AsyncSessionLocal,
        }
        thread_id_ignore = str(uuid4())
        config_ignore = {
            "configurable": {**base_configurable_items, "thread_id": thread_id_ignore}
        }

        # --- Estado Inicial ---
        initial_state = base_state_ignore_agent

        # --- Turno 1: Usuário ignora pergunta e muda de assunto ---
        logger.info(
            "\n--- Ignore Agent Test - Turn 1: User ignores question, goes off-topic ---"
        )
        user_input_t1 = "Nossa, que dia chuvoso hoje, né?"  # Off-topic comment ignoring the implication question

        state_t1_input = copy.deepcopy(initial_state)
        state_t1_input["current_user_input_text"] = user_input_t1
        state_t1_input["messages"].append(HumanMessage(content=user_input_t1))
        # current_turn_number (2) will be incremented to 3 by StateUpdater

        state_t1_output: Optional[RichConversationState] = None
        try:
            state_t1_output = await graph_app.ainvoke(
                state_t1_input, config=config_ignore
            )

            logger.info(f"Ignore Agent T1 - Input State: {state_t1_input}")
            logger.info(f"Ignore Agent T1 - Output State: {state_t1_output}")

            assert state_t1_output is not None
            assert (
                state_t1_output.get("current_turn_number") == 3
            ), "T1: Turn number should be 3"

            # Verificar InputProcessor/StateUpdater: Detectar off-topic
            analysis_result = state_t1_output.get(
                "user_input_analysis_result"
            )  # Check the raw analysis if needed (usually None after FinalStateUpdater)
            profile_t1 = state_t1_output.get("customer_profile_dynamic", {})
            # Intent might be OffTopic or RespondingToAgent (if LLM sees it as a response, albeit irrelevant)
            # The key is the interruption queue and the planner's reaction
            interrupt_queue_t1 = state_t1_output.get("user_interruptions_queue", [])
            # The queue might be empty now as the planner handled the off-topic comment
            # assert any(i.get("type") == "off_topic_comment" for i in interrupt_queue_t1), "T1: Off-topic interruption should have been queued"

            # Verificar Planner: Deve priorizar o off-topic
            goal_t1 = state_t1_output.get("current_agent_goal")
            assert (
                goal_t1 is not None
                and goal_t1.get("goal_type") == "ACKNOWLEDGE_AND_TRANSITION"
            ), "T1: Goal should be ACKNOWLEDGE_AND_TRANSITION"
            assert user_input_t1 in goal_t1.get("goal_details", {}).get(
                "text", ""
            ), "T1: Goal details should contain off-topic text"

            # Verificar Goal Aninhado: O goal original (INVESTIGATING_NEEDS) deve ser salvo
            prev_goal_t1 = goal_t1.get("previous_goal_if_interrupted")
            assert (
                prev_goal_t1 is not None
                and prev_goal_t1.get("goal_type") == "INVESTIGATING_NEEDS"
            ), "T1: Previous goal (INVESTIGATING_NEEDS) not stored"

            # Verificar Ação Planejada: Deve ser ACKNOWLEDGE_AND_TRANSITION
            action_t1 = state_t1_output.get("last_agent_action")
            assert (
                action_t1 is not None
                and action_t1.get("action_type") == "ACKNOWLEDGE_AND_TRANSITION"
            ), "T1: Action should be ACKNOWLEDGE_AND_TRANSITION"
            action_details_t1 = action_t1.get("details", {})
            assert (
                action_details_t1.get("off_topic_text") == user_input_t1
            ), "T1: Action details incorrect (off_topic_text)"
            assert (
                action_details_t1.get("previous_goal_topic") == "suas necessidades"
            ), "T1: Action details incorrect (previous_goal_topic)"  # Based on INVESTIGATING_NEEDS

            # Verificar Mensagem Gerada: Deve ser um reconhecimento + transição
            messages_t1 = state_t1_output.get("messages", [])
            assert (
                len(messages_t1) == len(initial_state.get("messages", [])) + 2
            ), "T1: Message count incorrect"
            last_ai_message_t1 = messages_t1[-1]
            assert isinstance(
                last_ai_message_t1, AIMessage
            ), "T1: Last message should be AI transition"
            # Check for keywords indicating transition back
            assert (
                "voltando" in last_ai_message_t1.content.lower()
                or "continuando" in last_ai_message_t1.content.lower()
                or "sobre suas necessidades" in last_ai_message_t1.content.lower()
            ), "T1: Transition message doesn't seem to transition back"
            logger.info(
                f"Ignore Agent T1 - Generated AI Transition: {last_ai_message_t1.content}"
            )

            logger.success(
                "Ignore Agent Test - Turn 1 (Acknowledge and Transition) PASSED!"
            )

            # --- Turno 2: Agente deve retomar o goal anterior e replanejar a ação ---
            logger.info(
                "\n--- Ignore Agent Test - Turn 2: Agent resumes previous goal ---"
            )
            # User input here doesn't matter as much, agent should act based on resumed goal
            # Let's simulate a simple acknowledgement from the user
            user_input_t2 = "Ok."

            state_t2_input = copy.deepcopy(state_t1_output)
            state_t2_input["current_user_input_text"] = user_input_t2
            state_t2_input["messages"].append(HumanMessage(content=user_input_t2))
            # current_turn_number (3) will be incremented to 4 by StateUpdater

            state_t2_output: Optional[RichConversationState] = None
            state_t2_output = await graph_app.ainvoke(
                state_t2_input, config=config_ignore
            )

            logger.info(f"Ignore Agent T2 - Input State: {state_t2_input}")
            logger.info(f"Ignore Agent T2 - Output State: {state_t2_output}")

            assert state_t2_output is not None
            assert (
                state_t2_output.get("current_turn_number") == 4
            ), "T2: Turn number should be 4"

            # Verificar Planner: Deve retomar INVESTIGATING_NEEDS e planejar a próxima pergunta SPIN
            goal_t2 = state_t2_output.get("current_agent_goal")
            assert (
                goal_t2 is not None
                and goal_t2.get("goal_type") == "INVESTIGATING_NEEDS"
            ), "T2: Goal should be INVESTIGATING_NEEDS (resumed)"
            assert (
                goal_t2.get("previous_goal_if_interrupted") is None
            ), "T2: Resumed goal should not have previous goal"

            # Verificar Ação Planejada: Deve ser a próxima pergunta SPIN (NeedPayoff)
            action_t2 = state_t2_output.get("last_agent_action")
            assert (
                action_t2 is not None
                and action_t2.get("action_type") == "ASK_SPIN_QUESTION"
            ), "T2: Action should be ASK_SPIN_QUESTION"
            action_details_t2 = action_t2.get("details", {})
            # The original goal had last_spin_type_asked = "Implication", so next is "NeedPayoff"
            assert (
                action_details_t2.get("spin_type") == "NeedPayoff"
            ), "T2: Should plan NeedPayoff question"

            # Verificar Mensagem Gerada: Deve ser a pergunta NeedPayoff
            messages_t2 = state_t2_output.get("messages", [])
            assert (
                len(messages_t2) == len(state_t1_output.get("messages", [])) + 2
            ), "T2: Message count incorrect"
            last_ai_message_t2 = messages_t2[-1]
            assert isinstance(
                last_ai_message_t2, AIMessage
            ), "T2: Last message should be AI question"
            # Check for keywords typical of NeedPayoff
            assert (
                "resolveria" in last_ai_message_t2.content.lower()
                or "ajudaria" in last_ai_message_t2.content.lower()
                or "benefício" in last_ai_message_t2.content.lower()
                or "impactaria" in last_ai_message_t2.content.lower()
            ), "T2: Message doesn't look like a NeedPayoff question"
            logger.info(
                f"Ignore Agent T2 - Generated AI NeedPayoff Question: {last_ai_message_t2.content}"
            )

            logger.success("Ignore Agent Test - Turn 2 (Resumption and SPIN) PASSED!")
            logger.success("Ignore Agent Test PASSED Overall!")

        except AssertionError as e:
            logger.error(f"Assertion failed in ignore agent test: {e}")
            if state_t1_output:
                logger.debug(f"State T1 Output for review: {state_t1_output}")
            if "state_t2_output" in locals() and state_t2_output:
                logger.debug(f"State T2 Output for review: {state_t2_output}")
            raise
        except Exception as e:
            logger.exception(f"Error during Ignore Agent Test: {e}")
            assert False, f"Ignore Agent Test Failed: {e}"
        finally:
            # await checkpointer.close()
            logger.info(f"--- {test_name} Finished ---")


# --- Bloco para Execução Direta ---
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.info("Starting integration test script (Ignore Agent)...")

    # --- Criar o estado inicial manualmente ---
    initial_goal_main = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={
            "spin_questions_asked_this_cycle": 2,
            "last_spin_type_asked": "Implication",
        },
    )
    last_ai_message_main = "Considerando esse problema, qual seria o impacto financeiro disso para sua operação?"
    initial_state_main = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "IgnoreTest Inc.",
            "language": "pt-br",
            "sales_tone": "direto",
            "fallback_contact_info": "ignore.com/faq",
            "business_description": "Testando ignorar.",
            "offering_overview": [
                {"name": "Produto Ignorado", "short_description": "Detalhes"}
            ],
            "key_selling_points": [],
            "address": None,
            "opening_hours": None,
            "communication_guidelines": [],
        },
        agent_config={},
        messages=[
            HumanMessage(content="Tenho um problema X."),
            AIMessage(content=last_ai_message_main),
        ],
        current_user_input_text="",
        current_turn_number=2,
        current_agent_goal=initial_goal_main,
        last_agent_action=PendingAgentAction(
            action_type="ASK_SPIN_QUESTION",
            details={"spin_type": "Implication"},
            action_generation_text=last_ai_message_main,
            attempts=1,
        ),
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
            "last_discerned_intent": None,
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=last_ai_message_main,
        final_agent_message_text=last_ai_message_main,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time(),
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        next_agent_action_command=None,
        action_parameters={},
    )
    # --- Fim da criação manual do estado ---

    try:
        if "create_agent_graph_v2_complete" not in globals() or not callable(
            create_agent_graph_v2_complete
        ):
            logger.error(
                "Graph creation function not found. Define or import from graph_utils."
            )
            sys.exit(1)
        asyncio.run(test_ignore_agent_question_and_change_topic(initial_state_main))
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Ignore Agent) finished.")
