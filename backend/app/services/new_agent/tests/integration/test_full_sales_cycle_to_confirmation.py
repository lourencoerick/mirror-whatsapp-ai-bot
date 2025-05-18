# backend/app/services/ai_reply/new_agent/tests/integration/test_full_sales_cycle_to_confirmation.py

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
    ClosingProcessStatusType,
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
async def run_full_sales_cycle_test():
    test_name = "Integration Test - Full Sales Cycle to Order Confirmation"
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
            "request_timeout": 75,
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

    db_file = "integration_test_full_sales_cycle.sqlite"
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

        product_z_name = "Produto Z Premium"
        product_z_price_str = "R$249,99"  # As it appears in company profile
        product_z_price_float = 249.99
        product_z_feature = "automação completa de tarefas"
        product_z_link = "http://testcomp.com/produto-z"

        company_profile_data = {
            "company_name": "TestComp Completa",
            "language": "pt-br",
            "sales_tone": "eficiente",
            "fallback_contact_info": "testcomp.com/suporte",
            "business_description": f"Oferecemos o {product_z_name} para {product_z_feature}.",
            "offering_overview": [
                {
                    "name": product_z_name,
                    "short_description": f"Ideal para {product_z_feature}.",
                    "price_info": product_z_price_str,
                    "key_features": [product_z_feature, "Relatórios Avançados"],
                    "target_audience_fit": "Empresas que buscam máxima produtividade",
                    "bonus_items": ["Setup prioritário"],
                    "link": product_z_link,
                    "category": "Software Premium",
                    "details_url": None,
                }
            ],
            "key_selling_points": ["Tecnologia de Ponta", "Resultados Garantidos"],
            "communication_guidelines": [],
            "address": None,
            "opening_hours": None,
            "target_audience": None,
            "delivery_options": [],
            "company_main_link_fallback": "http://testcomp.com",
            "specific_faq": [
                {
                    "question": "automação",
                    "answer": f"Nossa principal solução de automação é o {product_z_name}. Ele oferece {product_z_feature} e custa {product_z_price_str}.",
                }
            ],
            "privacy_policy_link": None,
            "social_media_links": {},
        }
        agent_config_data = {
            "max_follow_up_attempts": 2,
            "agent_name": "Assistente Premium",
            "agent_role": "Especialista",
            "temperature_fast_llm": 0.1,
            "temperature_strategy_llm": 0.1,
            "temperature_primary_llm": 0.1,
            "model_fast_llm": "gpt-4o",
            "model_strategy_llm": "gpt-4o",
            "model_primary_llm": "gpt-4o",
            "embedding_model": "text-embedding-ada-002",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.7,
        }

        # Initial state: User has just been greeted by the agent.
        initial_messages_t0: List[BaseMessage] = [
            HumanMessage(content="Olá"),
            AIMessage(
                content="Olá! Sou o Assistente Premium da TestComp Completa. Como posso ajudar com suas necessidades de automação hoje?"
            ),
        ]
        current_state = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages_t0),
            current_user_input_text="",
            current_turn_number=1,  # Turn after greeting
            current_agent_goal=AgentGoal(
                goal_type="INVESTIGATING_NEEDS", goal_details={}
            ),  # Ready to investigate
            last_agent_action=PendingAgentAction(
                action_type="GENERATE_GREETING",
                details={},
                action_generation_text=initial_messages_t0[-1].content,
                attempts=1,
            ),
            customer_profile_dynamic={
                "identified_needs": [
                    IdentifiedNeedEntry(
                        text=product_z_feature,
                        status="active",
                        source_turn=0,
                        priority=10,
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
            last_agent_generation_text=initial_messages_t0[-1].content,
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

        mock_no_proactive = ProactiveStepDecision(
            proactive_action_command=None,
            suggested_next_goal_type=None,
            justification="Test flow: No proactive action needed.",
        )

        # To store the very final state for debugging if any assertion fails
        final_test_state_for_logging = None

        try:
            # --- Turn 1: User asks about automation solutions ---
            logger.info(
                f"\n--- {test_name} - Turn 1: User asks about automation solutions ---"
            )
            user_input_t1 = "Me fale sobre suas soluções de automação."
            current_state["current_user_input_text"] = user_input_t1
            current_state["messages"].append(HumanMessage(content=user_input_t1))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive),
            ):
                state_t1: RichConversationState = await graph_app.ainvoke(
                    copy.deepcopy(current_state), config=config_test
                )
            current_state = state_t1
            final_test_state_for_logging = current_state

            logger.info(
                f"  T1 Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}, Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T1 Agent Response: {current_state.get('messages', [])[-1].content}"
            )
            assert current_state.get("current_turn_number") == 2
            # Planner should see this as a question and answer it. The answer might present the solution.
            assert (
                current_state.get("current_agent_goal", {}).get("goal_type")
                == "CLARIFYING_USER_INPUT"
            )
            assert (
                current_state.get("last_agent_action", {}).get("action_type")
                == "ANSWER_DIRECT_QUESTION"
            )
            # The response generator for ANSWER_DIRECT_QUESTION might present Produto Z here.
            # We are not asserting active_proposal yet, as ANSWER_DIRECT_QUESTION doesn't set it.

            # --- Turn 2: User expresses strong interest / buying signal for Produto Z ---
            logger.info(
                f"\n--- {test_name} - Turn 2: User gives buying signal for {product_z_name} ---"
            )
            user_input_t2 = (
                f"Excelente! O {product_z_name} parece ser o que preciso. Quero fechar!"
            )
            current_state["current_user_input_text"] = user_input_t2
            current_state["messages"].append(HumanMessage(content=user_input_t2))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive),
            ):
                state_t2: RichConversationState = await graph_app.ainvoke(
                    copy.deepcopy(current_state), config=config_test
                )
            current_state = state_t2
            final_test_state_for_logging = current_state

            logger.info(
                f"  T2 Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}, Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T2 Agent Response: {current_state.get('messages', [])[-1].content}"
            )
            assert current_state.get("current_turn_number") == 3
            assert (
                current_state.get("current_agent_goal", {}).get("goal_type")
                == "PRESENTING_SOLUTION"
            )
            assert (
                current_state.get("last_agent_action", {}).get("action_type")
                == "PRESENT_SOLUTION_OFFER"
            )
            assert (
                current_state.get("last_agent_action", {})
                .get("details", {})
                .get("product_name_to_present")
                == product_z_name
            )
            assert (
                current_state.get("active_proposal") is not None
            ), "active_proposal should be set"
            assert (
                current_state.get("active_proposal", {}).get("product_name")
                == product_z_name
            )
            assert (
                current_state.get("active_proposal", {}).get("price")
                == product_z_price_float
            )

            # --- Turn 3: User confirms the offer presented in Turn 2 ---
            logger.info(f"\n--- {test_name} - Turn 3: User confirms offer ---")
            user_input_t3 = "Sim, essa oferta do Produto Z Premium me parece ótima. Vamos prosseguir."
            current_state["current_user_input_text"] = user_input_t3
            current_state["messages"].append(HumanMessage(content=user_input_t3))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive),
            ):
                state_t3: RichConversationState = await graph_app.ainvoke(
                    copy.deepcopy(current_state), config=config_test
                )
            current_state = state_t3
            final_test_state_for_logging = current_state

            logger.info(
                f"  T3 Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}, Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T3 Agent Response: {current_state.get('messages', [])[-1].content}"
            )
            assert current_state.get("current_turn_number") == 4
            assert (
                current_state.get("current_agent_goal", {}).get("goal_type")
                == "ATTEMPTING_CLOSE"
            )
            assert (
                current_state.get("last_agent_action", {}).get("action_type")
                == "INITIATE_CLOSING"
            )
            assert (
                current_state.get("last_agent_action", {})
                .get("details", {})
                .get("product_name")
                == product_z_name
            )
            # After user confirms offer, state_updater should set closing_process_status based on intent
            # If intent is ConfirmingCloseAttempt/PositiveFeedbackToProposal after PRESENT_SOLUTION_OFFER,
            # state_updater might set status to 'attempt_made' or 'awaiting_confirmation'.
            # Planner's ATTEMPTING_CLOSE logic for 'not_started' or 'attempt_made' leads to INITIATE_CLOSING.
            # Let's check the status *after* this turn, which will be input to next.
            # The state_updater for *this* turn (T3) will process the "Sim, confirmo..."
            # If last action was INITIATE_CLOSING and intent is ConfirmingCloseAttempt, status becomes 'awaiting_confirmation'.
            # This is tricky to assert mid-turn vs end-of-turn state.
            # For now, let's assume the planner correctly plans INITIATE_CLOSING.
            # The closing_process_status in *this* state_t3 might still be 'not_started' or 'attempt_made'
            # before state_updater of this turn processes the user's "Sim, confirmo..."

            # --- Turn 4: User confirms to proceed with details (after INITIATE_CLOSING) ---
            logger.info(
                f"\n--- {test_name} - Turn 4: User confirms to proceed with details ---"
            )
            user_input_t4 = "Sim, pode confirmar os detalhes."
            current_state["current_user_input_text"] = user_input_t4
            current_state["messages"].append(HumanMessage(content=user_input_t4))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive),
            ):
                state_t4: RichConversationState = await graph_app.ainvoke(
                    copy.deepcopy(current_state), config=config_test
                )
            current_state = state_t4
            final_test_state_for_logging = current_state

            logger.info(
                f"  T4 Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}, Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T4 Agent Response: {current_state.get('messages', [])[-1].content}"
            )
            assert current_state.get("current_turn_number") == 5
            assert (
                current_state.get("current_agent_goal", {}).get("goal_type")
                == "ATTEMPTING_CLOSE"
            )
            assert (
                current_state.get("last_agent_action", {}).get("action_type")
                == "CONFIRM_ORDER_DETAILS"
            )
            assert (
                current_state.get("closing_process_status") == "awaiting_confirmation"
            ), f"Expected status 'awaiting_confirmation', got {current_state.get('closing_process_status')}"

            # --- Turn 5: User gives final confirmation of details ---
            logger.info(
                f"\n--- {test_name} - Turn 5: User gives final confirmation ---"
            )
            user_input_t5 = "Tudo certo, confirmo tudo!"
            current_state["current_user_input_text"] = user_input_t5
            current_state["messages"].append(HumanMessage(content=user_input_t5))

            with patch(
                "app.services.new_agent.components.proactive_step_decider._call_structured_llm",
                AsyncMock(return_value=mock_no_proactive),
            ):
                state_t5: RichConversationState = await graph_app.ainvoke(
                    copy.deepcopy(current_state), config=config_test
                )
            current_state = state_t5
            final_test_state_for_logging = current_state

            logger.info(
                f"  T5 Goal: {current_state.get('current_agent_goal',{}).get('goal_type')}, Action: {current_state.get('last_agent_action',{}).get('action_type')}"
            )
            logger.info(
                f"  T5 Agent Response: {current_state.get('messages', [])[-1].content}"
            )
            assert current_state.get("current_turn_number") == 6
            assert (
                current_state.get("current_agent_goal", {}).get("goal_type")
                == "ATTEMPTING_CLOSE"
            )
            assert (
                current_state.get("last_agent_action", {}).get("action_type")
                == "PROCESS_ORDER_CONFIRMATION"
            )
            assert (
                current_state.get("closing_process_status") == "confirmed_success"
            ), f"Expected status 'confirmed_success', got {current_state.get('closing_process_status')}"

            ai_response_t5_content = current_state.get("messages", [])[-1].content
            assert product_z_name.lower() in ai_response_t5_content.lower()
            assert (
                "pedido registrado" in ai_response_t5_content.lower()
                or "confirmado com sucesso" in ai_response_t5_content.lower()
                or "obrigado" in ai_response_t5_content.lower()
            )
            if product_z_link:
                assert product_z_link in ai_response_t5_content

            logger.success(f"{test_name} PASSED!")

        except AssertionError as e:
            logger.error(
                f"Assertion failed in {test_name} at turn {final_test_state_for_logging.get('current_turn_number') if final_test_state_for_logging else 'Unknown'}: {e}"
            )
            if final_test_state_for_logging:
                logger.debug(
                    f"Final State for review: Goal={final_test_state_for_logging.get('current_agent_goal')}, LastAction={final_test_state_for_logging.get('last_agent_action')}, ClosingStatus={final_test_state_for_logging.get('closing_process_status')}, Messages={final_test_state_for_logging.get('messages')}"
                )
            raise
        except Exception as e:
            logger.exception(f"Error during {test_name}: {e}")
            assert False, f"{test_name} Failed: {e}"
        finally:
            logger.info(f"--- {test_name} Finished ---")


if __name__ == "__main__":
    logger.info("Starting integration test script (Full Sales Cycle)...")
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_full_sales_cycle_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    finally:
        logger.info("Integration test script (Full Sales Cycle) finished.")
