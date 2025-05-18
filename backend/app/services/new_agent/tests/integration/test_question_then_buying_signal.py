# backend/app/services/ai_reply/new_agent/tests/integration/test_question_then_buying_signal.py

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
    IdentifiedNeedEntry,
    ProposedSolution,
    # Import other specific state parts if needed
)
from app.services.new_agent.schemas.proactive_step_output import ProactiveStepDecision

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


# --- Test Function ---
async def run_question_then_buying_signal_test():
    test_name = (
        "Integration Test - Question, Buying Signal, Confirm Offer, Initiate Close"
    )
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

    db_file = "integration_test_q_buy_confirm_close_memory.sqlite"  # New DB file name
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
        thread_id_test = str(uuid4())
        config_test = {
            "configurable": {**base_configurable_items, "thread_id": thread_id_test}
        }

        initial_messages: List[BaseMessage] = [
            HumanMessage(content="Olá"),
            AIMessage(content="Olá! Sou o assistente da TestComp. Como posso ajudar?"),
        ]

        product_y_name = "Produto Y"
        product_y_price_str = "R$99,90"
        product_y_price_float = 99.90
        product_y_feature = "Resolve sua necessidade de agilidade"  # For need matching

        company_profile_data = {
            "company_name": "TestComp Soluções",
            "language": "pt-br",
            "sales_tone": "prestativo",
            "fallback_contact_info": "testcomp.com/ajuda",
            "business_description": "Vendemos o Produto Y, focado em agilidade.",
            "offering_overview": [
                {
                    "name": product_y_name,
                    "short_description": product_y_feature,
                    "price_info": product_y_price_str,
                    "key_features": ["Característica A", product_y_feature],
                    "target_audience_fit": None,
                    "bonus_items": [],
                    "link": "http://testcomp.com/y",
                    "category": None,
                }
            ],
            "key_selling_points": ["Fácil de usar", "Preço Acessível"],
            "communication_guidelines": [],
            "address": None,
            "opening_hours": None,
            "target_audience": None,
            "delivery_options": ["Entrega em até 5 dias"],
            "company_main_link_fallback": "http://testcomp.com",
            "specific_faq": [
                {
                    "question": "Prazo de entrega?",
                    "answer": "O prazo de entrega padrão é de 5 dias úteis para sua região.",
                }
            ],
            "privacy_policy_link": None,
            "social_media_links": {},
        }
        agent_config_data = {
            "max_follow_up_attempts": 3,
            "agent_name": "Assistente TestComp",
            "agent_role": "Vendedor",
            "temperature_fast_llm": 0.1,
            "temperature_strategy_llm": 0.2,
            "temperature_primary_llm": 0.2,
            "model_fast_llm": "gpt-4o",
            "model_strategy_llm": "gpt-4o",
            "model_primary_llm": "gpt-4o",
            "embedding_model": "text-embedding-ada-002",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.75,
        }

        current_state = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text="",
            current_turn_number=1,
            current_agent_goal=AgentGoal(
                goal_type="INVESTIGATING_NEEDS", goal_details={}
            ),
            last_agent_action=PendingAgentAction(
                action_type="GENERATE_GREETING",
                details={},
                action_generation_text=initial_messages[-1].content,
                attempts=1,
            ),
            customer_profile_dynamic={
                "identified_needs": [
                    # Add a need that matches Produto Y to help _select_product_and_benefit_for_presentation
                    IdentifiedNeedEntry(
                        text="preciso de agilidade",
                        status="active",
                        source_turn=0,
                        priority=5,
                    )
                ],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": None,
            },
            company_profile=company_profile_data,
            agent_config=agent_config_data,  # type: ignore
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=None,
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=initial_messages[-1].content,
            final_agent_message_text=None,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
            next_agent_action_command=None,
            action_parameters={},
            follow_up_scheduled=False,
            follow_up_attempt_count=0,
            last_message_from_agent_timestamp=None,
            trigger_event="user_message",
            suggested_goal_type=None,
            suggested_goal_details=None,
        )

        # Mock proactive decider to do nothing if it's accidentally called
        mock_no_proactive_action = ProactiveStepDecision(
            proactive_action_command=None,
            suggested_next_goal_type=None,
            justification="Test flow: No proactive action needed.",
        )

        final_state_after_closing_initiation = (
            None  # To store the final state for debugging
        )

        try:
            # --- Turn 1: User asks about delivery time ---
            logger.info(
                f"\n--- {test_name} - Turn 1: User asks about delivery time ---"
            )
            user_question = f"Qual o prazo de entrega para o {product_y_name}?"
            current_state["current_user_input_text"] = user_question
            current_state["messages"].append(HumanMessage(content=user_question))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive_action),
            ):
                state_after_question: RichConversationState = await graph_app.ainvoke(
                    copy.deepcopy(current_state), config=config_test
                )
            current_state = (
                state_after_question  # Update current_state for the next turn
            )

            logger.info(
                f"  T1 Agent Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"  T1 Agent Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T1 Agent Response: {current_state.get('messages', [])[-1].content}"
            )

            assert current_state.get("current_turn_number") == 2
            assert (
                current_state.get("current_agent_goal", {}).get("goal_type")
                == "CLARIFYING_USER_INPUT"
            )
            assert (
                current_state.get("last_agent_action", {}).get("action_type")
                == "ANSWER_DIRECT_QUESTION"
            )
            assert user_question in current_state.get("last_agent_action", {}).get(
                "details", {}
            ).get("question_to_answer_text", "")

            ai_response_t1_content = current_state.get("messages", [])[-1].content
            assert (
                "prazo de entrega" in ai_response_t1_content.lower()
                or "5 dias" in ai_response_t1_content.lower()
            )

            # --- Turn 2: User gives buying signal ---
            logger.info(f"\n--- {test_name} - Turn 2: User gives buying signal ---")
            user_buying_signal = f"Ótimo, 5 dias é perfeito! Quero comprar o {product_y_name}. Como procedo?"
            current_state["current_user_input_text"] = user_buying_signal
            current_state["messages"].append(HumanMessage(content=user_buying_signal))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive_action),
            ):
                state_after_buying_signal: RichConversationState = (
                    await graph_app.ainvoke(
                        copy.deepcopy(current_state), config=config_test
                    )
                )
            current_state = state_after_buying_signal

            logger.info(
                f"  T2 Agent Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"  T2 Agent Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T2 Agent Response: {current_state.get('messages', [])[-1].content}"
            )

            assert current_state.get("current_turn_number") == 3
            goal_t2 = current_state.get("current_agent_goal", {})
            action_t2 = current_state.get("last_agent_action", {})

            assert (
                goal_t2.get("goal_type") == "PRESENTING_SOLUTION"
            ), f"Expected PRESENTING_SOLUTION, got {goal_t2.get('goal_type')}"
            assert action_t2.get("action_type") == "PRESENT_SOLUTION_OFFER"
            assert (
                action_t2.get("details", {}).get("product_name_to_present")
                == product_y_name
            )

            ai_response_t2_content = current_state.get("messages", [])[-1].content
            assert product_y_name.lower() in ai_response_t2_content.lower()
            assert (
                "confirmar" in ai_response_t2_content.lower()
                or "detalhes" in ai_response_t2_content.lower()
                or product_y_price_str.split("R$")[1] in ai_response_t2_content
            )  # Check for price

            # Check if active_proposal was set
            assert (
                current_state.get("active_proposal") is not None
            ), "active_proposal should be set after PRESENT_SOLUTION_OFFER"
            active_proposal_t2 = current_state.get("active_proposal", {})
            assert active_proposal_t2.get("product_name") == product_y_name
            assert active_proposal_t2.get("price") == product_y_price_float

            # --- Turn 3: User confirms the offer ---
            logger.info(f"\n--- {test_name} - Turn 3: User confirms offer ---")
            user_confirmation = "Sim, tudo certo! Vamos fechar."
            current_state["current_user_input_text"] = user_confirmation
            current_state["messages"].append(HumanMessage(content=user_confirmation))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive_action),
            ):
                state_after_confirmation: RichConversationState = (
                    await graph_app.ainvoke(
                        copy.deepcopy(current_state), config=config_test
                    )
                )
            final_state_after_closing_initiation = (
                state_after_confirmation  # For debugging if needed
            )

            logger.info(
                f"  T3 Agent Goal: {state_after_confirmation.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"  T3 Agent Action: {state_after_confirmation.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T3 Agent Response: {state_after_confirmation.get('messages', [])[-1].content}"
            )

            assert state_after_confirmation.get("current_turn_number") == 4
            goal_t3 = state_after_confirmation.get("current_agent_goal", {})
            action_t3 = state_after_confirmation.get("last_agent_action", {})

            assert (
                goal_t3.get("goal_type") == "ATTEMPTING_CLOSE"
            ), f"Expected ATTEMPTING_CLOSE, got {goal_t3.get('goal_type')}"
            assert (
                goal_t3.get("goal_details", {}).get("closing_step") == "initial_attempt"
            )  # Or could be 'awaiting_confirmation' depending on how planner handles it

            assert action_t3.get("action_type") == "INITIATE_CLOSING"
            assert action_t3.get("details", {}).get("product_name") == product_y_name
            assert action_t3.get("details", {}).get("price") == product_y_price_float

            ai_response_t3_content = state_after_confirmation.get("messages", [])[
                -1
            ].content
            assert (
                "prosseguir" in ai_response_t3_content.lower()
                or "finalizar" in ai_response_t3_content.lower()
            )
            assert product_y_name.lower() in ai_response_t3_content.lower()

            logger.success(f"{test_name} PASSED!")

        except AssertionError as e:
            logger.error(f"Assertion failed in {test_name}: {e}")
            if (
                final_state_after_closing_initiation
            ):  # Log the very final state if available
                logger.debug(
                    f"Final State for review: Goal={final_state_after_closing_initiation.get('current_agent_goal')}, LastAction={final_state_after_closing_initiation.get('last_agent_action')}, Messages={final_state_after_closing_initiation.get('messages')}"
                )
            elif "state_after_confirmation" in locals():
                logger.debug(
                    f"State after T3 confirmation for review: Goal={state_after_confirmation.get('current_agent_goal')}, LastAction={state_after_confirmation.get('last_agent_action')}, Messages={state_after_confirmation.get('messages')}"
                )
            elif "state_after_buying_signal" in locals():
                logger.debug(
                    f"State after T2 buying signal for review: Goal={state_after_buying_signal.get('current_agent_goal')}, LastAction={state_after_buying_signal.get('last_agent_action')}, Messages={state_after_buying_signal.get('messages')}"
                )
            elif "state_after_question" in locals():
                logger.debug(
                    f"State after T1 question for review: Goal={state_after_question.get('current_agent_goal')}, LastAction={state_after_question.get('last_agent_action')}, Messages={state_after_question.get('messages')}"
                )
            raise
        except Exception as e:
            logger.exception(f"Error during {test_name}: {e}")
            assert False, f"{test_name} Failed: {e}"
        finally:
            logger.info(f"--- {test_name} Finished ---")


if __name__ == "__main__":
    logger.info(
        "Starting integration test script (Question, Buying Signal, Confirm, Close)..."
    )
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_question_then_buying_signal_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    finally:
        logger.info(
            "Integration test script (Question, Buying Signal, Confirm, Close) finished."
        )
