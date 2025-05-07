# backend/app/services/ai_reply/new_agent/graph.py

import asyncio
from typing import Dict, Any, Optional, List, Literal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import os
import time
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import copy
from loguru import logger

# LangChain e OpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import AzureChatOpenAI

# Componentes locais
from .state_definition import RichConversationState  # Importar o estado principal
from .components.input_processor import process_user_input_node
from .components.state_updater import update_conversation_state_node
from .components.planner import goal_and_action_planner_node
from .components.knowledge_retriever import knowledge_retriever_node
from .components.response_generator import response_generator_node
from .components.output_formatter import output_formatter_node
from .components.final_state_updater import finalize_turn_state_node

from app.services.new_agent.components.planner import (
    MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION,  # Import to verify against
)

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


from .state_definition import (
    IdentifiedNeedEntry,
    PendingAgentAction,
    AgentGoal,
    IdentifiedPainPointEntry,
    IdentifiedObjectionEntry,
)
from app.database import AsyncSessionLocal

# --- Função de Roteamento Condicional ---


def route_action(
    state: RichConversationState,
) -> Literal["knowledge_retriever", "response_generator", "__end__"]:
    """
    Determines the next node based on the planned action command.
    Routes to RAG if needed, otherwise directly to response generation.

    Args:
        state: The current conversation state.

    Returns:
        The name of the next node or END.
    """
    action_command = state.get("next_agent_action_command")
    logger.debug(f"[Router: route_action] Planned action: {action_command}")

    actions_requiring_rag = [
        "ANSWER_DIRECT_QUESTION",
        "GENERATE_REBUTTAL",
    ]

    if action_command in actions_requiring_rag:
        logger.info("[Router: route_action] Routing to knowledge_retriever.")
        return "knowledge_retriever"
    elif action_command:
        logger.info("[Router: route_action] Routing directly to response_generator.")
        return "response_generator"
    else:
        logger.info("[Router: route_action] No action planned. Ending turn.")
        return END


# --- Função para Criar o Grafo Completo ---
def create_agent_graph_v2_complete(checkpointer):
    """
    Creates the complete agent graph with all integrated components.

    Args:
        checkpointer: The checkpointer for saving graph state.

    Returns:
        The compiled LangGraph application.
    """
    workflow = StateGraph(RichConversationState)
    logger.info("Initializing New Agent Graph (v2 - Complete)...")

    workflow.add_node("process_input", process_user_input_node)
    workflow.add_node("update_state", update_conversation_state_node)
    workflow.add_node("planner", goal_and_action_planner_node)
    workflow.add_node("knowledge_retriever", knowledge_retriever_node)
    workflow.add_node("response_generator", response_generator_node)
    workflow.add_node("output_formatter", output_formatter_node)
    workflow.add_node("finalize_turn_state", finalize_turn_state_node)

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

    logger.info("Compiling New Agent Graph (v2 - Complete)...")
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("New Agent Graph (v2 - Complete) compiled successfully.")
    return compiled_graph


async def run_integration_test_full_cycle():
    """
    Runs an integration test for the full objection handling cycle.
    """
    # Ensure MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION is 2 for these tests.
    if MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION != 2:
        logger.warning(
            f"MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION is {MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION}, "
            "but tests are designed for a limit of 2. Results may vary."
        )

    test_name = "Integration Test Full Cycle - Rebuttal Scenarios"
    logger.info(f"--- Starting {test_name} ---")
    log_file_name = f"{test_name.lower().replace(' ', '_').replace('-', '_')}.log"
    # Configure logger for this test run
    try:
        logger.remove()  # Remove default console logger if it exists
    except ValueError:
        pass  # No default handler to remove
    logger.add(sys.stderr, level="INFO")  # Add back a console logger for INFO
    logger.add(
        log_file_name, rotation="1 MB", level="DEBUG", backtrace=True, diagnose=True
    )

    llm_fast_real: Optional[AzureChatOpenAI] = None
    llm_primary_real: Optional[AzureChatOpenAI] = None
    try:
        if not SETTINGS_AVAILABLE:
            raise ValueError("Settings module not available.")
        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError("Azure OpenAI Endpoint or API Key not configured.")

        llm_instance = AzureChatOpenAI(
            azure_deployment="gpt-4o",  # Ensure this deployment exists
            temperature=0,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            max_retries=2,
            request_timeout=90,
        )
        llm_fast_real = llm_instance
        llm_primary_real = llm_instance
        logger.info(f"Using AzureChatOpenAI model: gpt-4o for fast and primary.")
    except Exception as e:
        logger.exception(
            f"Failed to initialize AzureChatOpenAI: {e}. Test will be skipped."
        )
        return

    db_file = "integration_test_rebuttal_cycle_memory.sqlite"
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
        logger.info(f"Removed previous test database: {db_file}")
    except OSError as e:
        logger.warning(f"Could not remove previous test database {db_file}: {e}")

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        logger.info(f"Using SqliteSaver checkpointer with db: {db_file}")
        graph_app = create_agent_graph_v2_complete(checkpointer=checkpointer)

        # Base config - LLM instances and db_session_factory are shared
        base_configurable_items = {
            "llm_fast_instance": llm_fast_real,
            "llm_primary_instance": llm_primary_real,
            "db_session_factory": AsyncSessionLocal,  # Using real DB session for RAG
        }

        # ================================================================================
        # Cenário de Teste: Ciclo de Objeção Completo
        # ================================================================================
        logger.info("\n--- Test Scenario: Full Objection Handling Cycle ---")

        common_initial_messages_obj_cycle: List[BaseMessage] = [
            HumanMessage(content="Olá, me fale sobre o Plano X."),
            AIMessage(
                content="Olá! O Plano X é excelente para [benefício chave]. Ele custa Y e inclui Z."
            ),
        ]
        common_company_profile_obj_cycle = {
            "company_name": "Objection Master Co",
            "language": "pt-br",
            "sales_tone": "confiante",
            "fallback_contact_info": "Consulte nosso FAQ em faq.com",
            "business_description": "Vendemos o Plano X, a melhor solução para seus problemas.",
            "offering_overview": [
                {
                    "name": "Plano X",
                    "short_description": "Descrição detalhada do Plano X",
                    "price_info": "Custa Y",
                }
            ],
            "key_selling_points": [
                "Ótimo Custo-Benefício",
                "Suporte 24/7",
                "Fácil Integração",
            ],
            "communication_guidelines": ["Ser direto", "Focar em valor"],
        }
        base_state_obj_cycle = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(common_initial_messages_obj_cycle),
            current_user_input_text="",
            current_turn_number=1,  # Starting turn
            current_agent_goal=AgentGoal(
                goal_type="PRESENTING_SOLUTION",
                goal_details={"presenting_product": "Plano X"},
            ),
            last_agent_action=PendingAgentAction(
                action_type="PRESENT_SOLUTION_OFFER",
                details={},
                action_generation_text=common_initial_messages_obj_cycle[-1].content,
                attempts=1,
            ),
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": None,
            },
            company_profile=common_company_profile_obj_cycle,  # type: ignore
            agent_config={},  # type: ignore
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=common_initial_messages_obj_cycle[-1].content,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )

        # --- Turno 1: Cliente levanta objeção "preço alto" ---
        logger.info(
            "\n--- Objection Cycle - Turn 1: User raises 'price too high' objection ---"
        )
        thread_id_obj_cycle = str(uuid4())

        # CORRECTED CONFIG CREATION:
        config_obj_cycle = {
            "configurable": {
                **base_configurable_items,  # Spread the shared items
                "thread_id": thread_id_obj_cycle,  # Add thread-specific item
            }
        }

        user_input_t1 = "O Plano X parece bom, mas o preço é muito alto."
        core_objection_phrase_t1 = "preço é muito alto"  # Expected core phrase
        state_t1_input = copy.deepcopy(base_state_obj_cycle)  # state can be deepcopied
        state_t1_input["current_user_input_text"] = user_input_t1
        state_t1_input["messages"].append(HumanMessage(content=user_input_t1))
        # current_turn_number will be incremented by StateUpdater to 2

        try:
            state_t1_output: RichConversationState = await graph_app.ainvoke(
                state_t1_input, config=config_obj_cycle
            )
            logger.info(f"ObjCycle T1 - Input State for invoke: {state_t1_input}")
            logger.info(f"ObjCycle T1 - Output State from invoke: {state_t1_output}")

            logger.info(
                f"ObjCycle T1 - Agent Goal: {state_t1_output.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"ObjCycle T1 - Agent Action Type: {state_t1_output.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"ObjCycle T1 - Agent Response: {state_t1_output.get('last_agent_action',{}).get('action_generation_text')}"
            )

            assert state_t1_output.get("current_turn_number") == 2

            profile_t1 = state_t1_output.get("customer_profile_dynamic", {})
            objections_t1 = profile_t1.get("identified_objections", [])

            assert (
                state_t1_output.get("current_agent_goal", {}).get("goal_type")
                == "HANDLING_OBJECTION"
            )
            original_objection_text_in_goal = (
                state_t1_output.get("current_agent_goal", {})
                .get("goal_details", {})
                .get("original_objection_text", "")
            )
            # Check if the core phrase is in the goal details
            assert (
                core_objection_phrase_t1.lower()
                in original_objection_text_in_goal.lower()
            ), f"Expected core objection phrase '{core_objection_phrase_t1}' in goal details, got '{original_objection_text_in_goal}'"

            action_type = state_t1_output.get("last_agent_action", {}).get(
                "action_type"
            )
            assert action_type == "GENERATE_REBUTTAL"

            assert len(objections_t1) == 1
            # Find the objection entry using the core phrase
            obj_entry_t1 = next(
                (
                    o
                    for o in objections_t1
                    if core_objection_phrase_t1.lower() in o.get("text", "").lower()
                ),
                None,
            )
            assert obj_entry_t1 is not None, (
                f"Core objection phrase '{core_objection_phrase_t1}' not found in profile objections: {objections_t1}. "
                f"User input was: '{user_input_t1}'"
            )

            assert obj_entry_t1.get("status") == "addressing"
            assert obj_entry_t1.get("rebuttal_attempts") == 1
            assert obj_entry_t1.get("source_turn") == 2

            logger.success(
                "ObjCycle T1: Objection raised, rebuttal planned, and profile updated successfully."
            )

            # --- Turno 2 (Cenário 2b): Objeção Persiste (Abaixo do Limite) ---
            logger.info(
                "\n--- Objection Cycle - Turn 2 (Scenario 2b): Objection persists, below limit ---"
            )
            user_input_t2b = "Entendo os benefícios, mas ainda acho caro."
            state_t2b_input = copy.deepcopy(state_t1_output)  # state can be deepcopied
            state_t2b_input["current_user_input_text"] = user_input_t2b
            state_t2b_input["messages"].append(HumanMessage(content=user_input_t2b))
            # current_turn_number (2) will be incremented by StateUpdater to 3

            # config_obj_cycle can be reused as thread_id is the same and LLM instances are shared

            state_t2b_output: RichConversationState = await graph_app.ainvoke(
                state_t2b_input, config=config_obj_cycle
            )
            logger.info(f"ObjCycle T2b - Input State for invoke: {state_t2b_input}")
            logger.info(f"ObjCycle T2b - Output State from invoke: {state_t2b_output}")

            logger.info(
                f"ObjCycle T2b - Agent Goal: {state_t2b_output.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"ObjCycle T2b - Agent Action Type: {state_t2b_output.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"ObjCycle T2b - Agent Response: {state_t2b_output.get('last_agent_action',{}).get('action_generation_text')}"
            )

            assert state_t2b_output.get("current_turn_number") == 3

            profile_t2b = state_t2b_output.get("customer_profile_dynamic", {})
            objections_t2b = profile_t2b.get("identified_objections", [])

            # Assuming the StateUpdater change IS made (does not increment attempts on "still_persists")
            # And MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION is 2
            assert (
                state_t2b_output.get("current_agent_goal", {}).get("goal_type")
                == "HANDLING_OBJECTION"
            )
            assert (
                state_t2b_output.get("last_agent_action", {}).get("action_type")
                == "GENERATE_REBUTTAL"
            )

            # Find the original objection entry using the core phrase
            obj_entry_t2b = next(
                (
                    o
                    for o in objections_t2b
                    if core_objection_phrase_t1.lower() in o.get("text", "").lower()
                ),
                None,
            )
            assert (
                obj_entry_t2b is not None
            ), f"Original core objection phrase '{core_objection_phrase_t1}' not found in profile after T2b: {objections_t2b}"

            assert obj_entry_t2b.get("status") == "addressing"
            assert obj_entry_t2b.get("rebuttal_attempts") == 2
            assert obj_entry_t2b.get("source_turn") == 2

            logger.success(
                "ObjCycle T2b: Objection persists, second rebuttal planned and profile updated successfully."
            )

            # --- Turno 3 (Cenário 2c): Objeção Persiste (Limite Atingido) ---
            logger.info(
                "\n--- Objection Cycle - Turn 3 (Scenario 2c): Objection persists, LIMIT REACHED ---"
            )
            user_input_t3c = "Não, realmente não dá. O preço é o problema."
            state_t3c_input = copy.deepcopy(state_t2b_output)  # state can be deepcopied
            state_t3c_input["current_user_input_text"] = user_input_t3c
            state_t3c_input["messages"].append(HumanMessage(content=user_input_t3c))
            # current_turn_number (3) will be incremented by StateUpdater to 4

            state_t3c_output: RichConversationState = await graph_app.ainvoke(
                state_t3c_input, config=config_obj_cycle  # Same thread
            )
            logger.info(f"ObjCycle T3c - Input State for invoke: {state_t3c_input}")
            logger.info(f"ObjCycle T3c - Output State from invoke: {state_t3c_output}")

            logger.info(
                f"ObjCycle T3c - Agent Goal: {state_t3c_output.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"ObjCycle T3c - Agent Action Type: {state_t3c_output.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"ObjCycle T3c - Agent Response: {state_t3c_output.get('last_agent_action',{}).get('action_generation_text')}"
            )

            assert state_t3c_output.get("current_turn_number") == 4

            profile_t3c = state_t3c_output.get("customer_profile_dynamic", {})
            objections_t3c = profile_t3c.get("identified_objections", [])

            # Planner should detect attempts=2, which is not < MAX_ATTEMPTS (2), leading to impasse.

            goal_type = state_t3c_output.get("current_agent_goal", {}).get("goal_type")
            # logger.info(f"state T3C : {state_t3c_output}")
            assert goal_type == "ENDING_CONVERSATION"
            assert (
                state_t3c_output.get("last_agent_action", {}).get("action_type")
                == "ACKNOWLEDGE_AND_TRANSITION"
            )  # Impasse action

            # Find the original objection entry using the core phrase
            obj_entry_t3c = next(
                (
                    o
                    for o in objections_t3c
                    if core_objection_phrase_t1.lower() in o.get("text", "").lower()
                ),
                None,
            )
            assert (
                obj_entry_t3c is not None
            ), f"Original core objection phrase '{core_objection_phrase_t1}' not found in profile after T3c: {objections_t3c}"

            assert obj_entry_t3c.get("status") == "active"  # Remains active
            assert obj_entry_t3c.get("rebuttal_attempts") == 2  # Max attempts reached

            logger.success(
                "ObjCycle T3c: Impasse due to max rebuttal attempts handled successfully."
            )

        except AssertionError as e:
            logger.error(f"Assertion failed in objection cycle: {e}")
            # Log full states for debugging
            if "state_t1_input" in locals():
                logger.debug(f"State T1 Input for review: {state_t1_input}")
            if "state_t1_output" in locals():
                logger.debug(f"State T1 Output for review: {state_t1_output}")
            if "state_t2b_input" in locals():
                logger.debug(f"State T2b Input for review: {state_t2b_input}")
            if "state_t2b_output" in locals():
                logger.debug(f"State T2b Output for review: {state_t2b_output}")
            if "state_t3c_input" in locals():
                logger.debug(f"State T3c Input for review: {state_t3c_input}")
            if "state_t3c_output" in locals():
                logger.debug(f"State T3c Output for review: {state_t3c_output}")
            raise
        except Exception as e:
            logger.exception(f"Error during Objection Cycle Test: {e}")
            assert False, f"Objection Cycle Test Failed: {e}"
        finally:
            logger.info("--- Objection Cycle Test Section Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    import sys  # Import sys for logger configuration

    logger.info("Starting integration test script (Rebuttal Cycle)...")
    try:
        asyncio.run(run_integration_test_full_cycle())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Rebuttal Cycle) finished.")
