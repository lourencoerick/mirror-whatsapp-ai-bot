# backend/app/services/ai_reply/new_agent/graph.py

import asyncio
from typing import Dict, Any, Optional, List, Literal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import os
import time
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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
)
from app.database import AsyncSessionLocal

# --- Função de Roteamento Condicional ---


def route_action(
    state: RichConversationState,
) -> Literal["knowledge_retriever", "response_generator", "__end__"]:
    """
    Determines the next node based on the planned action command.
    Routes to RAG if needed, otherwise directly to response generation.
    """

    logger.debug(
        f"[Router: route_action] Received state keys: {state.keys()}"
    )  # LOG ADICIONAL
    logger.debug(
        f"[Router: route_action] Value of next_agent_action_command from state: {state.get('next_agent_action_command')}"
    )  # LOG ADICIONAL
    action_command = state.get("next_agent_action_command")
    logger.debug(f"[Router: route_action] Planned action: {action_command}")

    # Ações que normalmente precisam de RAG
    actions_requiring_rag = [
        "ANSWER_DIRECT_QUESTION",
        "GENERATE_REBUTTAL",
        # Adicionar outras ações se precisarem de RAG no futuro
    ]

    if action_command in actions_requiring_rag:
        logger.info("[Router: route_action] Routing to knowledge_retriever.")
        return "knowledge_retriever"
    elif action_command:  # Qualquer outro comando de ação planejado
        logger.info("[Router: route_action] Routing directly to response_generator.")
        return "response_generator"
    else:
        # Se o planner não definiu uma ação (ex: esperando input após objeção)
        logger.info("[Router: route_action] No action planned. Ending turn.")
        return END  # Termina o turno do agente


# --- Função para Criar o Grafo Completo ---
def create_agent_graph_v2_complete(checkpointer):
    """
    Creates the complete agent graph with all integrated components.
    """
    workflow = StateGraph(RichConversationState)
    logger.info("Initializing New Agent Graph (v2 - Complete)...")

    # --- Adicionar Nós ---
    logger.debug("Adding node: process_input")
    workflow.add_node("process_input", process_user_input_node)

    logger.debug("Adding node: update_state")
    workflow.add_node("update_state", update_conversation_state_node)

    logger.debug("Adding node: planner")
    workflow.add_node("planner", goal_and_action_planner_node)

    logger.debug("Adding node: knowledge_retriever")
    workflow.add_node("knowledge_retriever", knowledge_retriever_node)

    logger.debug("Adding node: response_generator")
    workflow.add_node("response_generator", response_generator_node)

    logger.debug("Adding node: output_formatter")
    workflow.add_node("output_formatter", output_formatter_node)

    logger.debug("Adding node: finalize_turn_state")
    workflow.add_node("finalize_turn_state", finalize_turn_state_node)

    # --- Definir Fluxo ---
    logger.debug("Defining graph flow...")

    # 1. Ponto de Entrada
    workflow.set_entry_point("process_input")

    # 2. Input -> Update State -> Planner
    workflow.add_edge("process_input", "update_state")
    workflow.add_edge("update_state", "planner")

    # 3. Planner -> Roteador Condicional -> Retriever ou Generator
    workflow.add_conditional_edges(
        "planner",  # Nó de origem
        route_action,  # Função de roteamento
        {
            "knowledge_retriever": "knowledge_retriever",  # Rota se RAG for necessário
            "response_generator": "response_generator",  # Rota se RAG não for necessário
            END: END,  # Rota se nenhuma ação for planejada
        },
    )

    # 4. Retriever -> Generator
    workflow.add_edge("knowledge_retriever", "response_generator")

    # 5. Generator -> Formatter -> Final State Update -> Fim do Turno
    workflow.add_edge("response_generator", "output_formatter")
    workflow.add_edge("output_formatter", "finalize_turn_state")
    workflow.add_edge("finalize_turn_state", END)  # O turno do agente termina aqui

    logger.info("Compiling New Agent Graph (v2 - Complete)...")
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("New Agent Graph (v2 - Complete) compiled successfully.")
    return compiled_graph


# --- Função para Teste de Integração Completo ---
async def run_integration_test_full_cycle():
    """
    Runs an integration test for a full conversation turn using the complete graph.
    """
    test_name = "Integration Test Full Cycle"
    logger.info(f"--- Starting {test_name} ---")
    logger.add(
        f"{test_name.lower().replace(' ', '_')}.log", rotation="1 MB", level="DEBUG"
    )

    # --- Configurar LLM Real ---
    llm_fast_real: Optional[AzureChatOpenAI] = None
    llm_primary_real: Optional[AzureChatOpenAI] = None  # Usaremos o mesmo por enquanto
    try:
        if not SETTINGS_AVAILABLE:
            raise ValueError("Settings module not available.")
        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError("Azure OpenAI Endpoint or API Key not configured.")

        # Usar o mesmo modelo para ambos por simplicidade no teste, mas poderiam ser diferentes
        llm_instance = AzureChatOpenAI(
            azure_deployment="gpt-4o",
            temperature=0,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            max_retries=2,
            request_timeout=90,  # Timeout maior
        )
        llm_fast_real = llm_instance
        llm_primary_real = llm_instance
        logger.info(f"Using AzureChatOpenAI model: gpt-4o for fast and primary.")
    except Exception as e:
        logger.exception(f"Failed to initialize AzureChatOpenAI: {e}")
        return

    # --- Configurar Checkpointer ---
    db_file = "integration_test_full_cycle_memory.sqlite"
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
        logger.info(f"Removed previous test database: {db_file}")
    except OSError as e:
        logger.warning(f"Could not remove previous test database {db_file}: {e}")

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        logger.info(f"Using SqliteSaver checkpointer with db: {db_file}")

        # --- Criar o Grafo ---
        graph_app = create_agent_graph_v2_complete(checkpointer=checkpointer)

        mock_db_factory = MagicMock()
        mock_db_factory.__aenter__.return_value = AsyncMock()
        mock_db_factory.__aexit__.return_value = None

        # ================================================================================
        # Cenário de Teste 1: Pergunta direta (RAG pode retornar vazio)
        # ================================================================================
        logger.info("\n--- Test Scenario 1: Direct Question (RAG may be empty) ---")
        thread_id_1 = str(uuid4())
        config_1 = {
            "configurable": {
                "thread_id": thread_id_1,
                "llm_fast_instance": llm_fast_real,
                "llm_primary_instance": llm_primary_real,
                "db_session_factory": mock_db_factory,
            }
        }
        state_1_initial = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            company_profile={
                "company_name": "DirectQ Test Co",
                "language": "pt-br",
                "sales_tone": "prestativo",
                "fallback_contact_info": "Consulte nosso site para mais informações.",
                "business_description": "Testamos perguntas diretas.",
                "offering_overview": [],
                "key_selling_points": [],
                "communication_guidelines": [],
            },
            agent_config={},
            messages=[],
            current_user_input_text="Qual é a garantia do produto XPTO?",
            current_turn_number=0,
            current_agent_goal={"goal_type": "IDLE"},
            last_agent_action=None,
            user_interruptions_queue=[],
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
            },
            customer_question_log=[],
            current_turn_extracted_questions=[],
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=None,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )
        state_1_initial["messages"] = [
            HumanMessage(content=state_1_initial["current_user_input_text"])
        ]

        try:
            logger.info(f"Invoking graph for Scenario 1 (Thread ID: {thread_id_1})...")
            final_state_1 = await graph_app.ainvoke(state_1_initial, config=config_1)

            logger.info("Scenario 1 Invocation Complete.")
            logger.info(
                f"Final State 1 - Current Turn: {final_state_1.get('current_turn_number')}"
            )
            logger.info(
                f"Final State 1 - Last Error: {final_state_1.get('last_processing_error')}"
            )
            final_messages_1 = final_state_1.get("messages", [])
            if len(final_messages_1) == 2:  # Human + AI
                logger.info(
                    f"Final State 1 - Last AI Message: {final_messages_1[-1].content}"
                )
                assert isinstance(final_messages_1[-1], AIMessage)
                # Como o RAG está mockado para retornar vazio, esperamos o fallback
                assert "Consulte nosso site" in final_messages_1[-1].content
            else:
                logger.error(
                    f"Scenario 1: Incorrect message count. Expected 2, got {len(final_messages_1)}"
                )
                assert False, "Scenario 1: Incorrect message count"
            logger.success("Scenario 1: Direct question flow verified.")
        except Exception as e:
            logger.exception(f"Error invoking graph for Scenario 1: {e}")

        # ================================================================================
        # Cenário de Teste 2: Transição SPIN -> Apresentação
        # ================================================================================
        logger.info("\n--- Test Scenario 2: SPIN Exit to Solution Presentation ---")
        thread_id_2 = str(uuid4())
        config_2 = {
            "configurable": {
                "thread_id": thread_id_2,
                "llm_fast_instance": llm_fast_real,
                "llm_primary_instance": llm_primary_real,
                "db_session_factory": mock_db_factory,  # Mock RAG para focar na lógica do planner/generator
            }
        }

        confirmed_need = IdentifiedNeedEntry(
            text="otimizar meu tempo de resposta ao cliente",
            status="confirmed_by_user",
            priority=8,
            source_turn=3,
        )
        last_spin_action = PendingAgentAction(
            action_type="ASK_SPIN_QUESTION",
            details={"spin_type": "NeedPayoff"},
            action_generation_text="E como otimizar esse tempo de resposta ajudaria seus resultados?",
            attempts=1,
        )
        spin_messages_hist: List[BaseMessage] = [
            HumanMessage(content="Tenho demorado muito para responder meus clientes."),
            AIMessage(
                content="Entendo. E qual o impacto dessa demora nos seus negócios?"
            ),
            HumanMessage(content="Perco vendas e os clientes ficam insatisfeitos."),
            AIMessage(content=last_spin_action["action_generation_text"]),
        ]
        current_user_input_s2 = "Ajudaria MUITO! Conseguiria fechar mais negócios e ter clientes mais felizes."

        initial_state_s2 = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            company_profile={
                "company_name": "Soluções Rápidas Ltda",
                "language": "pt-br",
                "sales_tone": "consultivo",
                "fallback_contact_info": "Visite nosso site para mais detalhes.",
                "business_description": "Ajudamos empresas a otimizar o atendimento ao cliente.",
                "offering_overview": [
                    {
                        "name": "Plano Atendimento Pro",
                        "short_description": "Ferramentas avançadas para resposta rápida.",
                        "key_features": ["IA", "Automação"],
                        "price_info": "R$299/mês",
                    },
                    {
                        "name": "Consultoria Express",
                        "short_description": "Análise e otimização do seu fluxo.",
                        "key_features": ["Diagnóstico", "Plano de Ação"],
                        "price_info": "R$1200",
                    },
                ],
                "key_selling_points": [
                    "Aumento de eficiência",
                    "Melhora satisfação do cliente",
                ],
                "communication_guidelines": ["Ser empático", "Focar em soluções"],
            },
            agent_config={},
            messages=list(spin_messages_hist),  # Cópia do histórico
            current_user_input_text=current_user_input_s2,
            current_turn_number=3,
            current_agent_goal=AgentGoal(
                goal_type="INVESTIGATING_NEEDS",
                goal_details={
                    "spin_questions_asked_this_cycle": 4,
                    "last_spin_type_asked": "NeedPayoff",
                },
                previous_goal_if_interrupted=None,
            ),
            last_agent_action=last_spin_action,
            user_interruptions_queue=[],
            customer_profile_dynamic={
                "identified_needs": [confirmed_need],
                "identified_pain_points": [
                    IdentifiedPainPointEntry(
                        text="Perco vendas e clientes insatisfeitos",
                        status="active",
                        source_turn=3,
                    )
                ],
                "identified_objections": [],
                "certainty_levels": {
                    "product": 6,
                    "agent": 7,
                    "company": 5,
                    "last_assessed_turn": 2,
                },
            },
            customer_question_log=[],
            current_turn_extracted_questions=[],
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=last_spin_action["action_generation_text"],
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )
        initial_state_s2["messages"].append(
            HumanMessage(content=initial_state_s2["current_user_input_text"])
        )

        try:
            logger.info(
                f"Invoking graph for SPIN Exit Scenario (Thread ID: {thread_id_2})..."
            )
            final_state_s2 = await graph_app.ainvoke(initial_state_s2, config=config_2)

            logger.info("SPIN Exit Scenario Invocation Complete.")
            logger.info(
                f"Final State S2 - Current Turn: {final_state_s2.get('current_turn_number')}"
            )
            logger.info(
                f"Final State S2 - Current Agent Goal: {final_state_s2.get('current_agent_goal')}"
            )
            logger.info(
                f"Final State S2 - Last Error: {final_state_s2.get('last_processing_error')}"
            )

            final_messages_s2 = final_state_s2.get("messages", [])
            initial_message_count_s2 = len(
                initial_state_s2.get("messages", [])
            )  # Contagem antes da AIMessage

            logger.info(
                f"SPIN Exit - Initial messages count for invoke: {initial_message_count_s2}"
            )
            logger.info(f"SPIN Exit - Final messages count: {len(final_messages_s2)}")

            assert (
                final_state_s2.get("last_processing_error") is None
            ), "Processing error occurred in S2"

            if (
                len(final_messages_s2) == initial_message_count_s2 + 1
            ):  # Espera uma nova AIMessage
                generated_ai_message = final_messages_s2[-1].content
                logger.info(
                    f"Final State S2 - Generated AI Message (Presentation):\n{generated_ai_message}"
                )
                assert isinstance(final_messages_s2[-1], AIMessage)

                # Verificar se a apresentação menciona o produto e o benefício
                # A lógica de seleção de produto no planner é:
                # Planner: Matched need 'otimizar meu tempo de resposta ao cliente' to product 'Plano Atendimento Pro' based on keywords.
                assert (
                    "plano atendimento pro" in generated_ai_message.lower()
                ), f"Expected 'Plano Atendimento Pro' in S2 presentation, got: {generated_ai_message}"
                assert (
                    "otimizar" in generated_ai_message.lower()
                    and "tempo de resposta" in generated_ai_message.lower()
                    and "cliente" in generated_ai_message.lower()
                ), f"Expected benefit in S2 presentation, got: {generated_ai_message}"
            else:
                logger.error(
                    f"SPIN Exit - Generated AI presentation message not found or incorrect message count. Expected {initial_message_count_s2 + 1}, got {len(final_messages_s2)}"
                )
                for i, msg in enumerate(final_messages_s2):
                    logger.debug(
                        f"  S2 Msg {i}: Type={msg.type}, Content='{msg.content[:100]}...'"
                    )
                assert (
                    False
                ), "SPIN Exit: AI presentation message not generated or message count incorrect."

            last_action_s2 = final_state_s2.get("last_agent_action")
            logger.info(
                f"Final State S2 - Last Agent Action Recorded: {last_action_s2}"
            )
            assert (
                last_action_s2 is not None
            ), "Last agent action should be recorded in S2"
            assert (
                last_action_s2.get("action_type") == "PRESENT_SOLUTION_OFFER"
            ), "Action type should be PRESENT_SOLUTION_OFFER in S2"

            logger.success("SPIN Exit Scenario: Full cycle to presentation verified.")

        except Exception as e:
            logger.exception(f"Error invoking graph for SPIN Exit Scenario: {e}")
        finally:
            # await checkpointer.aclose()
            logger.info("Checkpointer connection closed.")

    # --- Ponto de Entrada ---


if __name__ == "__main__":
    logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")
    logger.info("Starting integration test script (Full Cycle)...")
    try:
        asyncio.run(run_integration_test_full_cycle())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Full Cycle) finished.")
