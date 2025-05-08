# backend/app/services/ai_reply/new_agent/test_closing_correction_loop.py

import asyncio
import copy
import os
import sys
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from loguru import logger

# Componentes locais (ajuste os imports conforme sua estrutura)
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
from app.services.new_agent.components.output_formatter import (
    output_formatter_node,
)
from app.services.new_agent.components.planner import (
    goal_and_action_planner_node,
)
from app.services.new_agent.components.response_generator import (
    response_generator_node,
)
from app.services.new_agent.components.state_updater import (
    update_conversation_state_node,
)
from app.services.new_agent.state_definition import (
    AgentGoal,
    IdentifiedNeedEntry,
    IdentifiedObjectionEntry,
    IdentifiedPainPointEntry,
    PendingAgentAction,
    ProposedSolution,
    RichConversationState,
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


# --- Funções do Grafo (Copiar de outros testes ou importar) ---
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
    logger.info("Initializing New Agent Graph (v2 - Complete)...")
    nodes = [
        ("process_input", process_user_input_node),
        ("update_state", update_conversation_state_node),
        ("planner", goal_and_action_planner_node),
        ("knowledge_retriever", knowledge_retriever_node),
        ("response_generator", response_generator_node),
        ("output_formatter", output_formatter_node),
        ("finalize_turn_state", finalize_turn_state_node),
    ]
    for name, node in nodes:
        workflow.add_node(name, node)
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


# --- Função de Teste de Integração ---
async def run_closing_correction_loop_test():
    """
    Tests the agent handling a correction request and re-confirming details.
    """
    test_name = "Integration Test - Closing Correction Loop"
    logger.info(f"--- Starting {test_name} ---")
    log_file_name = f"{test_name.lower().replace(' ', '_').replace('-', '_')}.log"
    try:
        logger.remove()
    except ValueError:
        pass
    logger.add(sys.stderr, level="INFO")
    logger.add(
        log_file_name, rotation="1 MB", level="DEBUG", backtrace=True, diagnose=True
    )

    # --- Configurar LLM ---
    llm_fast_real: Optional[AzureChatOpenAI] = None
    llm_primary_real: Optional[AzureChatOpenAI] = None
    try:
        if not SETTINGS_AVAILABLE:
            raise ValueError("Settings module not available.")
        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError("Azure OpenAI Endpoint or API Key not configured.")
        llm_instance = AzureChatOpenAI(
            azure_deployment="gpt-4o",
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

    # --- Configurar Checkpointer ---
    db_file = "integration_test_closing_correction_loop_memory.sqlite"
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
        logger.info(f"Removed previous test database: {db_file}")
    except OSError as e:
        logger.warning(f"Could not remove previous test database {db_file}: {e}")

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        logger.info(f"Using SqliteSaver checkpointer with db: {db_file}")
        graph_app = create_agent_graph_v2_complete(checkpointer=checkpointer)

        # --- Configuração Base do Teste ---
        base_configurable_items = {
            "llm_fast_instance": llm_fast_real,
            "llm_primary_instance": llm_primary_real,
            "db_session_factory": AsyncSessionLocal,
        }
        thread_id_closing = str(uuid4())
        config_closing = {
            "configurable": {
                **base_configurable_items,
                "thread_id": thread_id_closing,
            }
        }

        # --- Estado Inicial: Após agente pedir confirmação dos detalhes (CONFIRM_ORDER_DETAILS) ---
        product_name = "Plano Essencial"
        product_price = 99.00
        price_info = "/mês"
        confirm_details_message = f"Ok! Só para confirmar, estamos prosseguindo com o *{product_name}* por R${product_price:.2f}{price_info}. Correto?"

        initial_messages: List[BaseMessage] = [
            HumanMessage(
                content="Sim, pode confirmar!"
            ),  # Resposta do user à INITIATE_CLOSING
            AIMessage(
                content=confirm_details_message
            ),  # Mensagem do agente pedindo confirmação final
        ]

        state_after_details_request = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text="",
            current_turn_number=4,
            current_agent_goal=AgentGoal(
                goal_type="ATTEMPTING_CLOSE",
                goal_details={"closing_step": "confirming_details"},
                previous_goal_if_interrupted=None,
            ),
            last_agent_action=PendingAgentAction(
                action_type="CONFIRM_ORDER_DETAILS",
                details={
                    "product_name": product_name,
                    "price": product_price,
                    "price_info": price_info,
                },
                action_generation_text=confirm_details_message,
                attempts=1,
            ),
            active_proposal=ProposedSolution(
                product_name=product_name,
                price=product_price,
                price_info=price_info,
                key_benefits_highlighted=["básico"],
                turn_proposed=2,
                status="proposed",
            ),
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": "ConfirmingCloseAttempt",
            },
            company_profile={
                "company_name": "Correções Ltda",
                "language": "pt-br",
                "sales_tone": "atencioso",
                "fallback_contact_info": "site.com/ajuda",
                "business_description": "correction",
            },
            agent_config={},
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            closing_process_status="awaiting_confirmation",  # <<< Status ANTES do pedido de correção
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=confirm_details_message,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )

        # --- Turno 1 do Teste: Cliente pede correção ---
        logger.info(
            "\n--- Closing Correction Loop - Turn 1: User requests correction ---"
        )
        user_input_correction_req = "Na verdade, o CEP está errado."
        state_t1_input = copy.deepcopy(state_after_details_request)
        state_t1_input["current_user_input_text"] = user_input_correction_req
        state_t1_input["messages"].append(
            HumanMessage(content=user_input_correction_req)
        )

        try:
            state_t1_output: RichConversationState = await graph_app.ainvoke(
                state_t1_input, config=config_closing
            )
            logger.info(f"Correction Loop T1 - Input State: {state_t1_input}")
            logger.info(f"Correction Loop T1 - Output State: {state_t1_output}")

            # Assert T1: Agent asks for correction details
            assert state_t1_output.get("current_turn_number") == 5
            assert state_t1_output.get("closing_process_status") == "needs_correction"
            assert (
                state_t1_output.get("current_agent_goal", {}).get("goal_type")
                == "ATTEMPTING_CLOSE"
            )
            assert (
                state_t1_output.get("last_agent_action", {}).get("action_type")
                == "HANDLE_CLOSING_CORRECTION"
            )
            last_msg_t1 = state_t1_output.get("messages", [])[-1]
            assert isinstance(last_msg_t1, AIMessage)
            assert (
                "corrigir" in last_msg_t1.content.lower()
                or "ajustar" in last_msg_t1.content.lower()
                or "corrigida" in last_msg_t1.content.lower()
            )
            logger.success(
                "Correction Loop T1: Agent correctly asked for correction details."
            )

            # --- Turno 2 do Teste: Cliente fornece a correção ---
            logger.info(
                "\n--- Closing Correction Loop - Turn 2: User provides correction ---"
            )
            user_input_correction_details = "O CEP correto é 12345-000."
            state_t2_input = copy.deepcopy(state_t1_output)
            state_t2_input["current_user_input_text"] = user_input_correction_details
            state_t2_input["messages"].append(
                HumanMessage(content=user_input_correction_details)
            )

            state_t2_output: RichConversationState = await graph_app.ainvoke(
                state_t2_input, config=config_closing
            )
            logger.info(f"Correction Loop T2 - Input State: {state_t2_input}")
            logger.info(f"Correction Loop T2 - Output State: {state_t2_output}")

            # Assert T2: Agent re-confirms details
            assert state_t2_output.get("current_turn_number") == 6
            # StateUpdater should set status back to awaiting_confirmation
            assert (
                state_t2_output.get("closing_process_status") == "awaiting_confirmation"
            )
            assert (
                state_t2_output.get("current_agent_goal", {}).get("goal_type")
                == "ATTEMPTING_CLOSE"
            )
            # Planner should now plan CONFIRM_ORDER_DETAILS again
            assert (
                state_t2_output.get("last_agent_action", {}).get("action_type")
                == "CONFIRM_ORDER_DETAILS"
            )
            last_msg_t2 = state_t2_output.get("messages", [])[-1]
            assert isinstance(last_msg_t2, AIMessage)
            assert (
                "confirmar" in last_msg_t2.content.lower()
                or "informar" in last_msg_t2.content.lower()
            )  # Check if it's asking for confirmation again
            assert (
                product_name.lower() in last_msg_t2.content.lower()
            )  # Should still mention product
            # Note: We are not testing if the *content* of the proposal was updated yet
            logger.success(
                "Correction Loop T2: Agent correctly asked for re-confirmation after correction."
            )

            # --- Turno 3 do Teste: Cliente confirma DE NOVO ---
            logger.info(
                "\n--- Closing Correction Loop - Turn 3: User confirms after correction ---"
            )
            user_input_final_confirm = "Agora sim, tudo certo!"
            state_t3_input = copy.deepcopy(state_t2_output)
            state_t3_input["current_user_input_text"] = user_input_final_confirm
            state_t3_input["messages"].append(
                HumanMessage(content=user_input_final_confirm)
            )

            state_t3_output: RichConversationState = await graph_app.ainvoke(
                state_t3_input, config=config_closing
            )
            logger.info(f"Correction Loop T3 - Input State: {state_t3_input}")
            logger.info(f"Correction Loop T3 - Output State: {state_t3_output}")

            # Assert T3: Agent processes the order
            assert state_t3_output.get("current_turn_number") == 7
            assert state_t3_output.get("closing_process_status") == "confirmed_success"
            assert (
                state_t3_output.get("current_agent_goal", {}).get("goal_type")
                == "ATTEMPTING_CLOSE"
            )  # Stays here until processed
            assert (
                state_t3_output.get("last_agent_action", {}).get("action_type")
                == "PROCESS_ORDER_CONFIRMATION"
            )
            last_msg_t3 = state_t3_output.get("messages", [])[-1]
            assert isinstance(last_msg_t3, AIMessage)
            assert (
                "pedido confirmado" in last_msg_t3.content.lower()
                or "processado com sucesso" in last_msg_t3.content.lower()
            )
            logger.success(
                "Correction Loop T3: Agent successfully processed order after correction loop."
            )

            logger.success("Closing Correction Loop Test PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in closing correction loop test: {e}")
            # Log intermediate states for easier debugging
            if "state_t1_output" in locals():
                logger.debug(f"State T1 Output for review: {state_t1_output}")
            if "state_t2_output" in locals():
                logger.debug(f"State T2 Output for review: {state_t2_output}")
            if "state_t3_output" in locals():
                logger.debug(f"State T3 Output for review: {state_t3_output}")
            raise
        except Exception as e:
            logger.exception(f"Error during Closing Correction Loop Test: {e}")
            assert False, f"Closing Correction Loop Test Failed: {e}"
        finally:
            logger.info("--- Closing Correction Loop Test Section Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Closing Correction Loop)...")
    try:
        asyncio.run(run_closing_correction_loop_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Closing Correction Loop) finished.")
