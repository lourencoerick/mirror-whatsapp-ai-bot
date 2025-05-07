# backend/app/services/ai_reply/new_agent/graph.py

import asyncio
from typing import Dict, Any, Optional, List
from uuid import uuid4
import os  # Para carregar variáveis de ambiente

from langgraph.graph import StateGraph, END

# Usar AsyncSqliteSaver diretamente
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from loguru import logger
import time

# LangChain e OpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

load_dotenv()
# Componentes locais
from .state_definition import (
    RichConversationState,
    CustomerQuestionEntry,
    PendingAgentAction,
)  # Importar tipos necessários
from .components.input_processor import process_user_input_node
from .schemas.input_analysis import UserInputAnalysisOutput  # Para validação no teste

from .components.state_updater import update_conversation_state_node
from .schemas.input_analysis import UserInputAnalysisOutput

# Configuração (Assumindo que está em app/config.py)
try:
    from app.config import get_settings

    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    logger.error(
        "Could not import get_settings from app.config. Ensure it exists and PYTHONPATH is correct."
    )

    # Definir um fallback ou levantar erro se as settings forem essenciais
    class MockSettings:
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
        AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

    def get_settings():
        return MockSettings()


# Placeholder para o próximo nó
# from .components.state_updater import update_conversation_state_node


def create_agent_graph_v2(checkpointer):
    """
    Creates the agent graph including InputProcessor and StateUpdater.
    """
    workflow = StateGraph(RichConversationState)
    logger.info("Initializing New Agent Graph (v2 - with StateUpdater)...")

    # --- Adicionar Nós ---
    logger.debug("Adding node: process_input")
    workflow.add_node("process_input", process_user_input_node)

    logger.debug("Adding node: update_state")
    # Substituir o placeholder pelo nó real
    workflow.add_node("update_state", update_conversation_state_node)

    # --- Definir Fluxo ---
    logger.debug("Defining graph flow...")
    workflow.set_entry_point("process_input")
    # O fluxo agora vai do processador para o atualizador de estado
    workflow.add_edge("process_input", "update_state")

    # O grafo ainda termina após a atualização do estado para podermos inspecionar
    # O próximo passo seria adicionar o Planner aqui.
    workflow.add_edge("update_state", END)

    logger.info("Compiling New Agent Graph (v2 - with StateUpdater)...")
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("New Agent Graph (v2 - with StateUpdater) compiled successfully.")
    return compiled_graph


# --- Função para Teste de Integração ---
async def run_integration_test_input_processor():
    """
    Runs an integration test focusing on the process_user_input_node
    using a real LLM instance and SqliteSaver.
    """
    logger.info("--- Starting Integration Test for Input Processor ---")
    logger.add(
        "integration_test_input_processor.log", rotation="1 MB", level="DEBUG"
    )  # Log detalhado

    # --- Configurar LLM Real ---
    llm_fast_real: Optional[AzureChatOpenAI] = None
    try:
        if not SETTINGS_AVAILABLE:
            logger.error("Settings module not available. Cannot initialize LLM.")
            return  # Sair se não puder carregar settings

        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError(
                "Azure OpenAI Endpoint or API Key not configured in settings/environment."
            )

        llm_fast_real = AzureChatOpenAI(
            azure_deployment="gpt-4o",  # Confirme se este deployment existe e está acessível
            temperature=0,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",  # Usar versão estável
            max_retries=2,
            request_timeout=60,  # Aumentar timeout para chamadas complexas
        )
        logger.info(
            f"Using AzureChatOpenAI model: gpt-4o from endpoint: {settings.AZURE_OPENAI_ENDPOINT}"
        )
        # Teste rápido de conectividade (opcional)
        # await llm_fast_real.ainvoke("Test prompt")
        # logger.info("LLM connectivity test successful.")

    except Exception as e:
        logger.exception(f"Failed to initialize AzureChatOpenAI: {e}")
        logger.error(
            "Ensure Azure OpenAI settings (endpoint, key) are correctly configured via app.config or environment variables."
        )
        return

    # --- Configurar Checkpointer ---
    # Usar um arquivo para persistência entre cenários se desejado, ou :memory: para isolamento total
    db_file = "integration_test_memory.sqlite"
    try:
        if os.path.exists(db_file):
            os.remove(db_file)  # Limpar DB de testes anterior
            logger.info(f"Removed previous test database: {db_file}")
    except OSError as e:
        logger.warning(f"Could not remove previous test database {db_file}: {e}")

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        graph_app = create_agent_graph_v2(checkpointer=checkpointer)
        # --- Cenário de Teste 1: Pergunta Simples, Sem Histórico ---
        logger.info("\n--- Test Scenario 1: Simple Question, No History ---")
        thread_id_1 = str(uuid4())
        config_1 = {
            "configurable": {
                "thread_id": thread_id_1,
                "llm_fast_instance": llm_fast_real,
            }
        }

        state_1_initial = RichConversationState(  # Renomeado para clareza
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            company_profile={"company_name": "Test Co"},
            agent_config={},
            messages=[],
            current_user_input_text="Quanto custa o plano básico?",
            current_turn_number=0,  # Começa no turno 0
            # ... (resto do estado inicial como antes, log vazio, etc) ...
            current_agent_goal={
                "goal_type": "IDLE",
                "previous_goal_if_interrupted": None,
                "goal_details": None,
            },
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
            user_input_analysis_result=None,  # Importante iniciar como None
        )
        state_1_initial["messages"] = [
            HumanMessage(content=state_1_initial["current_user_input_text"])
        ]

        try:
            logger.info(f"Invoking graph for Scenario 1 (Thread ID: {thread_id_1})...")
            # Passar o estado inicial
            final_state_1 = await graph_app.ainvoke(state_1_initial, config=config_1)

            logger.info("Scenario 1 Invocation Complete.")
            # Analisar o ESTADO FINAL após o StateUpdater
            logger.debug(f"Final State 1 Keys: {final_state_1.keys()}")
            logger.info(
                f"Final State 1 - Current Turn: {final_state_1.get('current_turn_number')}"
            )
            logger.info(
                f"Final State 1 - Question Log: {final_state_1.get('customer_question_log')}"
            )
            logger.info(
                f"Final State 1 - Interrupt Queue: {final_state_1.get('user_interruptions_queue')}"
            )
            logger.info(
                f"Final State 1 - Error: {final_state_1.get('last_processing_error')}"
            )
            # O resultado da análise deve ter sido consumido e limpo
            logger.info(
                f"Final State 1 - Analysis Result (should be None): {final_state_1.get('user_input_analysis_result')}"
            )

            # Asserts no estado final
            assert (
                final_state_1.get("current_turn_number") == 1
            ), "Turn number should be incremented"
            assert (
                final_state_1.get("last_processing_error") is None
            ), "Should be no processing error"
            assert (
                final_state_1.get("user_input_analysis_result") is None
            ), "Analysis result should be cleared"

            question_log_1 = final_state_1.get("customer_question_log", [])
            assert (
                len(question_log_1) >= 1
            ), "Question log should contain the new question"
            # Assert mais específico pode falhar devido à extração do LLM, mas podemos tentar:
            assert any(
                "plano básico" in q.get("extracted_question_core", "").lower()
                for q in question_log_1
            ), "Basic plan question expected in log"
            assert (
                question_log_1[-1]["status"] == "newly_asked"
            ), "New question status should be 'newly_asked'"
            assert (
                question_log_1[-1]["turn_asked"] == 1
            ), "New question turn should be 1"

            interrupt_queue_1 = final_state_1.get("user_interruptions_queue", [])
            assert (
                len(interrupt_queue_1) >= 1
            ), "Interrupt queue should contain the new question"
            assert (
                interrupt_queue_1[-1]["type"] == "direct_question"
            ), "Interruption type should be 'direct_question'"
            assert (
                interrupt_queue_1[-1]["status"] == "pending_resolution"
            ), "Interruption status should be 'pending_resolution'"
            assert (
                interrupt_queue_1[-1]["turn_detected"] == 1
            ), "Interruption turn detected should be 1"
            logger.success("Scenario 1: Basic state updates verified.")

        except Exception as e:
            logger.exception(f"Error invoking graph for Scenario 1: {e}")

        # --- Cenário de Teste 2: Resposta à Ação + Nova Pergunta + Repetição ---
        logger.info("\n--- Test Scenario 2: Response + New Q + Repetition ---")
        thread_id_2 = str(uuid4())
        config_2 = {
            "configurable": {
                "thread_id": thread_id_2,
                "llm_fast_instance": llm_fast_real,
            }
        }

        # Estado inicial para o cenário 2
        previous_log_2 = [
            CustomerQuestionEntry(
                original_question_text="Qual o preço?",
                extracted_question_core="Qual o preço?",
                turn_asked=1,
                status="answered_with_fallback",  # <<< Status importante
                agent_direct_response_summary="Não tenho essa info.",
                repetition_of_turn=None,
                similarity_vector=None,
            )
        ]
        previous_agent_action_2 = PendingAgentAction(
            action_type="ASK_SPIN_QUESTION",
            details={"spin_type": "Problem"},
            action_generation_text="Quais os maiores desafios que você enfrenta hoje?",
            attempts=1,
        )
        previous_messages_2: List[BaseMessage] = [
            HumanMessage(content="Qual o preço?"),
            AIMessage(content="Não tenho essa info."),
            AIMessage(content=previous_agent_action_2["action_generation_text"]),
        ]

        state_2_initial = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            company_profile={"company_name": "Test Co"},
            agent_config={},
            messages=previous_messages_2,
            current_user_input_text="O maior desafio é o tempo gasto. Mas e o preço, qual é mesmo? E tem integração com X?",
            current_turn_number=2,  # Turno anterior foi 2
            current_agent_goal={
                "goal_type": "INVESTIGATING_NEEDS",
                "previous_goal_if_interrupted": None,
                "goal_details": None,
            },
            last_agent_action=previous_agent_action_2,
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
            },
            customer_question_log=previous_log_2,  # Log anterior
            current_turn_extracted_questions=[],
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=previous_agent_action_2[
                "action_generation_text"
            ],
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )
        state_2_initial["messages"].append(
            HumanMessage(content=state_2_initial["current_user_input_text"])
        )

        try:
            logger.info(f"Invoking graph for Scenario 2 (Thread ID: {thread_id_2})...")
            final_state_2 = await graph_app.ainvoke(state_2_initial, config=config_2)

            logger.info("Scenario 2 Invocation Complete.")
            logger.info(
                f"Final State 2 - Current Turn: {final_state_2.get('current_turn_number')}"
            )
            logger.info(
                f"Final State 2 - Question Log: {final_state_2.get('customer_question_log')}"
            )
            logger.info(
                f"Final State 2 - Interrupt Queue: {final_state_2.get('user_interruptions_queue')}"
            )
            logger.info(
                f"Final State 2 - Dynamic Profile: {final_state_2.get('customer_profile_dynamic')}"
            )
            logger.info(
                f"Final State 2 - Error: {final_state_2.get('last_processing_error')}"
            )
            logger.info(
                f"Final State 2 - Analysis Result (should be None): {final_state_2.get('user_input_analysis_result')}"
            )

            # Asserts no estado final
            assert (
                final_state_2.get("current_turn_number") == 3
            ), "Turn number should be incremented"
            assert (
                final_state_2.get("last_processing_error") is None
            ), "Should be no processing error"
            assert (
                final_state_2.get("user_input_analysis_result") is None
            ), "Analysis result should be cleared"

            question_log_2 = final_state_2.get("customer_question_log", [])
            # Esperamos 2 perguntas no log: a original de preço (atualizada) e a nova de integração
            assert len(question_log_2) == 2, "Should have 2 questions in log"

            price_q_log = next(
                (
                    q
                    for q in question_log_2
                    if "preço" in q.get("extracted_question_core", "").lower()
                ),
                None,
            )
            integration_q_log = next(
                (
                    q
                    for q in question_log_2
                    if "integração" in q.get("extracted_question_core", "").lower()
                ),
                None,
            )

            assert price_q_log is not None, "Price question should be in the log"
            assert (
                price_q_log["turn_asked"] == 1
            ), "Price question original turn should be 1"
            assert (
                price_q_log["status"] == "repetition_after_fallback"
            ), "Price question status should be updated to repetition_after_fallback"

            assert (
                integration_q_log is not None
            ), "Integration question should be in the log"
            assert (
                integration_q_log["turn_asked"] == 3
            ), "Integration question turn should be 3"
            assert (
                integration_q_log["status"] == "newly_asked"
            ), "Integration question status should be newly_asked"

            interrupt_queue_2 = final_state_2.get("user_interruptions_queue", [])
            # Esperamos ambas as perguntas na fila de interrupção
            assert (
                len(interrupt_queue_2) >= 2
            ), "Interrupt queue should contain at least the two questions"
            interrupt_texts_2 = {
                item["text"]
                for item in interrupt_queue_2
                if item["type"] == "direct_question"
            }
            assert any(
                "preço" in text.lower() for text in interrupt_texts_2
            ), "Price question should be in interrupt queue"
            assert any(
                "integração" in text.lower() for text in interrupt_texts_2
            ), "Integration question should be in interrupt queue"

            # Verificar se a dor foi adicionada ao perfil dinâmico
            dynamic_profile_2 = final_state_2.get("customer_profile_dynamic", {})
            assert (
                len(dynamic_profile_2.get("identified_pain_points", [])) >= 1
            ), "Pain point should be identified"
            assert any(
                "tempo gasto" in p.get("text", "").lower()
                for p in dynamic_profile_2.get("identified_pain_points", [])
            ), "Time spent pain point expected"

            logger.success(
                "Scenario 2: State updates for repetition and new question verified."
            )

        except Exception as e:
            logger.exception(f"Error invoking graph for Scenario 2: {e}")
        finally:
            # Fechar conexão do checkpointer
            # await checkpointer.aclose()  # Usar aclose() para AsyncSqliteSaver ou o método apropriado
            logger.info("Checkpointer connection closed.")


# --- Ponto de Entrada para Executar o Teste ---
if __name__ == "__main__":
    # Configurar logger para output claro no console também
    logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

    logger.info("Starting integration test script...")
    # Executar a função de teste
    # Nota: Se rodar via 'python -m ...', o asyncio.run é adequado.
    # Se estiver em um ambiente já com loop asyncio (como Jupyter), chame 'await run_integration_test_input_processor()'
    try:
        asyncio.run(run_integration_test_input_processor())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script finished.")
