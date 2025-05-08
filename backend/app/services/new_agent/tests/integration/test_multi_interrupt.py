# backend/app/services/ai_reply/new_agent/test_multi_interrupt.py

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
# Assume-se que a estrutura de diretórios permite estes imports
# Ajuste os caminhos se necessário
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
        IdentifiedObjectionEntry,
        PendingAgentAction,
        RichConversationState,
        UserInterruption,
    )

    # Importar funções de grafo de um local comum ou copiar
    # Tentativa de importar de um local comum primeiro
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

        # Fallback: Definir localmente se não encontrar graph_utils
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
                    logger.error(
                        f"Node function {name} is not callable. Skipping graph creation."
                    )
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
        f"Import error in test_multi_interrupt.py: {e}. Ensure paths are correct."
    )
    # Fallback definitions if imports fail, allowing file parsing but tests will fail
    AsyncSessionLocal = None
    finalize_turn_state_node = None
    process_user_input_node = None
    knowledge_retriever_node = None
    output_formatter_node = None
    goal_and_action_planner_node = None
    response_generator_node = None
    update_conversation_state_node = None
    AgentGoal = dict
    IdentifiedObjectionEntry = dict
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
# A fixture em si está correta e será usada pelo Pytest runner
@pytest.fixture
def base_state_multi_interrupt() -> RichConversationState:
    """Provides a base state before the multi-interruption message."""
    initial_goal = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={
            "spin_questions_asked_this_cycle": 1,
            "last_spin_type_asked": "Problem",
        },
    )
    last_ai_message = (
        "Entendo. E qual o maior problema que você enfrenta com sua solução atual?"
    )
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "MultiTest Co",
            "language": "pt-br",
            "sales_tone": "eficiente",
            "fallback_contact_info": "multitest.com",
            "business_description": "Testando interrupções.",
            "offering_overview": [
                {"name": "Produto Multi", "short_description": "Resolve A e B"}
            ],
            "key_selling_points": ["Ponto A", "Ponto B"],
            # Adicionando campos que podem faltar
            "address": None,
            "opening_hours": None,
            "communication_guidelines": [],
        },
        agent_config={},
        messages=[
            HumanMessage(content="Preciso de ajuda."),
            AIMessage(content=last_ai_message),
        ],
        current_user_input_text="",
        current_turn_number=2,
        current_agent_goal=initial_goal,
        last_agent_action=PendingAgentAction(
            action_type="ASK_SPIN_QUESTION",
            details={"spin_type": "Problem"},
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
# Esta função de teste está correta e usa a fixture injetada pelo Pytest
@pytest.mark.asyncio
async def test_multi_interruption_objection_and_question(base_state_multi_interrupt):
    """
    Tests handling when user input contains both an objection (higher priority)
    and a direct question (lower priority). Expects the objection to be handled first.
    """
    test_name = "Integration Test - Multi-Interruption (Objection + Question)"
    logger.info(f"--- Starting {test_name} ---")
    log_file_name = f"{test_name.lower().replace(' ', '_').replace('-', '_')}.log"

    # --- Configurar LLM (Real ou Mock) ---
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
        logger.warning(
            f"Failed to initialize AzureChatOpenAI: {e}. Skipping test or using mocks if available."
        )
        pytest.skip("Real LLM not available.")

    # --- Configurar Checkpointer ---
    db_file = "integration_test_multi_interrupt_memory.sqlite"
    if os.path.exists(db_file):
        os.remove(db_file)

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:

        # --- Criar Grafo ---
        if not callable(create_agent_graph_v2_complete):
            pytest.fail("create_agent_graph_v2_complete function not available.")
        graph_app = create_agent_graph_v2_complete(checkpointer=checkpointer)
        if graph_app is None:
            pytest.fail("Failed to create graph application.")

        # --- Configuração do Teste ---
        base_configurable_items = {
            "llm_fast_instance": llm_fast_real,
            "llm_primary_instance": llm_primary_real,
            "db_session_factory": AsyncSessionLocal,
        }
        thread_id_multi = str(uuid4())
        config_multi = {
            "configurable": {**base_configurable_items, "thread_id": thread_id_multi}
        }

        # --- Estado Inicial (Vem da fixture) ---
        initial_state = base_state_multi_interrupt  # Fixture é injetada aqui

        # --- Turno 1: Usuário responde com Objeção + Pergunta ---
        logger.info(
            "\n--- Multi-Interrupt Test - Turn 1: User provides Objection + Question ---"
        )
        user_input_t1 = "O problema é que parece caro. Qual o prazo de entrega?"
        objection_text = "parece caro"
        question_text = "Qual o prazo de entrega?"

        state_t1_input = copy.deepcopy(initial_state)
        state_t1_input["current_user_input_text"] = user_input_t1
        state_t1_input["messages"].append(HumanMessage(content=user_input_t1))

        state_t1_output: Optional[RichConversationState] = None
        try:
            state_t1_output = await graph_app.ainvoke(
                state_t1_input, config=config_multi
            )

            logger.info(f"Multi-Interrupt T1 - Input State: {state_t1_input}")
            logger.info(f"Multi-Interrupt T1 - Output State: {state_t1_output}")

            assert state_t1_output is not None
            assert (
                state_t1_output.get("current_turn_number") == 3
            ), "T1: Turn number should be 3"

            profile_t1 = state_t1_output.get("customer_profile_dynamic", {})
            objections_t1 = profile_t1.get("identified_objections", [])
            found_objection_t1 = any(
                objection_text.lower() in o.get("text", "").lower()
                and o.get("status") == "addressing"
                for o in objections_t1
            )
            assert (
                found_objection_t1
            ), f"T1: Objection '{objection_text}' not found or not 'addressing' in profile: {objections_t1}"

            goal_t1 = state_t1_output.get("current_agent_goal")
            assert (
                goal_t1 is not None and goal_t1.get("goal_type") == "HANDLING_OBJECTION"
            ), "T1: Goal should be HANDLING_OBJECTION"
            assert (
                objection_text.lower()
                in goal_t1.get("goal_details", {})
                .get("original_objection_text", "")
                .lower()
            ), "T1: Goal details should contain objection text"

            prev_goal_t1 = goal_t1.get("previous_goal_if_interrupted")
            assert (
                prev_goal_t1 is not None
                and prev_goal_t1.get("goal_type") == "INVESTIGATING_NEEDS"
            ), "T1: Previous goal (INVESTIGATING_NEEDS) not stored"

            action_t1 = state_t1_output.get("last_agent_action")
            assert (
                action_t1 is not None
                and action_t1.get("action_type") == "GENERATE_REBUTTAL"
            ), "T1: Action should be GENERATE_REBUTTAL"
            assert (
                objection_text.lower()
                in action_t1.get("details", {})
                .get("objection_text_to_address", "")
                .lower()
            ), "T1: Action details incorrect"

            messages_t1 = state_t1_output.get("messages", [])
            assert (
                len(messages_t1) == len(initial_state.get("messages", [])) + 2
            ), "T1: Message count incorrect"
            last_ai_message_t1 = messages_t1[-1]
            assert isinstance(
                last_ai_message_t1, AIMessage
            ), "T1: Last message should be AI rebuttal"
            assert (
                "caro" in last_ai_message_t1.content.lower()
                or "preço" in last_ai_message_t1.content.lower()
            ), "T1: Rebuttal should address price/cost"
            logger.info(
                f"Multi-Interrupt T1 - Generated AI Rebuttal: {last_ai_message_t1.content}"
            )

            logger.success("Multi-Interrupt Test - Turn 1 (Objection Handling) PASSED!")

            # --- Turno 2: Usuário responde à refutação, agente deve lidar com a pergunta pendente ---
            logger.info(
                "\n--- Multi-Interrupt Test - Turn 2: User responds, agent handles pending question ---"
            )
            user_input_t2 = "Entendi sobre o valor. Mas e o prazo de entrega?"

            state_t2_input = copy.deepcopy(state_t1_output)
            state_t2_input["current_user_input_text"] = user_input_t2
            state_t2_input["messages"].append(HumanMessage(content=user_input_t2))

            state_t2_output: Optional[RichConversationState] = None
            state_t2_output = await graph_app.ainvoke(
                state_t2_input, config=config_multi
            )

            logger.info(f"Multi-Interrupt T2 - Input State: {state_t2_input}")
            logger.info(f"Multi-Interrupt T2 - Output State: {state_t2_output}")

            assert state_t2_output is not None
            assert (
                state_t2_output.get("current_turn_number") == 4
            ), "T2: Turn number should be 4"

            profile_t2 = state_t2_output.get("customer_profile_dynamic", {})
            objections_t2 = profile_t2.get("identified_objections", [])
            found_resolved_objection_t2 = any(
                objection_text.lower() in o.get("text", "").lower()
                and o.get("status") == "resolved"
                for o in objections_t2
            )
            assert (
                found_resolved_objection_t2
            ), f"T2: Objection '{objection_text}' should be resolved in profile: {objections_t2}"

            goal_t2 = state_t2_output.get("current_agent_goal")
            # Planner should resume INVESTIGATING_NEEDS, then immediately handle the question interruption -> CLARIFYING_USER_INPUT
            assert (
                goal_t2 is not None
                and goal_t2.get("goal_type") == "CLARIFYING_USER_INPUT"
            ), "T2: Goal should be CLARIFYING_USER_INPUT (for the question)"
            assert (
                question_text.lower()
                in goal_t2.get("goal_details", {}).get("text", "").lower()
            ), "T2: Goal details should contain question text"

            prev_goal_t2 = goal_t2.get("previous_goal_if_interrupted")
            assert (
                prev_goal_t2 is not None
                and prev_goal_t2.get("goal_type") == "INVESTIGATING_NEEDS"
            ), "T2: Previous goal (INVESTIGATING_NEEDS) not stored correctly"

            action_t2 = state_t2_output.get("last_agent_action")
            assert (
                action_t2 is not None
                and action_t2.get("action_type") == "ANSWER_DIRECT_QUESTION"
            ), "T2: Action should be ANSWER_DIRECT_QUESTION"
            assert (
                question_text.lower()
                in action_t2.get("details", {})
                .get("question_to_answer_text", "")
                .lower()
            ), "T2: Action details incorrect"

            messages_t2 = state_t2_output.get("messages", [])
            assert (
                len(messages_t2) == len(state_t1_output.get("messages", [])) + 2
            ), "T2: Message count incorrect"
            last_ai_message_t2 = messages_t2[-1]
            assert isinstance(
                last_ai_message_t2, AIMessage
            ), "T2: Last message should be AI answer"
            assert (
                "prazo" in last_ai_message_t2.content.lower()
                or "entrega" in last_ai_message_t2.content.lower()
            ), "T2: Answer should address delivery time"
            logger.info(
                f"Multi-Interrupt T2 - Generated AI Answer: {last_ai_message_t2.content}"
            )

            logger.success("Multi-Interrupt Test - Turn 2 (Question Handling) PASSED!")
            logger.success(
                "Multi-Interrupt Test (Objection + Question) PASSED Overall!"
            )

        except AssertionError as e:
            logger.error(f"Assertion failed in multi-interrupt test: {e}")
            if state_t1_output:
                logger.debug(f"State T1 Output for review: {state_t1_output}")
            if "state_t2_output" in locals() and state_t2_output:
                logger.debug(f"State T2 Output for review: {state_t2_output}")
            raise
        except Exception as e:
            logger.exception(f"Error during Multi-Interrupt Test: {e}")
            assert False, f"Multi-Interrupt Test Failed: {e}"
        finally:
            # await checkpointer.close()
            logger.info(f"--- {test_name} Finished ---")


# --- Bloco para Execução Direta (Corrigido) ---
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.info("Starting integration test script (Multi-Interruption)...")

    # --- Criar o estado inicial manualmente (simulando a fixture) ---
    # É importante que esta lógica seja idêntica à da fixture
    initial_goal_main = AgentGoal(
        goal_type="INVESTIGATING_NEEDS",
        previous_goal_if_interrupted=None,
        goal_details={
            "spin_questions_asked_this_cycle": 1,
            "last_spin_type_asked": "Problem",
        },
    )
    last_ai_message_main = (
        "Entendo. E qual o maior problema que você enfrenta com sua solução atual?"
    )
    initial_state_main = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "MultiTest Co",
            "language": "pt-br",
            "sales_tone": "eficiente",
            "fallback_contact_info": "multitest.com",
            "business_description": "Testando interrupções.",
            "offering_overview": [
                {"name": "Produto Multi", "short_description": "Resolve A e B"}
            ],
            "key_selling_points": ["Ponto A", "Ponto B"],
            "address": None,
            "opening_hours": None,
            "communication_guidelines": [],
        },
        agent_config={},
        messages=[
            HumanMessage(content="Preciso de ajuda."),
            AIMessage(content=last_ai_message_main),
        ],
        current_user_input_text="",
        current_turn_number=2,
        current_agent_goal=initial_goal_main,
        last_agent_action=PendingAgentAction(
            action_type="ASK_SPIN_QUESTION",
            details={"spin_type": "Problem"},
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
        # Passar o estado criado manualmente para a função de teste
        asyncio.run(test_multi_interruption_objection_and_question(initial_state_main))
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Multi-Interruption) finished.")
