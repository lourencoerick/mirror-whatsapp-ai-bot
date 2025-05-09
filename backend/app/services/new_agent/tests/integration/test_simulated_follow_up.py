# backend/app/services/ai_reply/new_agent/tests/integration/test_simulated_follow_up.py

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
from langgraph.graph import END, StateGraph  # StateGraph é usado em create_agent_graph
from loguru import logger

# Componentes locais e definições de estado
try:
    from app.database import AsyncSessionLocal
    from app.services.new_agent.graph import (
        create_agent_graph,
    )  # Importar do novo graph.py
    from app.services.new_agent.state_definition import (
        RichConversationState,
        AgentGoal,
        PendingAgentAction,
        # Para mock de user_input_analysis_result
    )

    # UserInputAnalysisOutput, PendingAgentActionResponseAnalysis
except ImportError as e:
    logger.error(
        f"Import error in test_simulated_follow_up.py: {e}. Ensure paths are correct and graph.py exists."
    )
    # Fallbacks para permitir a análise do arquivo, mas os testes falharão.
    AsyncSessionLocal = None
    create_agent_graph = lambda x: None
    RichConversationState = dict
    AgentGoal = dict
    PendingAgentAction = dict
    UserInputAnalysisOutput = dict
    PendingAgentActionResponseAnalysis = dict


# Configuração de LLM (similar a outros testes de integração)
try:
    from app.config import get_settings

    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    logger.error("Could not import get_settings from app.config.")

    class MockSettings:
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
        AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
        MAX_FOLLOW_UP_ATTEMPTS = 2  # Definir um valor para o teste

    def get_settings():
        return MockSettings()


# --- Fixture de Estado Base ---
@pytest.fixture
def base_state_for_follow_up_test() -> RichConversationState:
    """Fornece um estado inicial para o teste de follow-up."""
    agent_last_message_text = "O Plano X é ideal para você, pois oferece alta velocidade e suporte prioritário. O que acha de explorarmos os detalhes?"
    initial_goal = AgentGoal(
        goal_type="PRESENTING_SOLUTION",  # Agente acabou de apresentar uma solução
        goal_details={
            "presenting_product": "Plano X",
            "main_benefit_focus": "velocidade",
        },
        previous_goal_if_interrupted=None,
    )
    # Simular um user_input_analysis_result mínimo do turno anterior (que levou à apresentação da solução)
    # Este campo é limpo pelo FinalStateUpdater, então para o *início* do turno do agente, ele seria None.
    # No entanto, para o setup do *primeiro turno do teste*, podemos deixá-lo como None.

    settings = get_settings()  # Para obter MAX_FOLLOW_UP_ATTEMPTS

    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "FollowUp Inc.",
            "language": "pt-br",
            "sales_tone": "prestativo",
            "fallback_contact_info": "followup.inc/contato",
            "business_description": "Testando follow-ups.",
            "offering_overview": [
                {"name": "Plano X", "short_description": "Alta velocidade e suporte."}
            ],
            "key_selling_points": ["Alta velocidade", "Suporte prioritário"],
        },
        agent_config={
            "max_follow_up_attempts": getattr(settings, "MAX_FOLLOW_UP_ATTEMPTS", 2)
        },  # Usar da config
        messages=[
            HumanMessage(content="Preciso de algo rápido."),
            AIMessage(content=agent_last_message_text),  # Última mensagem do agente
        ],
        current_user_input_text=None,  # Começa sem input do usuário (para simular timeout)
        current_turn_number=2,  # Agente falou no turno 2
        current_agent_goal=initial_goal,
        last_agent_action=PendingAgentAction(
            action_type="PRESENT_SOLUTION_OFFER",
            details={
                "product_name_to_present": "Plano X",
                "key_benefit_to_highlight": "velocidade",
            },
            action_generation_text=agent_last_message_text,
            attempts=1,
        ),
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [
                {
                    "text": "velocidade",
                    "status": "active",
                    "priority": 1,
                    "source_turn": 1,
                }
            ],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
            "last_discerned_intent": "StatingInformationOrOpinion",  # Do input "Preciso de algo rápido"
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=agent_last_message_text,  # Texto da última geração do agente
        final_agent_message_text=agent_last_message_text,  # Texto que foi "enviado"
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time()
        - 70000,  # Simular que a última msg foi há muito tempo
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,  # Limpo no início do turno
        next_agent_action_command=None,
        action_parameters={},
        # Flags de Follow-up (serão setadas pelo FinalStateUpdater do turno anterior)
        follow_up_scheduled=True,  # Assumir que o turno anterior agendou
        follow_up_attempt_count=0,  # Nenhuma tentativa ainda
        last_message_from_agent_timestamp=time.time()
        - 70000,  # Timestamp da última msg do agente
        trigger_event=None,  # Será definido pelo "sistema externo" ao invocar
    )
    return state


# --- Teste de Integração ---
@pytest.mark.asyncio
async def test_simulated_follow_up_flow(
    base_state_for_follow_up_test: RichConversationState,
):
    """
    Tests the full follow-up flow:
    1. Agent sends a message. (Setup na fixture)
    2. FinalStateUpdater sets follow_up_scheduled=True. (Verificado implicitamente pelo setup)
    3. (Simulado) Timeout occurs. Graph is invoked with trigger_event="follow_up_timeout".
    4. Planner detects timeout, plans DECIDE_PROACTIVE_STEP.
    5. ProactiveStepDecider plans a follow-up action (e.g., ASK_CLARIFYING_QUESTION).
    6. Agent sends follow-up message.
    7. FinalStateUpdater updates follow_up_attempt_count and re-schedules (updates timestamp).
    8. (Simulado) Second timeout.
    9. Planner detects timeout, plans DECIDE_PROACTIVE_STEP with incremented attempt count.
    10. ProactiveStepDecider plans FAREWELL if max attempts reached.
    """
    test_name = "Integration Test - Simulated Follow-up Flow"
    logger.info(f"--- Starting {test_name} ---")

    # --- Configurar LLM e Grafo ---
    llm_instance: Optional[AzureChatOpenAI] = None
    try:
        if not SETTINGS_AVAILABLE:
            raise ValueError("Settings missing")
        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError("Credentials missing")
        llm_instance = AzureChatOpenAI(
            azure_deployment="gpt-4o",
            temperature=0.1,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
            max_retries=2,
            request_timeout=60,
        )
        logger.info(f"Using REAL AzureChatOpenAI model: gpt-4o for {test_name}")
    except Exception as e:
        logger.warning(
            f"Failed to initialize AzureChatOpenAI for {test_name}: {e}. Skipping test."
        )
        pytest.skip("Real LLM not available for follow-up test.")

    db_file = "integration_test_sim_follow_up_memory.sqlite"
    if os.path.exists(db_file):
        os.remove(db_file)

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        if not callable(create_agent_graph):
            pytest.fail("create_agent_graph function not available.")
        graph_app = create_agent_graph(checkpointer=checkpointer)
        if graph_app is None:
            pytest.fail("Failed to create graph application for follow-up test.")

        config_follow_up = {
            "configurable": {
                "thread_id": str(base_state_for_follow_up_test["conversation_id"]),
                "llm_primary_instance": llm_instance,
                "llm_fast_instance": llm_instance,  # Usar o mesmo para simplicidade no teste
                "llm_strategy_instance": llm_instance,  # Para o proactive_step_decider
                "db_session_factory": AsyncSessionLocal,
            }
        }

        # --- Turno 1: Simular Timeout e Primeiro Follow-up ---
        logger.info("\n--- Follow-up Test - Turn 1 (Simulated Timeout 1) ---")
        state_t1_input = copy.deepcopy(base_state_for_follow_up_test)
        state_t1_input["trigger_event"] = "follow_up_timeout"
        state_t1_input["current_user_input_text"] = None  # Sem input do usuário
        # follow_up_scheduled e follow_up_attempt_count já estão no estado base

        state_t1_output: Optional[RichConversationState] = None
        try:
            state_t1_output = await graph_app.ainvoke(
                state_t1_input, config=config_follow_up
            )
            assert state_t1_output is not None, "T1: Graph invocation returned None"

            logger.info(
                f"Follow-up T1 - Output State: {state_t1_output.get('last_agent_action')}"
            )

            # Verificar Planner
            # O Planner deve ter delegado para DECIDE_PROACTIVE_STEP,
            # e o ProactiveStepDecider deve ter planejado uma ação de follow-up.
            # A last_agent_action registrada será a ação de follow-up.
            last_action_t1 = state_t1_output.get("last_agent_action")
            assert last_action_t1 is not None, "T1: No last_agent_action recorded"
            # Esperamos que o LLM decida por ASK_CLARIFYING_QUESTION como follow-up
            assert (
                last_action_t1.get("action_type") == "ASK_CLARIFYING_QUESTION"
            ), f"T1: Expected follow-up action ASK_CLARIFYING_QUESTION, got {last_action_t1.get('action_type')}"
            assert (
                state_t1_output.get("follow_up_attempt_count") == 1
            ), "T1: follow_up_attempt_count should be 1"
            assert (
                state_t1_output.get("follow_up_scheduled") is True
            ), "T1: follow_up_scheduled should remain True for next attempt"

            messages_t1 = state_t1_output.get("messages", [])
            assert len(messages_t1) > 0, "T1: Message history should not be empty"
            last_ai_message_t1 = messages_t1[-1]
            assert isinstance(
                last_ai_message_t1, AIMessage
            ), "T1: Last message in history should be AIMessage"
            assert (
                last_ai_message_t1.content is not None
                and len(last_ai_message_t1.content) > 0
            ), "T1: Agent should have sent a follow-up message (checked from history)"
            logger.info(
                f"T1: Follow-up message from history: {last_ai_message_t1.content}"
            )
            assert (
                "continuar" in last_ai_message_t1.content.lower()
                or "ainda por aí" in last_ai_message_t1.content.lower()
                or "ajudar" in last_ai_message_t1.content.lower()
            ), f"T1: Follow-up message content seems incorrect: {last_ai_message_t1.content}"

            logger.success("Follow-up Test - Turn 1 (First Follow-up) PASSED!")

            # --- Turno 2: Simular Segundo Timeout e Último Follow-up (ou Despedida) ---
            logger.info("\n--- Follow-up Test - Turn 2 (Simulated Timeout 2) ---")
            state_t2_input = copy.deepcopy(
                state_t1_output
            )  # Usar o estado de saída do T1
            state_t2_input["trigger_event"] = "follow_up_timeout"
            state_t2_input["current_user_input_text"] = None
            state_t2_input["user_input_analysis_result"] = (
                None  # Limpar análise anterior
            )
            state_t2_input["last_processing_error"] = None  # Limpar erro anterior
            # last_message_from_agent_timestamp foi atualizado pelo FinalStateUpdater do T1

            state_t2_output: Optional[RichConversationState] = None
            state_t2_output = await graph_app.ainvoke(
                state_t2_input, config=config_follow_up
            )
            assert state_t2_output is not None, "T2: Graph invocation returned None"

            logger.info(
                f"Follow-up T2 - Output State: {state_t2_output.get('last_agent_action')}"
            )

            last_action_t2 = state_t2_output.get("last_agent_action")
            assert last_action_t2 is not None, "T2: No last_agent_action recorded"

            max_attempts = state_t2_output.get("agent_config", {}).get(
                "max_follow_up_attempts", 2
            )

            if (
                state_t1_output.get("follow_up_attempt_count", 0) < max_attempts
            ):  # Se T1 foi a tentativa 1 e max é 2, T2 é a tentativa 2
                assert (
                    last_action_t2.get("action_type") == "ASK_CLARIFYING_QUESTION"
                ), f"T2: Expected follow-up action ASK_CLARIFYING_QUESTION, got {last_action_t2.get('action_type')}"
                assert (
                    state_t2_output.get("follow_up_attempt_count") == 2
                ), "T2: follow_up_attempt_count should be 2"
                assert (
                    state_t2_output.get("follow_up_scheduled") is True
                ), "T2: follow_up_scheduled should be True if not max attempts"
                logger.info(
                    f"T2: Second follow-up message: {state_t2_output.get('final_agent_message_text')}"
                )
            else:  # Atingiu o limite de tentativas no T1, então T2 deve ser FAREWELL
                # Ou, se T1 foi a penúltima, T2 é a última tentativa antes do FAREWELL no próximo timeout.
                # A lógica atual do planner é: se current_attempts < max_attempts, tenta DECIDE_PROACTIVE_STEP.
                # Se current_attempts (que é o valor *antes* do incremento do planner para este turno)
                # já é >= max_attempts, ele vai para FAREWELL.
                # No nosso caso, T1 teve attempt_count=0 (passado para proactive), planner incrementou para 1 no estado.
                # T2 recebe attempt_count=1, planner incrementa para 2. Se max_attempts=2, o próximo timeout
                # receberá attempt_count=2, e o planner irá para FAREWELL.
                # Então, se max_attempts = 2, esta segunda chamada de timeout (T2) ainda deve ser ASK_CLARIFYING.
                assert (
                    last_action_t2.get("action_type") == "ASK_CLARIFYING_QUESTION"
                ), f"T2: Expected ASK_CLARIFYING_QUESTION as it's attempt {state_t1_output.get('follow_up_attempt_count',0)}, max {max_attempts}. Got {last_action_t2.get('action_type')}"
                assert (
                    state_t2_output.get("follow_up_attempt_count") == max_attempts
                ), f"T2: Expected attempt count {max_attempts}"

            logger.success(
                "Follow-up Test - Turn 2 (Second Follow-up/Farewell) PASSED!"
            )

            # --- Turno 3: Simular Terceiro Timeout - Deve ser FAREWELL se max_attempts = 2 ---
            if max_attempts == 2:  # Apenas se o limite for 2 para testar o farewell
                logger.info(
                    "\n--- Follow-up Test - Turn 3 (Simulated Timeout 3 - Max Attempts Reached) ---"
                )
                state_t3_input = copy.deepcopy(state_t2_output)
                state_t3_input["trigger_event"] = "follow_up_timeout"
                state_t3_input["current_user_input_text"] = None
                state_t3_input["user_input_analysis_result"] = None
                state_t3_input["last_processing_error"] = None

                state_t3_output: Optional[RichConversationState] = None
                state_t3_output = await graph_app.ainvoke(
                    state_t3_input, config=config_follow_up
                )
                assert state_t3_output is not None, "T3: Graph invocation returned None"

                logger.info(
                    f"Follow-up T3 - Output State: {state_t3_output.get('last_agent_action')}"
                )
                last_action_t3 = state_t3_output.get("last_agent_action")
                assert last_action_t3 is not None, "T3: No last_agent_action recorded"
                assert (
                    last_action_t3.get("action_type") == "GENERATE_FAREWELL"
                ), f"T3: Expected FAREWELL after max attempts, got {last_action_t3.get('action_type')}"
                assert (
                    state_t3_output.get("follow_up_scheduled") is False
                ), "T3: follow_up_scheduled should be False after farewell"
                assert (
                    state_t3_output.get("follow_up_attempt_count") == max_attempts
                ), "T3: Attempt count should be at max"
                logger.success(
                    "Follow-up Test - Turn 3 (Farewell after max attempts) PASSED!"
                )

        except AssertionError as e:
            logger.error(f"Assertion failed in simulated follow-up test: {e}")
            if state_t1_output:
                logger.debug(f"State T1 Output for review: {state_t1_output}")
            if "state_t2_output" in locals() and state_t2_output:
                logger.debug(f"State T2 Output for review: {state_t2_output}")
            if "state_t3_output" in locals() and state_t3_output:
                logger.debug(f"State T3 Output for review: {state_t3_output}")
            raise
        except Exception as e:
            logger.exception(f"Error during simulated follow-up test: {e}")
            assert False, f"Simulated follow-up test failed: {e}"
        finally:
            # await checkpointer.aclose() # Corrigido para aclose
            logger.info(f"--- {test_name} Finished ---")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.info("Starting integration test script (Simulated Follow-up)...")

    # Criar manualmente o estado inicial para execução direta
    # (Esta parte pode ser simplificada se a fixture for chamada de forma diferente ou se o teste for sempre rodado com pytest)
    # Para execução direta, precisamos instanciar o estado que a fixture forneceria.
    # Copiando a lógica da fixture para cá:
    agent_last_message_text_main = "O Plano X é ideal para você, pois oferece alta velocidade e suporte prioritário. O que acha de explorarmos os detalhes?"
    initial_goal_main = AgentGoal(
        goal_type="PRESENTING_SOLUTION",
        goal_details={
            "presenting_product": "Plano X",
            "main_benefit_focus": "velocidade",
        },
        previous_goal_if_interrupted=None,
    )
    settings_main = get_settings()
    initial_state_main = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={
            "company_name": "FollowUp Inc.",
            "language": "pt-br",
            "sales_tone": "prestativo",
            "fallback_contact_info": "followup.inc/contato",
            "business_description": "Testando follow-ups.",
            "offering_overview": [
                {"name": "Plano X", "short_description": "Alta velocidade e suporte."}
            ],
            "key_selling_points": ["Alta velocidade", "Suporte prioritário"],
        },
        agent_config={
            "max_follow_up_attempts": getattr(
                settings_main, "MAX_FOLLOW_UP_ATTEMPTS", 2
            )
        },
        messages=[
            HumanMessage(content="Preciso de algo rápido."),
            AIMessage(content=agent_last_message_text_main),
        ],
        current_user_input_text=None,
        current_turn_number=2,
        current_agent_goal=initial_goal_main,
        last_agent_action=PendingAgentAction(
            action_type="PRESENT_SOLUTION_OFFER",
            details={
                "product_name_to_present": "Plano X",
                "key_benefit_to_highlight": "velocidade",
            },
            action_generation_text=agent_last_message_text_main,
            attempts=1,
        ),
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [
                {
                    "text": "velocidade",
                    "status": "active",
                    "priority": 1,
                    "source_turn": 1,
                }
            ],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
            "last_discerned_intent": "StatingInformationOrOpinion",
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=agent_last_message_text_main,
        final_agent_message_text=agent_last_message_text_main,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=time.time() - 70000,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        next_agent_action_command=None,
        action_parameters={},
        follow_up_scheduled=True,
        follow_up_attempt_count=0,
        last_message_from_agent_timestamp=time.time() - 70000,
        trigger_event=None,
    )

    try:
        if not callable(create_agent_graph):
            logger.error(
                "create_agent_graph function not found. Ensure graph.py is correct and importable."
            )
            sys.exit(1)
        asyncio.run(test_simulated_follow_up_flow(initial_state_main))
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Simulated Follow-up) finished.")
