# backend/app/services/ai_reply/new_agent/test_closing_confirmation.py

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
    """
    Determines the next node based on the planned action command.

    Args:
        state: The current conversation state.

    Returns:
        The name of the next node or END.
    """
    action_command = state.get("next_agent_action_command")
    logger.debug(f"[Router: route_action] Planned action: {action_command}")
    actions_requiring_rag = ["ANSWER_DIRECT_QUESTION", "GENERATE_REBUTTAL"]
    if action_command in actions_requiring_rag:
        logger.info("[Router: route_action] Routing to knowledge_retriever.")
        return "knowledge_retriever"
    elif action_command:
        logger.info("[Router: route_action] Routing directly to response_generator.")
        return "response_generator"
    else:
        logger.info("[Router: route_action] No action planned. Ending turn.")
        return END


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


# --- Função de Teste de Integração ---
async def run_closing_confirmation_test():
    """
    Tests the agent's transition to confirming details after user confirms closing initiation.
    """
    test_name = "Integration Test - Closing Confirmation"
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
    db_file = "integration_test_closing_confirmation_memory.sqlite"
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
        product_name = "Plano Avançado"
        product_price = 299.00
        initiate_closing_message = f"Perfeito! Gostaria então de prosseguir com o pedido do *{product_name}* (R${product_price:.2f})?"

        initial_messages: List[BaseMessage] = [
            HumanMessage(
                content="Gostei, quero esse!"
            ),  # Mensagem que levou ao fechamento
            AIMessage(content=initiate_closing_message),  # Mensagem do agente iniciando
        ]

        state_after_initiation = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text="",  # Será preenchido
            current_turn_number=3,  # Turno onde o agente iniciou o fechamento
            current_agent_goal=AgentGoal(  # Goal definido pelo Planner no turno anterior
                goal_type="ATTEMPTING_CLOSE",
                goal_details={"closing_step": "initial_attempt"},
                previous_goal_if_interrupted=None,
            ),
            last_agent_action=PendingAgentAction(  # Ação realizada no turno anterior
                action_type="INITIATE_CLOSING",
                details={"product_name": product_name, "price": product_price},
                action_generation_text=initiate_closing_message,
                attempts=1,
            ),
            active_proposal=ProposedSolution(  # Proposta ativa
                product_name=product_name,
                price=product_price,
                price_info="",  # Ex: /mês
                key_benefits_highlighted=["benefício A", "benefício B"],
                turn_proposed=2,  # Turno em que foi proposta originalmente
                status="proposed",
            ),
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": "RequestForNextStepInPurchase",  # Intent que levou ao fechamento
            },
            company_profile={
                "company_name": "Fechamentos SA",
                "language": "pt-br",
                "sales_tone": "eficiente",
                "fallback_contact_info": "site.com/contato",
                "business_description": "Empresa especializada em fechamentos",
            },
            agent_config={},
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            # Status ANTES da confirmação do usuário
            closing_process_status="attempt_made",  # Ou o status que o StateUpdater definiria após INITIATE_CLOSING
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

        # --- Turno do Teste: Cliente confirma o início do fechamento ---
        logger.info(
            "\n--- Closing Confirmation Test - Turn: User confirms closing initiation ---"
        )
        user_input_confirmation = "Sim, pode confirmar!"
        state_for_confirmation_invoke = copy.deepcopy(state_after_initiation)
        state_for_confirmation_invoke["current_user_input_text"] = (
            user_input_confirmation
        )
        state_for_confirmation_invoke["messages"].append(
            HumanMessage(content=user_input_confirmation)
        )
        # current_turn_number (3) será incrementado para 4 pelo StateUpdater

        try:
            final_state_confirmation: RichConversationState = await graph_app.ainvoke(
                state_for_confirmation_invoke, config=config_closing
            )

            logger.info(
                f"Closing Confirmation Test - Input State for invoke: {state_for_confirmation_invoke}"
            )
            logger.info(
                f"Closing Confirmation Test - Output State from invoke: {final_state_confirmation}"
            )

            # --- Asserts ---
            assert (
                final_state_confirmation.get("current_turn_number") == 4
            ), "Turn number should increment"

            # Verificar Status do Fechamento (Atualizado pelo StateUpdater)
            assert (
                final_state_confirmation.get("closing_process_status")
                == "awaiting_confirmation"
            ), "Closing status should be awaiting_confirmation after user confirms"

            # Verificar Goal (Deve continuar tentando fechar)
            final_goal = final_state_confirmation.get("current_agent_goal")
            assert final_goal is not None, "Current agent goal should exist"
            assert (
                final_goal.get("goal_type") == "ATTEMPTING_CLOSE"
            ), "Goal should remain ATTEMPTING_CLOSE"
            # Opcional: verificar se goal_details foi atualizado pelo planner
            # assert final_goal.get("goal_details", {}).get("closing_step") == "confirming_details"

            # Verificar Última Ação (Planejada pelo Planner e registrada pelo FinalStateUpdater)
            final_action = final_state_confirmation.get("last_agent_action")
            assert final_action is not None, "Last agent action should exist"
            assert (
                final_action.get("action_type") == "CONFIRM_ORDER_DETAILS"
            ), "Action type should be CONFIRM_ORDER_DETAILS"
            # Verificar se detalhes da proposta foram passados para a ação
            assert final_action.get("details", {}).get("product_name") == product_name
            assert final_action.get("details", {}).get("price") == product_price

            # Verificar Mensagem Gerada
            final_messages = final_state_confirmation.get("messages", [])
            assert (
                len(final_messages) == len(initial_messages) + 2
            ), "Should have initial messages + user input + AI response"
            last_ai_message = final_messages[-1]
            assert isinstance(
                last_ai_message, AIMessage
            ), "Last message should be from AI"
            logger.info(
                f"Closing Confirmation Test - Generated AI Message: {last_ai_message.content}"
            )
            # Verificar conteúdo da mensagem de confirmação
            assert (
                "confirmar" in last_ai_message.content.lower()
            ), "AI message should ask for confirmation"
            assert (
                product_name.lower() in last_ai_message.content.lower()
            ), f"AI message should mention product '{product_name}'"
            assert (
                f"{product_price:.2f}" in last_ai_message.content
            ), f"AI message should mention price '{product_price:.2f}'"
            assert (
                "correto para seguirmos" in last_ai_message.content.lower()
                or "posso prosseguir" in last_ai_message.content.lower()
                or "confirma estes detalhes" in last_ai_message.content.lower()
            ), "AI message should ask for final confirmation"

            logger.success("Closing Confirmation Test PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in closing confirmation test: {e}")
            logger.debug(
                f"Final State for review: {final_state_confirmation if 'final_state_confirmation' in locals() else 'N/A'}"
            )
            raise
        except Exception as e:
            logger.exception(f"Error during Closing Confirmation Test: {e}")
            assert False, f"Closing Confirmation Test Failed: {e}"
        finally:
            logger.info("--- Closing Confirmation Test Section Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Closing Confirmation)...")
    try:
        asyncio.run(run_closing_confirmation_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Closing Confirmation) finished.")
