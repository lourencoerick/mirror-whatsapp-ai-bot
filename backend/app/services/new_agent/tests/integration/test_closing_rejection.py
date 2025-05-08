# backend/app/services/ai_reply/new_agent/test_closing_rejection.py

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
async def run_closing_rejection_test():
    """
    Tests the agent's handling of a rejection during the closing process.
    """
    test_name = "Integration Test - Closing Rejection"
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
    db_file = "integration_test_closing_rejection_memory.sqlite"
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

        # --- Estado Inicial: Após agente iniciar fechamento (INITIATE_CLOSING) ---
        product_name = "Plano Teste"
        product_price = 50.00
        initiate_closing_message = (
            f"Legal! Quer prosseguir com o *{product_name}* (R${product_price:.2f})?"
        )

        initial_messages: List[BaseMessage] = [
            HumanMessage(content="Ok, quero esse."),
            AIMessage(content=initiate_closing_message),
        ]

        state_after_initiation = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text="",  # Será preenchido
            current_turn_number=3,
            current_agent_goal=AgentGoal(
                goal_type="ATTEMPTING_CLOSE",
                goal_details={"closing_step": "initial_attempt"},
                previous_goal_if_interrupted=None,
            ),
            last_agent_action=PendingAgentAction(
                action_type="INITIATE_CLOSING",
                details={"product_name": product_name, "price": product_price},
                action_generation_text=initiate_closing_message,
                attempts=1,
            ),
            active_proposal=ProposedSolution(
                product_name=product_name,
                price=product_price,
                price_info="",
                key_benefits_highlighted=[],
                turn_proposed=2,
                status="proposed",
            ),
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": "RequestForNextStepInPurchase",
            },
            company_profile={
                "company_name": "Rejeições SA",
                "language": "pt-br",
                "sales_tone": "compreensivo",
                "fallback_contact_info": "site.com/duvidas",
                "business_description": "rejeicoes",
            },
            agent_config={},
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            closing_process_status="attempt_made",  # Status após INITIATE_CLOSING
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=initiate_closing_message,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )

        # --- Turno do Teste: Cliente rejeita o fechamento ---
        logger.info(
            "\n--- Closing Rejection Test - Turn: User rejects closing initiation ---"
        )
        user_input_rejection = (
            "Ah, pensando bem, acho que vou esperar mais um pouco. Obrigado."
        )
        state_for_rejection_invoke = copy.deepcopy(state_after_initiation)
        state_for_rejection_invoke["current_user_input_text"] = user_input_rejection
        state_for_rejection_invoke["messages"].append(
            HumanMessage(content=user_input_rejection)
        )
        # current_turn_number (3) será incrementado para 4 pelo StateUpdater

        try:
            final_state_rejection: RichConversationState = await graph_app.ainvoke(
                state_for_rejection_invoke, config=config_closing
            )

            logger.info(
                f"Closing Rejection Test - Input State for invoke: {state_for_rejection_invoke}"
            )
            logger.info(
                f"Closing Rejection Test - Output State from invoke: {final_state_rejection}"
            )

            # --- Asserts ---
            assert (
                final_state_rejection.get("current_turn_number") == 4
            ), "Turn number should increment"

            # Verificar Status do Fechamento (Atualizado pelo StateUpdater)
            assert (
                final_state_rejection.get("closing_process_status")
                == "confirmation_rejected"
            ), "Closing status should be confirmation_rejected after user rejects"

            # Verificar Goal (Deve mudar para ENDING_CONVERSATION)
            final_goal = final_state_rejection.get("current_agent_goal")
            assert final_goal is not None, "Current agent goal should exist"
            assert (
                final_goal.get("goal_type") == "ENDING_CONVERSATION"
            ), "Goal should be ENDING_CONVERSATION"
            assert (
                final_goal.get("goal_details", {}).get("reason")
                == "Closing attempt rejected"
            ), "Goal reason should be set"

            # Verificar Última Ação (Planejada pelo Planner e registrada pelo FinalStateUpdater)
            final_action = final_state_rejection.get("last_agent_action")
            assert final_action is not None, "Last agent action should exist"
            assert (
                final_action.get("action_type") == "GENERATE_FAREWELL"
            ), "Action type should be GENERATE_FAREWELL"
            assert (
                final_action.get("details", {}).get("reason")
                == "Closing attempt rejected"
            ), "Action reason should be set"

            # Verificar Mensagem Gerada
            final_messages = final_state_rejection.get("messages", [])
            assert (
                len(final_messages) == len(initial_messages) + 2
            ), "Should have initial messages + user input + AI response"
            last_ai_message = final_messages[-1]
            assert isinstance(
                last_ai_message, AIMessage
            ), "Last message should be from AI"
            logger.info(
                f"Closing Rejection Test - Generated AI Message: {last_ai_message.content}"
            )
            # Verificar conteúdo da mensagem de despedida
            assert (
                "entendo" in last_ai_message.content.lower()
                or "compreendo" in last_ai_message.content.lower()
            ), "AI message should acknowledge rejection"
            assert (
                "obrigado pelo seu tempo" in last_ai_message.content.lower()
                or "agradeço" in last_ai_message.content.lower()
            ), "AI message should thank the user"
            assert (
                "se mudar de ideia" in last_ai_message.content.lower()
                or "estou à disposição" in last_ai_message.content.lower()
                or "site.com/duvidas" in last_ai_message.content.lower()
            ), "AI message should offer future help/info"

            logger.success("Closing Rejection Test PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in closing rejection test: {e}")
            logger.debug(
                f"Final State for review: {final_state_rejection if 'final_state_rejection' in locals() else 'N/A'}"
            )
            raise
        except Exception as e:
            logger.exception(f"Error during Closing Rejection Test: {e}")
            assert False, f"Closing Rejection Test Failed: {e}"
        finally:
            logger.info("--- Closing Rejection Test Section Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Closing Rejection)...")
    try:
        asyncio.run(run_closing_rejection_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Closing Rejection) finished.")
