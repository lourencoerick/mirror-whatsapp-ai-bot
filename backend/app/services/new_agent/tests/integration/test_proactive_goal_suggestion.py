# backend/app/services/ai_reply/new_agent/tests/integration/test_proactive_goal_suggestion.py

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

# Import the actual graph from your application
from app.services.new_agent.graph import create_agent_graph

# Import necessary state definitions and schemas
from app.services.new_agent.state_definition import (
    RichConversationState,
    AgentGoal,
    PendingAgentAction,
    IdentifiedNeedEntry,
    # Import other specific state parts if needed by your initial state
)
from app.services.new_agent.schemas.proactive_step_output import ProactiveStepDecision
from app.services.new_agent.schemas.input_analysis import (
    UserInputAnalysisOutput,  # For type hinting if we were to mock input_processor output
    PendingAgentActionResponseAnalysis,
    ReactionToPresentation,
    ObjectionAfterRebuttalStatus,
)


from app.database import AsyncSessionLocal  # If your graph config needs it

# Configuration
try:
    from app.config import get_settings

    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    logger.error("Could not import get_settings from app.config.")

    class MockSettings:  # Basic mock for environment variables
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
        AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
        # Add other settings if your LLM init or other parts need them

    def get_settings():
        return MockSettings()


# --- Test Function ---
async def run_proactive_goal_suggestion_test():
    test_name = "Integration Test - Proactive Goal Suggestion"
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

    # --- Configure LLM ---
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
            "api_version": "2024-02-01",  # Use a recent, valid API version
            "max_retries": 1,
            "request_timeout": 60,
        }
        # Ensure your Azure deployments "gpt-35-turbo" and "gpt-4o" exist and are correctly named.
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

    # --- Configure Checkpointer ---
    db_file = "integration_test_proactive_goal_memory.sqlite"
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
        logger.info(f"Removed previous test database: {db_file}")
    except OSError as e:
        logger.warning(f"Could not remove previous test database {db_file}: {e}")

    async with AsyncSqliteSaver.from_conn_string(db_file) as checkpointer:
        logger.info(f"Using SqliteSaver checkpointer with db: {db_file}")
        # USE THE ACTUAL GRAPH FROM YOUR APPLICATION
        graph_app = create_agent_graph(checkpointer=checkpointer)

        base_configurable_items = {
            "llm_fast_instance": llm_fast_real,
            "llm_primary_instance": llm_primary_real,
            "llm_strategy_instance": llm_strategy_real,
            "db_session_factory": AsyncSessionLocal,
        }
        thread_id_proactive = str(uuid4())
        config_proactive = {
            "configurable": {
                **base_configurable_items,
                "thread_id": thread_id_proactive,
            }
        }

        # --- Initial State: Conversation stalled after agent asked a question ---
        agent_last_question = "Considerando esses desafios, qual seria o impacto financeiro para sua operação?"
        initial_messages: List[BaseMessage] = [
            HumanMessage(content="Tenho tido alguns problemas com a logística."),
            AIMessage(content=agent_last_question),
        ]

        # Construct a more complete company_profile and agent_config
        company_profile_data = {
            "company_name": "LogPro Soluções",
            "language": "pt-br",
            "sales_tone": "consultivo",
            "fallback_contact_info": "logpro.com/contato",
            "business_description": "Otimização de logística para empresas que buscam eficiência.",
            "offering_overview": [
                {
                    "name": "Sistema LogMax",
                    "short_description": "Otimiza toda a sua cadeia de suprimentos.",
                    "key_features": [
                        "Rastreamento em tempo real",
                        "Otimização de rotas",
                    ],
                    "target_audience_fit": "Empresas de médio porte",
                    "bonus_items": ["Consultoria inicial gratuita"],
                    "link": "http://logpro.com/logmax",
                    "details_url": None,
                    "price_info": "Sob consulta",
                    "category": "Software",
                }
            ],
            "key_selling_points": [
                "Eficiência Comprovada",
                "Redução de Custos",
                "Suporte Especializado",
            ],
            "communication_guidelines": [
                "Ser claro e objetivo",
                "Focar nos benefícios para o cliente",
            ],
            "address": "Av. Logística, 123, São Paulo, SP",
            "opening_hours": "Seg-Sex, 9h-18h",
            "target_audience": "Empresas com desafios logísticos",
            "delivery_options": [],
            "company_main_link_fallback": "http://logpro.com",
            "specific_faq": [
                {"question": "Como funciona?", "answer": "Nosso sistema integra..."}
            ],
            "privacy_policy_link": "logpro.com/privacidade",
            "social_media_links": {"linkedin": "linkedin.com/company/logpro"},
        }
        agent_config_data = {
            "max_follow_up_attempts": 3,
            "agent_name": "LogAgent",
            "agent_role": "Consultor de Logística",
            "temperature_fast_llm": 0.1,
            "temperature_strategy_llm": 0.2,
            "temperature_primary_llm": 0.2,
            "model_fast_llm": "gpt-35-turbo",
            "model_strategy_llm": "gpt-4o",
            "model_primary_llm": "gpt-4o",
            "embedding_model": "text-embedding-ada-002",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.75,
        }

        state_before_proactive_nudge = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text="",  # Will be filled
            current_turn_number=2,
            current_agent_goal=AgentGoal(
                goal_type="INVESTIGATING_NEEDS",
                goal_details={
                    "last_spin_type_asked": "Implication",
                    "spin_questions_asked_this_cycle": 2,
                },
            ),
            last_agent_action=PendingAgentAction(
                action_type="ASK_SPIN_QUESTION",
                details={"spin_type": "Implication"},
                action_generation_text=agent_last_question,
                attempts=1,
            ),
            customer_profile_dynamic={
                "identified_needs": [
                    IdentifiedNeedEntry(
                        text="melhorar logística",
                        status="active",
                        source_turn=1,
                        priority=None,
                    )
                ],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {
                    "product": None,
                    "agent": None,
                    "company": None,
                    "last_assessed_turn": None,
                },
                "last_discerned_intent": None,
            },
            company_profile=company_profile_data,  # type: ignore
            agent_config=agent_config_data,  # type: ignore
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=None,
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=agent_last_question,
            final_agent_message_text=None,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,  # Will be populated by process_input
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
            "\n--- Proactive Goal Suggestion Test - Turn: User gives minimal response ---"
        )
        user_minimal_response = "Entendi."  # This input needs to be reliably parsed as minimal/vague by input_processor
        state_for_proactive_invoke = copy.deepcopy(state_before_proactive_nudge)
        state_for_proactive_invoke["current_user_input_text"] = user_minimal_response
        state_for_proactive_invoke["messages"].append(
            HumanMessage(content=user_minimal_response)
        )

        # Mock the proactive decider's LLM call to ensure deterministic suggestion
        mock_proactive_decision = ProactiveStepDecision(
            suggested_next_goal_type="INVESTIGATING_NEEDS",
            suggested_next_goal_details={
                "spin_type_to_ask_next": "NeedPayoff",
                "last_spin_type_asked": "Implication",
                "spin_questions_asked_this_cycle": 2,
            },  # Planner will increment
            justification="User response was minimal, probing further with NeedPayoff question to solidify value.",
            proactive_action_command=None,
            proactive_action_parameters={},
        )

        # Patch the _call_structured_llm function within the proactive_step_decider module
        with patch(
            "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
            AsyncMock(return_value=mock_proactive_decision),
        ) as mock_llm_call_for_proactive:
            try:
                final_state_proactive: RichConversationState = await graph_app.ainvoke(
                    state_for_proactive_invoke, config=config_proactive
                )

                logger.info(
                    f"Proactive Test - Input User Message: {state_for_proactive_invoke['current_user_input_text']}"
                )
                logger.info(
                    f"Proactive Test - Output State from invoke (turn {final_state_proactive.get('current_turn_number')}):"
                )
                logger.info(
                    f"  Final Goal: {final_state_proactive.get('current_agent_goal')}"
                )
                logger.info(
                    f"  Last Action: {final_state_proactive.get('last_agent_action')}"
                )
                logger.info(
                    f"  Final AI Message: {final_state_proactive.get('messages', [])[-1].content if final_state_proactive.get('messages') and isinstance(final_state_proactive.get('messages')[-1], AIMessage) else 'N/A'}"
                )

                assert (
                    final_state_proactive.get("current_turn_number") == 3
                ), "Turn number should increment"

                # Check that the input processor ran and produced some analysis
                # The actual content of user_input_analysis_result is cleared by state_updater by the end of the turn.
                # So, we can't check its content in final_state_proactive.
                # We rely on the absence of errors from input_processor in the logs.

                # Assert that the proactive_step_decider's LLM (mocked) was called
                mock_llm_call_for_proactive.assert_called_once()

                final_goal = final_state_proactive.get("current_agent_goal")
                assert final_goal is not None, "Current agent goal should exist"
                assert (
                    final_goal.get("goal_type") == "INVESTIGATING_NEEDS"
                ), "Goal should be the proactively suggested INVESTIGATING_NEEDS"

                # Planner takes the suggested goal and plans the next SPIN question.
                # The 'spin_type_to_ask_next' from suggestion becomes 'last_spin_type_asked' after planning.
                # And 'spin_questions_asked_this_cycle' is incremented by the planner.
                assert (
                    final_goal.get("goal_details", {}).get("last_spin_type_asked")
                    == "NeedPayoff"
                ), f"Planner should have set SPIN type from suggestion. Got: {final_goal.get('goal_details', {}).get('last_spin_type_asked')}"
                assert (
                    final_goal.get("goal_details", {}).get(
                        "spin_questions_asked_this_cycle"
                    )
                    == 3
                ), f"Planner should have incremented spin_questions_asked_this_cycle. Got: {final_goal.get('goal_details', {}).get('spin_questions_asked_this_cycle')}"

                final_action = final_state_proactive.get("last_agent_action")
                assert final_action is not None, "Last agent action should exist"
                assert (
                    final_action.get("action_type") == "ASK_SPIN_QUESTION"
                ), "Action should be ASK_SPIN_QUESTION based on suggested goal"
                assert (
                    final_action.get("details", {}).get("spin_type") == "NeedPayoff"
                ), "SPIN type should match suggested"

                final_messages = final_state_proactive.get("messages", [])
                assert (
                    len(final_messages) == len(initial_messages) + 2
                ), "Should have initial messages + user input + AI response"
                last_ai_message = final_messages[-1]
                assert isinstance(
                    last_ai_message, AIMessage
                ), "Last message should be from AI"
                logger.info(
                    f"Proactive Test - Generated AI Message: {last_ai_message.content}"
                )

                assert (
                    last_ai_message.content is not None
                    and last_ai_message.content.strip() != ""
                ), "AI message content should not be empty"
                assert (
                    "vantagem" in last_ai_message.content.lower()
                    or "benefício" in last_ai_message.content.lower()
                    or "ajudaria" in last_ai_message.content.lower()
                    or "resolver" in last_ai_message.content.lower()
                    or "reduzir" in last_ai_message.content.lower()
                ), f"AI message '{last_ai_message.content}' should sound like a NeedPayoff question"

                assert (
                    final_state_proactive.get("suggested_goal_type") is None
                ), "suggested_goal_type should be cleared"
                assert (
                    final_state_proactive.get("suggested_goal_details") is None
                ), "suggested_goal_details should be cleared"
                assert (
                    final_state_proactive.get("next_agent_action_command") is None
                ), "next_agent_action_command should be cleared"

                logger.success(f"{test_name} PASSED!")

            except AssertionError as e:
                logger.error(f"Assertion failed in {test_name}: {e}")
                if "final_state_proactive" in locals():
                    logger.debug(
                        f"Final State for review: Goal={final_state_proactive.get('current_agent_goal')}, LastAction={final_state_proactive.get('last_agent_action')}, Messages={final_state_proactive.get('messages')}"
                    )
                raise
            except Exception as e:
                logger.exception(f"Error during {test_name}: {e}")
                assert False, f"{test_name} Failed: {e}"
            finally:
                logger.info(f"--- {test_name} Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Proactive Goal Suggestion)...")
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_proactive_goal_suggestion_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Proactive Goal Suggestion) finished.")
