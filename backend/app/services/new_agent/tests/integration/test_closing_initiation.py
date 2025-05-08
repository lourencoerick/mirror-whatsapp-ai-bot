# backend/app/services/ai_reply/new_agent/test_closing_initiation.py

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
    ProposedSolution,  # Importar ProposedSolution
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


# --- Funções do Grafo (Copiar de test_objection_graph.py ou importar) ---


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
async def run_closing_initiation_test():
    """
    Tests the agent's transition to closing after a buying signal.
    """
    test_name = "Integration Test - Closing Initiation"
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
    db_file = "integration_test_closing_initiation_memory.sqlite"
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

        # --- Estado Inicial: Após apresentação da solução, sem objeções ---
        product_name = "Plano Super Rápido"
        product_price = 199.90
        presentation_message = f"Com base na sua necessidade de velocidade, o *{product_name}* seria ideal! Ele oferece [benefício X] e custa R${product_price:.2f}/mês. O que acha?"

        initial_messages: List[BaseMessage] = [
            HumanMessage(content="Preciso de algo mais rápido."),
            AIMessage(content=presentation_message),
        ]

        state_before_buying_signal = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text="",  # Será preenchido
            current_turn_number=2,  # Turno onde o agente apresentou
            current_agent_goal=AgentGoal(
                goal_type="PRESENTING_SOLUTION",
                goal_details={
                    "presenting_product": product_name,
                    "main_benefit_focus": "velocidade",
                },
            ),
            last_agent_action=PendingAgentAction(
                action_type="PRESENT_SOLUTION_OFFER",
                details={
                    "product_name_to_present": product_name,
                    "key_benefit_to_highlight": "velocidade",
                },
                action_generation_text=presentation_message,
                attempts=1,
            ),
            # Proposta ativa refletindo o que foi apresentado
            active_proposal=ProposedSolution(
                product_name=product_name,
                price=product_price,
                price_info="/mês",
                key_benefits_highlighted=["velocidade", "[benefício X]"],
                turn_proposed=2,
                status="proposed",
            ),
            customer_profile_dynamic={
                "identified_needs": [
                    IdentifiedNeedEntry(
                        text="velocidade", status="active", source_turn=1
                    )
                ],
                "identified_pain_points": [],
                "identified_objections": [],  # <<< Sem objeções ativas
                "certainty_levels": {},
                "last_discerned_intent": None,  # Será atualizado
            },
            company_profile={  # Perfil simples para o teste
                "company_name": "Vendas Rápidas Inc.",
                "language": "pt-br",
                "sales_tone": "prestativo",
                "fallback_contact_info": "site.com/ajuda",
                "business_description": "vends rapida para sua empresa",
                "offering_overview": [
                    {"name": "Plano X", "short_description": "Descrição do Plano X"}
                ],
                "key_selling_points": ["Ótimo Custo-Benefício"],
                "communication_guidelines": [],
            },
            agent_config={},
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=presentation_message,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )

        # --- Turno do Teste: Cliente dá sinal de compra ---
        logger.info(
            "\n--- Closing Initiation Test - Turn: User provides buying signal ---"
        )
        user_input_buying_signal = (
            "Perfeito! É isso mesmo que eu quero. Como faço para contratar?"
        )
        state_for_closing_invoke = copy.deepcopy(state_before_buying_signal)
        state_for_closing_invoke["current_user_input_text"] = user_input_buying_signal
        state_for_closing_invoke["messages"].append(
            HumanMessage(content=user_input_buying_signal)
        )
        # current_turn_number (2) será incrementado para 3 pelo StateUpdater

        try:
            final_state_closing: RichConversationState = await graph_app.ainvoke(
                state_for_closing_invoke, config=config_closing
            )

            logger.info(
                f"Closing Test - Input State for invoke: {state_for_closing_invoke}"
            )
            logger.info(
                f"Closing Test - Output State from invoke: {final_state_closing}"
            )

            # --- Asserts ---
            assert (
                final_state_closing.get("current_turn_number") == 3
            ), "Turn number should increment"

            # Verificar Goal
            final_goal = final_state_closing.get("current_agent_goal")
            assert final_goal is not None, "Current agent goal should exist"
            assert (
                final_goal.get("goal_type") == "ATTEMPTING_CLOSE"
            ), "Goal should be ATTEMPTING_CLOSE"
            assert (
                final_goal.get("goal_details", {}).get("closing_step")
                == "initial_attempt"
            ), "Closing step should be initial_attempt"

            # Verificar Última Ação
            final_action = final_state_closing.get("last_agent_action")
            assert final_action is not None, "Last agent action should exist"
            assert (
                final_action.get("action_type") == "INITIATE_CLOSING"
            ), "Action type should be INITIATE_CLOSING"
            # Verificar se detalhes da proposta foram passados (se existiam)
            assert final_action.get("details", {}).get("product_name") == product_name
            assert final_action.get("details", {}).get("price") == product_price

            # Verificar Mensagem Gerada
            final_messages = final_state_closing.get("messages", [])
            assert (
                len(final_messages) == len(initial_messages) + 2
            ), "Should have initial messages + user input + AI response"
            last_ai_message = final_messages[-1]
            assert isinstance(
                last_ai_message, AIMessage
            ), "Last message should be from AI"
            logger.info(
                f"Closing Test - Generated AI Message: {last_ai_message.content}"
            )
            # Verificar conteúdo da mensagem (pode precisar de ajuste dependendo do LLM)
            assert (
                "ótimo" in last_ai_message.content.lower()
                or "perfeito" in last_ai_message.content.lower()
            ), "AI message should acknowledge positively"
            assert (
                "gostaria de prosseguir" in last_ai_message.content.lower()
                or "vamos finalizar" in last_ai_message.content.lower()
            ), "AI message should ask to proceed"
            assert (
                product_name.lower() in last_ai_message.content.lower()
            ), f"AI message should mention product '{product_name}'"

            # Verificar Status do Fechamento (Opcional - depende de onde é atualizado)
            # Se o StateUpdater atualizar baseado no intent:
            # assert final_state_closing.get("closing_process_status") == "attempt_made", "Closing status should be attempt_made"
            # Se for atualizado após a ação:
            # assert final_state_closing.get("closing_process_status") == "not_started", "Closing status might not be updated yet"
            # Por enquanto, vamos focar no goal e na ação.

            logger.success("Closing Initiation Test PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in closing initiation test: {e}")
            logger.debug(
                f"Final State for review: {final_state_closing if 'final_state_closing' in locals() else 'N/A'}"
            )
            raise
        except Exception as e:
            logger.exception(f"Error during Closing Initiation Test: {e}")
            assert False, f"Closing Initiation Test Failed: {e}"
        finally:
            logger.info("--- Closing Initiation Test Section Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Closing Initiation)...")
    try:
        asyncio.run(run_closing_initiation_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Closing Initiation) finished.")
