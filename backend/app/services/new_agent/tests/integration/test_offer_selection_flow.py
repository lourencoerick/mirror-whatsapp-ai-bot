# backend/app/services/ai_reply/new_agent/tests/integration/test_offer_selection_flow.py

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
    IdentifiedPainPointEntry,  # Added for completeness
    ProposedSolution,
    DynamicCustomerProfile,
)
from app.services.new_agent.schemas.offer_selection_output import (
    OfferSelectionOutput,
    SelectedOffer,
)
from app.services.new_agent.schemas.input_analysis import (
    UserInputAnalysisOutput,  # Though not directly used for mocking input_processor here
    PendingAgentActionResponseAnalysis,
    ReactionToPresentation,
    ObjectionAfterRebuttalStatus,
)
from app.api.schemas.company_profile import CompanyProfileSchema, OfferingInfo


from app.database import AsyncSessionLocal

# Configuration
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
async def run_offer_selection_integration_test():
    test_name = "Integration Test - Offer Selection Flow"
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

    # --- Configure Checkpointer ---
    db_file = "integration_test_offer_selection_memory.sqlite"
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
        thread_id_offer_selection = str(uuid4())
        config_offer_selection = {
            "configurable": {
                **base_configurable_items,
                "thread_id": thread_id_offer_selection,
            }
        }

        # --- Initial State: User has gone through SPIN, expressed needs, and agent is about to present ---
        initial_messages: List[BaseMessage] = [
            HumanMessage(
                content="Olá, estou buscando uma solução para melhorar a performance da minha equipe."
            ),
            AIMessage(
                content="Olá! Entendido. Para que eu possa te ajudar melhor, poderia me dizer um pouco mais sobre os desafios de performance que sua equipe enfrenta? (Situation)"
            ),
            HumanMessage(
                content="O principal problema é que nossos computadores são lentos e antigos, e isso atrasa o trabalho de design gráfico. (Problem Answer)"
            ),
            AIMessage(
                content="Compreendo. E qual o impacto desses atrasos nos seus projetos e prazos? (Implication Question)"
            ),
            HumanMessage(
                content="Perdemos horas valiosas e às vezes até clientes por não entregar a tempo. (Implication Answer)"
            ),
            AIMessage(
                content="Entendo o quão frustrante isso pode ser. Se houvesse uma forma de acelerar drasticamente o processamento em design gráfico, eliminando esses gargalos, isso traria que tipo de benefício para vocês? (NeedPayoff Question)"
            ),
        ]
        user_confirms_benefit_for_presentation = "Isso seria fantástico! Significaria entregas mais rápidas e clientes mais satisfeitos."

        # Define OfferingInfo instances first
        offering1 = OfferingInfo(
            name="Workstation Criativa X1000",
            short_description="Potência máxima para design gráfico e vídeo.",
            key_features=[
                "CPU i9 de última geração",
                "GPU NVIDIA RTX 4090",
                "64GB RAM DDR5",
                "SSD NVMe 2TB ultrarrápido",
            ],
            price_info="R$15.000,00",
            link="https://techup.com/x1000",
            category="Hardware",
        )
        offering2 = OfferingInfo(
            name="Laptop Portátil P500",
            short_description="Performance e portabilidade para criativos em movimento.",
            key_features=["CPU i7", "GPU NVIDIA RTX 3070", "32GB RAM", "SSD NVMe 1TB"],
            price_info="R$9.500,00",
            link="https://techup.com/p500",
            category="Hardware",
        )
        offering3 = OfferingInfo(
            name="Software de Edição Pro",
            short_description="Suite completa para edição de imagem e vídeo.",
            key_features=["Licença vitalícia", "Plugins exclusivos"],
            price_info="R$1.200,00",
            category="Software",
            link=None,
        )
        offering4 = OfferingInfo(
            name="Consultoria de Otimização",
            short_description="Avaliamos e otimizamos seu fluxo de trabalho criativo.",
            key_features=[],
            price_info="R$350/hora",
            category="Serviço",
            link=None,
        )

        company_profile_data = CompanyProfileSchema(
            company_name="TechUp Soluções Criativas",
            language="pt-br",
            sales_tone="consultivo e prestativo",
            fallback_contact_info="techup.com/contato",
            business_description="Fornecemos hardware e software de ponta para profissionais criativos.",
            offering_overview=[offering1, offering2, offering3, offering4],
            key_selling_points=[
                "Equipamentos de Alta Performance",
                "Soluções Sob Medida",
                "Suporte Especializado",
            ],
            communication_guidelines=["Focar no benefício", "Ser transparente"],
            company_main_link_fallback="https://techup.com",
            address="Rua da Tecnologia, 404",
            opening_hours="9h-18h",
            target_audience="Profissionais e estúdios de design, vídeo e arquitetura.",
            delivery_options=["Entrega expressa para SP capital"],
            specific_faq=[],  # Ensure all required fields are present
            privacy_policy_link=None,
            social_media_links=None,
        )

        agent_config_data = {
            "max_follow_up_attempts": 2,
            "agent_name": "TechGuru",
            "agent_role": "Consultor de Soluções Criativas",
            "temperature_fast_llm": 0.1,
            "temperature_strategy_llm": 0.2,
            "temperature_primary_llm": 0.2,
            "model_fast_llm": "gpt-4o",
            "model_strategy_llm": "gpt-4o",
            "model_primary_llm": "gpt-4o",
            "embedding_model": "text-embedding-ada-002",
            "rag_chunk_limit": 3,
            "rag_similarity_threshold": 0.7,
        }

        initial_state = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            bot_agent_id=None,
            messages=list(initial_messages),
            current_user_input_text=user_confirms_benefit_for_presentation,
            current_turn_number=len(initial_messages) // 2 + 1,  # Start of Turn 4
            current_agent_goal=AgentGoal(
                goal_type="INVESTIGATING_NEEDS",
                goal_details={
                    "last_spin_type_asked": "NeedPayoff",
                    "spin_questions_asked_this_cycle": 3,
                },
            ),
            last_agent_action=PendingAgentAction(
                action_type="ASK_SPIN_QUESTION",
                details={"spin_type": "NeedPayoff"},
                action_generation_text=initial_messages[-1].content,  # type: ignore
                attempts=1,
            ),
            customer_profile_dynamic=DynamicCustomerProfile(
                identified_needs=[
                    IdentifiedNeedEntry(
                        text="acelerar processamento em design gráfico",
                        status="confirmed_by_user",
                        priority=1,
                        source_turn=3,
                    ),
                    IdentifiedNeedEntry(
                        text="eliminar gargalos de lentidão",
                        status="confirmed_by_user",
                        priority=1,
                        source_turn=3,
                    ),
                ],
                identified_pain_points=[
                    IdentifiedPainPointEntry(text="computadores lentos e antigos", status="confirmed_by_user", source_turn=2),  # type: ignore
                    IdentifiedPainPointEntry(text="perda de horas e clientes por atrasos", status="confirmed_by_user", source_turn=3),  # type: ignore
                ],
                identified_objections=[],
                certainty_levels={
                    "product": None,
                    "agent": None,
                    "company": None,
                    "last_assessed_turn": None,
                },
                last_discerned_intent="PositiveFeedbackToProposal",  # Simulating input_processor output
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
            last_interaction_timestamp=time.time() - 100,
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,  # This will be populated by input_processor node first
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
            f"\n--- {test_name} - Turn: User confirms benefit, agent should select and present offer ---"
        )

        mock_selected_offer_details = SelectedOffer(
            product_name="Workstation Criativa X1000",
            reason_for_selection="O cliente confirmou a necessidade de performance para design gráfico, e a X1000 é ideal para isso.",
            confidence_score=0.95,
            key_benefit_to_highlight="performance máxima para design gráfico com sua CPU i9 e RTX 4090",
        )
        mock_offer_selection_llm_output = OfferSelectionOutput(
            selected_offer=mock_selected_offer_details,
            no_suitable_offer_found=False,
            overall_justification="Workstation Criativa X1000 é a melhor opção para a necessidade de performance em design.",
        )

        # Patch the _call_structured_llm within offer_selector module
        with patch(
            "app.services.new_agent.components.offer_selector._call_structured_llm",
            AsyncMock(return_value=mock_offer_selection_llm_output),
        ) as mock_offer_selector_llm_call:
            try:
                # For this test, we also want to see the intermediate states if possible,
                # or at least ensure the planner is called multiple times as expected.
                # However, a single ainvoke will run the graph to completion for this input.

                logger.debug(
                    f"Invoking graph with initial state (turn {initial_state['current_turn_number']}) for offer selection flow."
                )
                final_state_after_presentation: RichConversationState = (
                    await graph_app.ainvoke(
                        initial_state, config=config_offer_selection
                    )
                )

                logger.info(
                    f"{test_name} - Input User Message: {initial_state['current_user_input_text']}"
                )
                logger.info(
                    f"{test_name} - Output State from invoke (turn {final_state_after_presentation.get('current_turn_number')}):"
                )
                logger.info(
                    f"  Final Goal: {final_state_after_presentation.get('current_agent_goal')}"
                )
                logger.info(
                    f"  Last Action: {final_state_after_presentation.get('last_agent_action')}"
                )
                final_messages = final_state_after_presentation.get("messages", [])
                logger.info(
                    f"  Final AI Message: {final_messages[-1].content if final_messages and isinstance(final_messages[-1], AIMessage) else 'N/A'}"
                )

                # 1. Check if offer_selector's LLM (mocked) was called
                mock_offer_selector_llm_call.assert_called_once()

                # 2. Planner should have processed this and planned PRESENT_SOLUTION_OFFER
                final_action = final_state_after_presentation.get("last_agent_action")
                assert final_action is not None, "Last agent action should exist"
                assert (
                    final_action.get("action_type") == "PRESENT_SOLUTION_OFFER"
                ), "Final action should be to present the selected solution"
                assert (
                    final_action.get("details", {}).get("product_name_to_present")
                    == "Workstation Criativa X1000"
                )
                assert "performance máxima" in final_action.get("details", {}).get(
                    "key_benefit_to_highlight", ""
                )

                # 3. An active_proposal should be set
                active_proposal = final_state_after_presentation.get("active_proposal")
                key_benefits_list = active_proposal.get("key_benefits_highlighted", [])
                assert isinstance(
                    key_benefits_list, list
                ), "key_benefits_highlighted should be a list"
                assert (
                    len(key_benefits_list) > 0
                ), "key_benefits_highlighted should not be empty"

                assert (
                    active_proposal is not None
                ), "Active proposal should be set in the state"
                assert isinstance(
                    active_proposal, dict
                ), "Active proposal should be a dictionary"
                assert (
                    active_proposal.get("product_name") == "Workstation Criativa X1000"
                )
                assert (
                    "performance máxima" in key_benefits_list[0].lower()
                ), f"Expected 'performance máxima' in highlighted benefits, got: {key_benefits_list[0]}"
                assert active_proposal.get("price_info") == "R$15.000,00"
                assert active_proposal.get("product_url") == "https://techup.com/x1000"

                # 4. Check the AI's response message
                last_ai_message = final_messages[-1]
                assert isinstance(
                    last_ai_message, AIMessage
                ), "Last message should be from AI"
                response_content = last_ai_message.content.lower()  # type: ignore
                logger.info(
                    f"{test_name} - Generated AI Presentation: {last_ai_message.content}"
                )

                assert (
                    "workstation criativa x1000" in response_content
                ), "AI response should mention the selected product"
                assert (
                    "performance" in response_content
                    or "design gráfico" in response_content
                ), "AI response should mention the key benefit context"
                # assert (
                #     "r$15.000,00" in response_content or "15.000" in response_content
                # ), "AI response should mention price if available"
                # Check for specific features mentioned in the key_benefit_to_highlight or product description
                assert (
                    "cpu i9" in response_content
                    or "rtx 4090" in response_content
                    or "potência máxima" in response_content
                ), "AI response should use details to describe"

                # 5. Temporary fields should be cleared
                assert (
                    final_state_after_presentation.get("offer_selection_result") is None
                ), "offer_selection_result should be cleared"
                assert (
                    final_state_after_presentation.get("next_agent_action_command")
                    is None
                )
                assert (
                    final_state_after_presentation.get("user_input_analysis_result")
                    is None
                )  # Also check this

                logger.success(f"{test_name} PASSED!")

            except AssertionError as e:
                logger.error(f"Assertion failed in {test_name}: {e}")
                if "final_state_after_presentation" in locals():  # type: ignore
                    logger.debug(
                        f"Final State for review: Goal={final_state_after_presentation.get('current_agent_goal')}, LastAction={final_state_after_presentation.get('last_agent_action')}, ActiveProposal={final_state_after_presentation.get('active_proposal')}, Messages={final_state_after_presentation.get('messages')}"
                    )
                raise
            except Exception as e:
                logger.exception(f"Error during {test_name}: {e}")
                assert False, f"{test_name} Failed: {e}"
            finally:
                logger.info(f"--- {test_name} Finished ---")

    logger.info(f"Integration test logs are in: {log_file_name}")


if __name__ == "__main__":
    logger.info("Starting integration test script (Offer Selection Flow)...")
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_offer_selection_integration_test())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Offer Selection Flow) finished.")
