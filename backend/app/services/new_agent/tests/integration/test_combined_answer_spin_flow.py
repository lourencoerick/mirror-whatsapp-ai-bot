# backend/app/services/ai_reply/new_agent/tests/integration/test_combined_answer_spin_flow.py

import asyncio
import copy
import os
import sys
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from loguru import logger

from app.services.new_agent.graph import create_agent_graph
from app.services.new_agent.state_definition import (
    RichConversationState,
    AgentGoal,
    PendingAgentAction,
    DynamicCustomerProfile,
    CustomerQuestionEntry,  # For initial state
    CustomerQuestionStatusType,
)
from app.api.schemas.company_profile import CompanyProfileSchema, OfferingInfo
from app.database import AsyncSessionLocal

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


async def run_combined_answer_spin_integration_test():
    test_name = "Integration Test - Combined Answer + SPIN Flow"
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

    llm_fast_real: Optional[BaseChatModel] = None
    llm_primary_real: Optional[BaseChatModel] = None
    llm_strategy_real: Optional[BaseChatModel] = None

    try:
        if not SETTINGS_AVAILABLE:
            raise ValueError("Settings module not available.")
        settings = get_settings()
        if not all([settings.AZURE_OPENAI_ENDPOINT, settings.AZURE_OPENAI_API_KEY]):
            raise ValueError("Azure OpenAI Endpoint or API Key not configured.")

        common_llm_params = {
            "temperature": 0.1,
            "azure_endpoint": settings.AZURE_OPENAI_ENDPOINT,
            "api_key": settings.AZURE_OPENAI_API_KEY,
            "api_version": "2024-02-01",
            "max_retries": 1,
            "request_timeout": 60,
        }
        llm_fast_real = AzureChatOpenAI(azure_deployment="gpt-4o", **common_llm_params)
        llm_primary_real = AzureChatOpenAI(
            azure_deployment="gpt-4o", **common_llm_params
        )
        llm_strategy_real = AzureChatOpenAI(
            azure_deployment="gpt-4o", **common_llm_params
        )
        logger.info("Using AzureChatOpenAI models for testing.")
    except Exception as e:
        logger.error(
            f"Failed to initialize AzureChatOpenAI: {e}. Test will be skipped."
        )
        return

    db_file = "integration_test_combined_answer_spin_memory.sqlite"
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
        logger.info(f"Removed previous test database: {db_file}")
    except OSError as e:
        logger.warning(f"Could not remove previous test database {db_file}: {e}")

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        logger.info(f"Using SqliteSaver checkpointer with db: {db_file}")
        graph_app = create_agent_graph(checkpointer=checkpointer)

        base_configurable_items = {
            "llm_fast_instance": llm_fast_real,
            "llm_primary_instance": llm_primary_real,
            "llm_strategy_instance": llm_strategy_real,
            "db_session_factory": AsyncSessionLocal,
        }
        thread_id_combined_answer = str(uuid4())
        config_combined_answer = {
            "configurable": {
                **base_configurable_items,
                "thread_id": thread_id_combined_answer,
            }
        }

        # --- Initial State: Agent has greeted (maybe with combined Situation q), user asks a direct question ---
        agent_greeting_and_situation_q = "Olá! Sou o InovaBot da Soluções Inovadoras Ltda. Para começarmos, poderia me contar um pouco sobre o que te traz aqui hoje ou qual desafio você está buscando resolver?"
        initial_messages: List[BaseMessage] = [
            HumanMessage(content="Oi"),  # User's first message
            AIMessage(
                content=agent_greeting_and_situation_q
            ),  # Agent's combined greeting
        ]
        user_asks_direct_question = "Vocês trabalham com otimização de custos de TI?"

        company_profile_data = CompanyProfileSchema(
            company_name="Soluções Inovadoras Ltda.",
            language="pt-br",
            sales_tone="consultivo",
            fallback_contact_info="inovadoras.com/suporte",
            business_description="Ajudamos empresas a otimizar processos e custos com tecnologia de ponta.",
            offering_overview=[
                OfferingInfo(
                    name="Consultoria de Custos de TI",
                    short_description="Análise e redução de despesas de TI.",
                    key_features=[
                        "Diagnóstico completo",
                        "Plano de ação",
                        "ROI rápido",
                    ],
                    price_info="A partir de R$2.000",
                    link="https://inovadoras.com/custos-ti",
                    category="Serviço",
                ),
                OfferingInfo(
                    name="Plataforma Optimize",
                    short_description="Otimização de fluxo de trabalho.",
                    key_features=["IA", "Automação"],
                    price_info="Consulte-nos",
                    link="https://inovadoras.com/optimize",
                    category="Software",
                ),
            ],
            key_selling_points=[
                "Redução de Custos Comprovada",
                "Especialistas em TI",
                "Soluções Personalizadas",
            ],
            communication_guidelines=["Ser transparente sobre custos", "Mostrar valor"],
            company_main_link_fallback="https://inovadoras.com",
            address="Av. Principal, 100",
            opening_hours="8h-18h",
            target_audience="Empresas B2B",
            delivery_options=[],
            specific_faq=[],
            privacy_policy_link=None,
            social_media_links=None,
        )
        agent_config_data = {
            "max_follow_up_attempts": 3,
            "agent_name": "InovaBot",
            "agent_role": "Consultor de Otimização",
            "temperature_fast_llm": 0.1,
            "temperature_strategy_llm": 0.2,
            "temperature_primary_llm": 0.1,
            "model_fast_llm": "gpt-4o",
            "model_strategy_llm": "gpt-4o",
            "model_primary_llm": "gpt-4o",
            "embedding_model": "text-embedding-ada-002",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.7,
        }

        # State after agent's combined greeting, before user's direct question is processed by this invoke
        state_before_user_question = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages) + [user_asks_direct_question],
            current_user_input_text=user_asks_direct_question,  # This is the input for the current run
            current_turn_number=2,  # User's question starts Turn 2
            current_agent_goal=AgentGoal(  # Planner set this after combined greeting
                goal_type="INVESTIGATING_NEEDS",
                goal_details={
                    "last_spin_type_asked": "Situation",
                    "spin_questions_asked_this_cycle": 1,
                },
            ),
            last_agent_action=PendingAgentAction(  # The combined greeting action
                action_type="GENERATE_GREETING",
                details={"combined_spin_question_type": "Situation"},
                action_generation_text=agent_greeting_and_situation_q,
                attempts=1,
            ),
            customer_profile_dynamic=DynamicCustomerProfile(
                identified_needs=[],
                identified_pain_points=[],
                identified_objections=[],
                certainty_levels={
                    "product": None,
                    "agent": None,
                    "company": None,
                    "last_assessed_turn": None,
                },
                last_discerned_intent=None,  # Will be populated by input_processor for user_asks_direct_question
            ),
            company_profile=company_profile_data.model_dump(mode="json"),
            agent_config=agent_config_data,
            user_interruptions_queue=[],
            customer_question_log=[],  # Log is empty before this question is processed
            current_turn_extracted_questions=None,
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=None,
            final_agent_message_text=None,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time() - 10,
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
            offer_selection_result=None,
            next_agent_action_command=None,
            action_parameters={},
            follow_up_scheduled=False,
            follow_up_attempt_count=0,
            last_message_from_agent_timestamp=None,
            trigger_event="user_message",
            suggested_goal_type=None,
            suggested_goal_details=None,
        )

        logger.info(
            f"\n--- {test_name} - Turn 2: User asks direct question, agent should answer + ask SPIN Problem ---"
        )

        # We are NOT mocking the ResponseGenerator's LLM call for ANSWER_DIRECT_QUESTION.
        # We want to see if the real LLM, given the modified prompt and combined_spin_question_type,
        # generates the combined message.

        try:
            final_state_after_answer_spin: RichConversationState = (
                await graph_app.ainvoke(
                    state_before_user_question, config=config_combined_answer
                )
            )

            logger.info(
                f"{test_name} - Input User Message: {state_before_user_question['current_user_input_text']}"
            )
            logger.info(
                f"{test_name} - Output State from invoke (turn {final_state_after_answer_spin.get('current_turn_number')}):"
            )

            final_goal = final_state_after_answer_spin.get("current_agent_goal")
            logger.info(f"  Final Goal: {final_goal}")

            final_action = final_state_after_answer_spin.get("last_agent_action")
            logger.info(f"  Last Action: {final_action}")

            final_messages = final_state_after_answer_spin.get("messages", [])
            ai_response_message = (
                final_messages[-1]
                if final_messages and isinstance(final_messages[-1], AIMessage)
                else None
            )
            logger.info(
                f"  Final AI Message: {ai_response_message.content if ai_response_message else 'N/A'}"
            )

            # 1. Planner should have planned ANSWER_DIRECT_QUESTION with combined_spin_question_type: "Problem"
            assert final_action is not None, "Last agent action should exist"
            assert (
                final_action.get("action_type") == "ANSWER_DIRECT_QUESTION"
            ), "Action should be ANSWER_DIRECT_QUESTION"
            action_details = final_action.get("details", {})
            assert (
                action_details.get("question_to_answer_text")
                == user_asks_direct_question
            )
            assert (
                action_details.get("combined_spin_question_type") == "Problem"
            ), "Action details should include combined SPIN type 'Problem'"

            # 2. The agent's goal should remain/be INVESTIGATING_NEEDS, and SPIN cycle advanced
            assert final_goal is not None, "Current agent goal should exist"
            assert (
                final_goal.get("goal_type") == "INVESTIGATING_NEEDS"
            ), "Goal should be INVESTIGATING_NEEDS"
            goal_details = final_goal.get("goal_details", {})
            assert (
                goal_details.get("last_spin_type_asked") == "Problem"
            ), "last_spin_type_asked should be Problem"
            assert (
                goal_details.get("spin_questions_asked_this_cycle") == 2
            ), "spin_questions_asked_this_cycle should be 2 (Situation + Problem)"

            # 3. Check customer_question_log for the answered question
            question_log = final_state_after_answer_spin.get(
                "customer_question_log", []
            )
            assert len(question_log) >= 1, "Question log should not be empty"
            answered_q_entry = next(
                (
                    q
                    for q in question_log
                    if q.get("extracted_question_core") == user_asks_direct_question
                ),
                None,
            )
            assert (
                answered_q_entry is not None
            ), f"Question '{user_asks_direct_question}' not found in log"
            assert (
                answered_q_entry.get("status") == "answered_satisfactorily"
            ), "Question status should be answered_satisfactorily"

            # 4. Check the AI's response message for both the answer and the SPIN Problem question
            assert ai_response_message is not None, "AI response message should exist"
            response_content = ai_response_message.content  # type: ignore
            response_content_lower = response_content.lower()

            # Check for answer part (flexible, depends on RAG/profile)
            assert (
                "sim" in response_content_lower
                or "trabalhamos com otimização de custos" in response_content_lower
                or "consultoria de custos de ti" in response_content_lower
            ), f"AI response '{response_content}' should contain an answer to the user's question."

            # Check for SPIN Problem question part (flexible)
            assert (
                "problema" in response_content_lower
                or "desafios" in response_content_lower
                or "dificuldade" in response_content_lower
                or "enfrenta" in response_content_lower
                or "preocupa" in response_content_lower
                or "quais desafios" in response_content_lower
            ), f"AI response '{response_content}' should contain a SPIN Problem question."

            assert (
                "?" in response_content
            ), "AI response should end with a question mark (from the SPIN question)."
            # Ensure the answer part comes before the question part
            answer_keywords = [
                "sim, nós oferecemos",
                "sim, nós trabalhamos",
                "sim, trabalhamos",
                "oferecemos consultoria de custos",
                "sim, podemos ajudar com otimização",
            ]  # Adicionar variações da resposta

            # Tornar as problem_keywords mais flexíveis para corresponder à geração do LLM
            problem_keywords = [
                "qual é o principal problema",
                "que tipo de desafio",
                "necessidades",
                "poderia me dizer mais sobre as dificuldades",
                "quais desafios específicos você está enfrentando",  # <<< ADICIONADO
                "quais são seus maiores desafios",  # Outra variação
                "que dificuldades você tem",  # Outra variação
            ]

            answer_pos = -1
            for kw in answer_keywords:
                if kw.lower() in response_content_lower:
                    answer_pos = response_content_lower.find(kw)
                    break

            problem_q_pos = -1
            for kw in problem_keywords:
                if kw in response_content_lower:
                    problem_q_pos = response_content_lower.find(kw)
                    break

            assert (
                answer_pos != -1
            ), f"Answer part not clearly found in combined message: '{response_content}' using keywords: {answer_keywords}"
            assert (
                problem_q_pos != -1
            ), f"Problem SPIN question part not clearly found in combined message: '{response_content}' using keywords: {problem_keywords}"
            assert (
                answer_pos < problem_q_pos
            ), "Answer should come before the SPIN question in the combined message"
            # 5. Temporary fields should be cleared
            assert (
                final_state_after_answer_spin.get("next_agent_action_command") is None
            )
            assert (
                final_state_after_answer_spin.get("user_input_analysis_result") is None
            )

            logger.success(f"{test_name} PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in {test_name}: {e}")
            if "final_state_after_answer_spin" in locals():  # type: ignore
                logger.debug(
                    f"Final State for review: Goal={final_state_after_answer_spin.get('current_agent_goal')}, LastAction={final_state_after_answer_spin.get('last_agent_action')}, QuestionLog={final_state_after_answer_spin.get('customer_question_log')}, Messages={final_state_after_answer_spin.get('messages')}"
                )
            raise
        except Exception as e:
            logger.exception(f"Error during {test_name}: {e}")
            assert False, f"{test_name} Failed: {e}"
        finally:
            logger.info(f"--- {test_name} Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Combined Answer + SPIN Flow)...")
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_combined_answer_spin_integration_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Combined Answer + SPIN Flow) finished.")
