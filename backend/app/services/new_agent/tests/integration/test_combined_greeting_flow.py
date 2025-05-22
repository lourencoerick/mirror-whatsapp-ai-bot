# backend/app/services/ai_reply/new_agent/tests/integration/test_combined_greeting_flow.py

import asyncio
import copy
import os
import sys
import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from unittest.mock import (
    patch,
    AsyncMock,
)  # Keep patch if we need to mock LLM for response_generator

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
    # Add other necessary types if initial state requires them
)

# No need for OfferSelectionOutput here
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


async def run_combined_greeting_integration_test():
    test_name = "Integration Test - Combined Greeting Flow"
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
            "temperature": 0.1,  # Low temperature for deterministic greeting
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
        # Strategy LLM might not be strictly needed if not mocking proactive decider for this test
        llm_strategy_real = AzureChatOpenAI(
            azure_deployment="gpt-4o", **common_llm_params
        )
        logger.info("Using AzureChatOpenAI models for testing.")
    except Exception as e:
        logger.error(
            f"Failed to initialize AzureChatOpenAI: {e}. Test will be skipped."
        )
        return

    db_file = "integration_test_combined_greeting_memory.sqlite"
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
        thread_id_combined_greeting = str(uuid4())
        config_combined_greeting = {
            "configurable": {
                **base_configurable_items,
                "thread_id": thread_id_combined_greeting,
            }
        }

        # --- Initial State: User sends a simple greeting ---
        initial_messages: List[BaseMessage] = []  # Start with no messages
        user_first_message = "Olá"

        company_profile_data = CompanyProfileSchema(
            company_name="Soluções Inovadoras Ltda.",
            language="pt-br",
            sales_tone="amigável e eficiente",
            fallback_contact_info="inovadoras.com/suporte",
            business_description="Ajudamos empresas a otimizar processos com tecnologia.",
            offering_overview=[  # Keep a few for context, though not directly used by greeting
                OfferingInfo(
                    name="Plataforma Optimize",
                    short_description="Otimização de fluxo de trabalho.",
                    key_features=["IA", "Automação"],
                    price_info="Consulte-nos",
                    link="https://inovadoras.com/optimize",
                    category="Software",
                ),
            ],
            key_selling_points=["Inovação Contínua", "Resultados Comprovados"],
            communication_guidelines=["Ser claro", "Focar no valor"],
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
            "temperature_primary_llm": 0.1,  # Low temp for greeting
            "model_fast_llm": "gpt-4o",
            "model_strategy_llm": "gpt-4o",
            "model_primary_llm": "gpt-4o",
            "embedding_model": "text-embedding-ada-002",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.7,
        }

        initial_state_for_greeting = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),  # Empty
            current_user_input_text=user_first_message,
            current_turn_number=1,  # First turn
            current_agent_goal=AgentGoal(
                goal_type="IDLE", goal_details={}
            ),  # Starts IDLE
            last_agent_action=None,
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
                last_discerned_intent=None,
            ),
            company_profile=company_profile_data.model_dump(mode="json"),
            agent_config=agent_config_data,
            user_interruptions_queue=[],
            customer_question_log=[],
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
            f"\n--- {test_name} - Turn 1: User sends greeting, agent should reply with combined greeting + SPIN Situation ---"
        )

        # For this test, we are NOT mocking the ResponseGenerator's LLM call for the greeting.
        # We want to see if the real LLM, given the modified prompt, generates the combined message.
        # This makes it a truer integration test for this specific feature.
        # If it's too flaky, we can mock response_generator._call_llm_for_generation.

        try:
            final_state_after_greeting: RichConversationState = await graph_app.ainvoke(
                initial_state_for_greeting, config=config_combined_greeting
            )

            logger.info(
                f"{test_name} - Input User Message: {initial_state_for_greeting['current_user_input_text']}"
            )
            logger.info(
                f"{test_name} - Output State from invoke (turn {final_state_after_greeting.get('current_turn_number')}):"
            )

            final_goal = final_state_after_greeting.get("current_agent_goal")
            logger.info(f"  Final Goal: {final_goal}")

            final_action = final_state_after_greeting.get("last_agent_action")
            logger.info(f"  Last Action: {final_action}")

            final_messages = final_state_after_greeting.get("messages", [])
            ai_response_message = (
                final_messages[-1]
                if final_messages and isinstance(final_messages[-1], AIMessage)
                else None
            )
            logger.info(
                f"  Final AI Message: {ai_response_message.content if ai_response_message else 'N/A'}"
            )

            # 1. Planner should have planned GENERATE_GREETING with combined_spin_question_type
            # This is harder to assert directly without inspecting intermediate states or planner's delta.
            # We infer it from the final_action and final_goal.

            assert final_action is not None, "Last agent action should exist"
            assert (
                final_action.get("action_type") == "GENERATE_GREETING"
            ), "Action should be GENERATE_GREETING"
            assert (
                final_action.get("details", {}).get("combined_spin_question_type")
                == "Situation"
            ), "Action details should include combined SPIN type"

            # 2. The agent's goal should now be INVESTIGATING_NEEDS, and SPIN cycle started
            assert final_goal is not None, "Current agent goal should exist"
            assert (
                final_goal.get("goal_type") == "INVESTIGATING_NEEDS"
            ), "Goal should be INVESTIGATING_NEEDS after combined greeting"
            goal_details = final_goal.get("goal_details", {})
            assert (
                goal_details.get("last_spin_type_asked") == "Situation"
            ), "last_spin_type_asked should be Situation"
            assert (
                goal_details.get("spin_questions_asked_this_cycle") == 1
            ), "spin_questions_asked_this_cycle should be 1"

            # 3. Check the AI's response message for both greeting and Situation question
            assert ai_response_message is not None, "AI response message should exist"
            response_content = ai_response_message.content.lower()  # type: ignore

            # Check for greeting part (flexible)
            assert (
                "olá" in response_content
                or "oi" in response_content
                or company_profile_data.company_name.lower() in response_content
            ), f"AI response '{ai_response_message.content}' should contain a greeting."

            # Check for Situation question part (flexible, looking for keywords)
            assert (
                "ajudar" in response_content
                or "desafio" in response_content
                or "objetivo" in response_content
                or "traz aqui" in response_content
                or "contar um pouco" in response_content
                or "posso te direcionar" in response_content
            ), f"AI response '{ai_response_message.content}' should contain a Situation question."

            # Check that it's likely a question
            assert (
                "?" in ai_response_message.content
            ), "AI response should end with a question mark."

            # 4. Temporary fields should be cleared
            assert final_state_after_greeting.get("next_agent_action_command") is None
            assert final_state_after_greeting.get("user_input_analysis_result") is None

            logger.success(f"{test_name} PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in {test_name}: {e}")
            if "final_state_after_greeting" in locals():  # type: ignore
                logger.debug(
                    f"Final State for review: Goal={final_state_after_greeting.get('current_agent_goal')}, LastAction={final_state_after_greeting.get('last_agent_action')}, Messages={final_state_after_greeting.get('messages')}"
                )
            raise
        except Exception as e:
            logger.exception(f"Error during {test_name}: {e}")
            assert False, f"{test_name} Failed: {e}"
        finally:
            logger.info(f"--- {test_name} Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Combined Greeting Flow)...")
    try:
        asyncio.run(run_combined_greeting_integration_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Combined Greeting Flow) finished.")
