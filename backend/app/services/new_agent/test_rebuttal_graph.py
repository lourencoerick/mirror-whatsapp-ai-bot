# backend/app/services/ai_reply/new_agent/graph.py

import asyncio
from typing import Dict, Any, Optional, List, Literal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import os
import time
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import copy
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

from app.services.new_agent.components.planner import (
    MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION,
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


from .state_definition import (
    IdentifiedNeedEntry,
    PendingAgentAction,
    AgentGoal,
    IdentifiedPainPointEntry,
    IdentifiedObjectionEntry,
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
        # Cenário de Teste
        # ================================================================================
        thread_id = str(uuid4())
        config = {
            "configurable": {
                "thread_id": thread_id,
                "llm_fast_instance": llm_fast_real,
                "llm_primary_instance": llm_primary_real,
                "db_session_factory": AsyncSessionLocal,
            }
        }
        initial_messages: List[BaseMessage] = [
            HumanMessage(content="Olá"),
            AIMessage(
                content="Olá! Apresento nosso Plano X que é ótimo para você."
            ),  # Agente apresentou
        ]
        state_turn0 = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            messages=initial_messages,
            current_user_input_text="",
            current_turn_number=1,  # Próximo turno será 1
            current_agent_goal=AgentGoal(
                goal_type="PRESENTING_SOLUTION",
                goal_details={"presenting_product": "Plano X"},
            ),
            last_agent_action=PendingAgentAction(
                action_type="PRESENT_SOLUTION_OFFER",
                details={},
                action_generation_text="Apresento o Plano X...",
                attempts=1,
            ),
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": None,
            },
            company_profile={
                "company_name": "Test Objection Co",
                "fallback_contact_info": "fallback.com",
                "language": "pt-br",
                "sales_tone": "consultivo",
                "business_description": "BD",
                "offering_overview": [],
                "key_selling_points": [],
                "communication_guidelines": [],
            },
            # ... (outros campos com defaults)
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=initial_messages[-1].content,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )
        # Persistir o estado inicial para a thread (LangGraph fará isso na primeira invocação)
        # Para simular, podemos apenas usar este como base para o input do próximo turno.

        # # --- Turno 1: Cliente levanta objeção ---
        # logger.info("\n--- Objection Cycle - Turn 1: User raises objection ---")
        # user_input_obj_raise = "O Plano X parece bom, mas o preço é muito alto."

        # # Preparar o input para o grafo (o que o LangGraph faria)
        # current_state_for_turn1 = copy.deepcopy(
        #     state_turn0
        # )  # Começa do estado anterior
        # current_state_for_turn1["current_user_input_text"] = user_input_obj_raise
        # current_state_for_turn1["messages"].append(
        #     HumanMessage(content=user_input_obj_raise)
        # )
        # # current_turn_number será incrementado pelo StateUpdater

        # try:
        #     state_after_rebuttal = await graph_app.ainvoke(
        #         current_state_for_turn1, config=config
        #     )

        #     logger.info(
        #         f"Turn 1 - Agent Goal: {state_after_rebuttal.get('current_agent_goal',{}).get('goal_type')}"
        #     )
        #     logger.info(
        #         f"Turn 1 - Agent Action: {state_after_rebuttal.get('last_agent_action',{}).get('action_type')}"
        #     )
        #     logger.info(
        #         f"Turn 1 - Agent Response: {state_after_rebuttal.get('last_agent_action',{}).get('action_generation_text')}"
        #     )

        #     assert (
        #         state_after_rebuttal.get("current_agent_goal", {}).get("goal_type")
        #         == "HANDLING_OBJECTION"
        #     )
        #     assert (
        #         state_after_rebuttal.get("last_agent_action", {}).get("action_type")
        #         == "GENERATE_REBUTTAL"
        #     )

        #     profile_after_rebuttal = state_after_rebuttal.get(
        #         "customer_profile_dynamic", {}
        #     )
        #     objections_after_rebuttal = profile_after_rebuttal.get(
        #         "identified_objections", []
        #     )
        #     assert len(objections_after_rebuttal) == 1
        #     assert (
        #         "preço é muito alto"
        #         in objections_after_rebuttal[0].get("text", "").lower()
        #     )
        #     assert (
        #         objections_after_rebuttal[0].get("status") == "addressing"
        #     )  # Ou "active" dependendo da sua lógica exata no StateUpdater
        #     assert objections_after_rebuttal[0].get("rebuttal_attempts") == 1

        #     # --- Turno 2 (Cenário 2a): Cliente responde positivamente ao rebuttal ---
        #     logger.info(
        #         "\n--- Objection Cycle - Turn 2: User responds positively (Objection Resolved) ---"
        #     )
        #     user_input_obj_resolved = (
        #         "Ah, entendi sobre as opções de pagamento. Isso ajuda!"
        #     )

        #     current_state_for_turn2 = copy.deepcopy(state_after_rebuttal)
        #     current_state_for_turn2["current_user_input_text"] = user_input_obj_resolved
        #     current_state_for_turn2["messages"].append(
        #         HumanMessage(content=user_input_obj_resolved)
        #     )

        #     final_state_resolved = await graph_app.ainvoke(
        #         current_state_for_turn2, config=config
        #     )

        #     logger.info(
        #         f"Turn 2 (Resolved) - Agent Goal: {final_state_resolved.get('current_agent_goal',{}).get('goal_type')}"
        #     )
        #     logger.info(
        #         f"Turn 2 (Resolved) - Agent Action: {final_state_resolved.get('last_agent_action',{}).get('action_type')}"
        #     )  # Deve ser None ou ação do goal retomado
        #     logger.info(
        #         f"Turn 2 (Resolved) - Agent Response: {final_state_resolved.get('last_agent_action',{}).get('action_generation_text')}"
        #     )

        #     # Verificar se o objetivo foi retomado (PRESENTING_SOLUTION)
        #     assert (
        #         final_state_resolved.get("current_agent_goal", {}).get("goal_type")
        #         == "PRESENTING_SOLUTION"
        #     )
        #     # Verificar se a objeção foi marcada como resolvida no perfil
        #     profile_resolved = final_state_resolved.get("customer_profile_dynamic", {})
        #     obj_resolved_entry = next(
        #         (
        #             o
        #             for o in profile_resolved.get("identified_objections", [])
        #             if "preço é muito alto" in o.get("text", "").lower()
        #         ),
        #         None,
        #     )
        #     assert obj_resolved_entry is not None
        #     assert obj_resolved_entry.get("status") == "resolved"
        #     # Verificar se a fila de interrupções está vazia (para esta objeção)
        #     interrupt_queue_resolved = final_state_resolved.get(
        #         "user_interruptions_queue", []
        #     )
        #     assert not any(
        #         inter.get("type") == "objection"
        #         and "preço é muito alto" in inter.get("text", "").lower()
        #         for inter in interrupt_queue_resolved
        #     )

        #     logger.success("Objection Cycle - Scenario 2a (Resolved) PASSED")

        # except Exception as e:
        #     logger.exception(f"Error during Objection Cycle Test: {e}")
        #     assert False, f"Objection Cycle Test Failed: {e}"
        # finally:
        #     # await checkpointer.aclose()
        #     logger.info("Checkpointer connection closed.")

        # # ================================================================================
        # # Cenário 2: Ciclo de Objeção Completo
        # # ================================================================================
        logger.info("\n--- Test Scenario 2: Full Objection Handling Cycle ---")
        thread_id_2 = str(uuid4())
        config_2 = dict(config["configurable"])
        config_2["thread_id"] = thread_id_2

        # --- Estado Inicial Comum para o Ciclo de Objeção ---
        common_initial_messages_obj_cycle: List[BaseMessage] = [
            HumanMessage(content="Olá, me fale sobre o Plano X."),
            AIMessage(
                content="Olá! O Plano X é excelente para [benefício chave]. Ele custa Y e inclui Z."
            ),  # Agente apresentou
        ]
        common_company_profile_obj_cycle = {
            "company_name": "Objection Master Co",
            "language": "pt-br",
            "sales_tone": "confiante",
            "fallback_contact_info": "Consulte nosso FAQ.",
            "business_description": "Vendemos o Plano X.",
            "offering_overview": [
                {"name": "Plano X", "short_description": "Descrição do Plano X"}
            ],
            "key_selling_points": ["Ótimo Custo-Benefício"],
            "communication_guidelines": [],
        }
        base_state_obj_cycle = RichConversationState(
            account_id=uuid4(),
            conversation_id=uuid4(),
            messages=list(common_initial_messages_obj_cycle),  # Cópia
            current_user_input_text="",
            current_turn_number=1,  # Próximo turno será 1
            current_agent_goal=AgentGoal(
                goal_type="PRESENTING_SOLUTION",
                goal_details={"presenting_product": "Plano X"},
            ),
            last_agent_action=PendingAgentAction(
                action_type="PRESENT_SOLUTION_OFFER",
                details={},
                action_generation_text=common_initial_messages_obj_cycle[-1].content,
                attempts=1,
            ),
            customer_profile_dynamic={
                "identified_needs": [],
                "identified_pain_points": [],
                "identified_objections": [],
                "certainty_levels": {},
                "last_discerned_intent": None,
            },
            company_profile=common_company_profile_obj_cycle,
            agent_config={},
            user_interruptions_queue=[],
            customer_question_log=[],
            current_turn_extracted_questions=[],
            active_proposal=None,
            closing_process_status="not_started",
            last_objection_handled_turn=None,
            retrieved_knowledge_for_next_action=None,
            last_agent_generation_text=common_initial_messages_obj_cycle[-1].content,
            conversation_summary_for_llm=None,
            last_interaction_timestamp=time.time(),
            is_simulation=False,
            last_processing_error=None,
            disengagement_reason=None,
            user_input_analysis_result=None,
        )

        # # --- Turno 1: Cliente levanta objeção "preço alto" ---
        # logger.info(
        #     "--- Objection Cycle - Turn 1: User raises 'price too high' objection ---"
        # )
        # user_input_t1 = "O Plano X parece bom, mas o preço é muito alto."
        # state_t1_input = copy.deepcopy(base_state_obj_cycle)
        # state_t1_input["current_user_input_text"] = user_input_t1
        # state_t1_input["messages"].append(HumanMessage(content=user_input_t1))

        # state_t1_output: RichConversationState = await graph_app.ainvoke(
        #     state_t1_input, config=config_2
        # )

        # logger.info(
        #     f"ObjCycle T1 - Agent Goal: {state_t1_output.get('current_agent_goal',{}).get('goal_type')}"
        # )
        # logger.info(
        #     f"ObjCycle T1 - Agent Action Type: {state_t1_output.get('last_agent_action',{}).get('action_type')}"
        # )
        # logger.info(
        #     f"ObjCycle T1 - Agent Response: {state_t1_output.get('last_agent_action',{}).get('action_generation_text')}"
        # )
        # profile_t1 = state_t1_output.get("customer_profile_dynamic", {})
        # objections_t1 = profile_t1.get("identified_objections", [])
        # assert (
        #     state_t1_output.get("current_agent_goal", {}).get("goal_type")
        #     == "HANDLING_OBJECTION"
        # )
        # assert (
        #     state_t1_output.get("last_agent_action", {}).get("action_type")
        #     == "GENERATE_REBUTTAL"
        # )
        # assert len(objections_t1) == 1
        # assert "preço é muito alto" in objections_t1[0].get("text", "").lower()
        # assert objections_t1[0].get("status") == "addressing"
        # assert objections_t1[0].get("rebuttal_attempts") == 1
        # logger.success(
        #     "ObjCycle T1: Objection raised and rebuttal planned successfully."
        # )

        # # --- Turno 2 (Cenário 2b): Objeção Persiste (Abaixo do Limite) ---
        # # logger.info(
        # #     "\n--- Objection Cycle - Turn 2 (Scenario 2b): Objection persists, below limit ---"
        # # )
        # # user_input_t2b = "Entendo os benefícios, mas ainda acho caro."
        # # state_t2b_input = copy.deepcopy(state_t1_output)  # Continuar do estado anterior
        # # state_t2b_input["current_user_input_text"] = user_input_t2b
        # # state_t2b_input["messages"].append(HumanMessage(content=user_input_t2b))

        # # state_t2b_output: RichConversationState = await graph_app.ainvoke(
        # #     state_t2b_input, config=config_2
        # # )

        # # logger.info(
        # #     f"ObjCycle T2b - Agent Goal: {state_t2b_output.get('current_agent_goal',{}).get('goal_type')}"
        # # )
        # # logger.info(
        # #     f"ObjCycle T2b - Agent Action Type: {state_t2b_output.get('last_agent_action',{}).get('action_type')}"
        # # )
        # # logger.info(
        # #     f"ObjCycle T2b - Agent Response: {state_t2b_output.get('last_agent_action',{}).get('action_generation_text')}"
        # # )
        # # profile_t2b = state_t2b_output.get("customer_profile_dynamic", {})
        # # objections_t2b = profile_t2b.get("identified_objections", [])

        # # assert (
        # #     state_t2b_output.get("current_agent_goal", {}).get("goal_type")
        # #     == "HANDLING_OBJECTION"
        # # )
        # # assert (
        # #     state_t2b_output.get("last_agent_action", {}).get("action_type")
        # #     == "GENERATE_REBUTTAL"
        # # )  # Gerou outro rebuttal
        # # assert len(objections_t2b) == 1
        # # obj_entry_t2b = next(
        # #     (o for o in objections_t2b if "preço" in o.get("text", "").lower()), None
        # # )
        # # assert obj_entry_t2b is not None
        # # assert obj_entry_t2b.get("status") == "addressing"  # Ainda está tratando
        # # assert obj_entry_t2b.get("rebuttal_attempts") == 2  # Segunda tentativa
        # # logger.success(
        # #     "ObjCycle T2b: Objection persists, second rebuttal planned successfully."
        # # )

        # # # --- Turno 3 (Cenário 2c): Objeção Persiste (Limite Atingido) ---
        # # logger.info(
        # #     "\n--- Objection Cycle - Turn 3 (Scenario 2c): Objection persists, limit reached ---"
        # # )
        # # user_input_t3c = "Não, realmente não dá. O preço é o problema."
        # # state_t3c_input = copy.deepcopy(
        # #     state_t2b_output
        # # )  # Continuar do estado anterior
        # # state_t3c_input["current_user_input_text"] = user_input_t3c
        # # state_t3c_input["messages"].append(HumanMessage(content=user_input_t3c))

        # # # Garantir que MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION seja 2 para este teste
        # # # Se for diferente, o teste pode não atingir o limite como esperado.
        # # # Poderíamos mockar a constante para o teste, mas é mais simples garantir que ela seja 2.
        # # original_max_attempts = MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION
        # # try:
        # #     # Temporariamente setar para 2 se for maior, para forçar o limite
        # #     # Isto é um pouco hacky para um teste de integração. Idealmente, o estado inicial
        # #     # da objeção já teria rebuttal_attempts = MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION - 1
        # #     # Mas como estamos construindo o estado turno a turno, vamos assim por enquanto.
        # #     # Se MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION já é 2, não faz nada.
        # #     # Se for 1, este teste já seria o de impasse.
        # #     # A lógica atual do planner é attempts < MAX, então se MAX=2, a 2a tentativa é <, a 3a não.
        # #     # O estado t2b_output já tem attempts = 2. Então a próxima tentativa seria a 3a.

        # #     state_t3c_output: RichConversationState = await graph_app.ainvoke(
        # #         state_t3c_input, config=config_2
        # #     )

        # #     logger.info(
        # #         f"ObjCycle T3c - Agent Goal: {state_t3c_output.get('current_agent_goal',{}).get('goal_type')}"
        # #     )
        # #     logger.info(
        # #         f"ObjCycle T3c - Agent Action Type: {state_t3c_output.get('last_agent_action',{}).get('action_type')}"
        # #     )
        # #     logger.info(
        # #         f"ObjCycle T3c - Agent Response: {state_t3c_output.get('last_agent_action',{}).get('action_generation_text')}"
        # #     )
        # #     profile_t3c = state_t3c_output.get("customer_profile_dynamic", {})
        # #     objections_t3c = profile_t3c.get("identified_objections", [])

        # #     assert (
        # #         state_t3c_output.get("current_agent_goal", {}).get("goal_type")
        # #         == "ENDING_CONVERSATION"
        # #     )  # Ou HANDLE_IMPASSE
        # #     assert (
        # #         state_t3c_output.get("last_agent_action", {}).get("action_type")
        # #         == "ACKNOWLEDGE_AND_TRANSITION"
        # #     )  # Ação de impasse

        # #     obj_entry_t3c = next(
        # #         (o for o in objections_t3c if "preço" in o.get("text", "").lower()),
        # #         None,
        # #     )
        # #     assert obj_entry_t3c is not None
        # #     assert (
        # #         obj_entry_t3c.get("status") == "active"
        # #     )  # Permanece ativa, mas o agente desistiu
        # #     assert (
        # #         obj_entry_t3c.get("rebuttal_attempts")
        # #         == MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION
        # #     )  # Ou MAX + 1 dependendo de quando incrementa
        # #     logger.success(
        # #         "ObjCycle T3c: Impasse due to max rebuttal attempts handled successfully."
        # #     )

        # # finally:
        # #     # Restaurar MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION se foi modificado (não foi neste caso)
        # #     # MAX_REBUTTAL_ATTEMPTS_PER_OBJECTION = original_max_attempts
        # #     pass

        # --- Cenário 2a: Objeção Resolvida (Re-fazer com estado limpo para isolar) ---
        logger.info(
            "\n--- Objection Cycle - Scenario 2a (Re-test): Objection Resolved ---"
        )
        thread_id_2a = str(uuid4())
        config_2a = dict(config["configurable"])
        config_2a["thread_id"] = thread_id_2a

        # Estado após o primeiro rebuttal (Turno 1 output)
        # Precisamos de um estado onde a objeção está 'addressing' e com attempts = 1
        state_after_first_rebuttal = copy.deepcopy(
            base_state_obj_cycle
        )  # Começar do base
        state_after_first_rebuttal["current_turn_number"] = (
            2  # Agente está no turno 2, cliente vai responder
        )
        state_after_first_rebuttal["current_agent_goal"] = AgentGoal(
            goal_type="HANDLING_OBJECTION",
            previous_goal_if_interrupted=base_state_obj_cycle[
                "current_agent_goal"
            ],  # O goal de PRESENTING_SOLUTION
            goal_details={"original_objection_text": "o preço é muito alto"},
        )
        state_after_first_rebuttal["customer_profile_dynamic"][
            "identified_objections"
        ] = [
            IdentifiedObjectionEntry(
                text="o preço é muito alto",
                status="addressing",
                rebuttal_attempts=1,
                source_turn=2,
            )
        ]
        state_after_first_rebuttal["last_agent_action"] = (
            PendingAgentAction(  # O rebuttal que foi feito
                action_type="GENERATE_REBUTTAL",
                details={"objection_text_to_address": "o preço é muito alto"},
                action_generation_text="Rebuttal sobre o preço...",
                attempts=1,
            )
        )
        state_after_first_rebuttal["messages"].append(
            HumanMessage(content="O Plano X parece bom, mas o preço é muito alto.")
        )  # Obj do user
        state_after_first_rebuttal["messages"].append(
            AIMessage(content="Rebuttal sobre o preço...")
        )  # Rebuttal do agente

        user_input_obj_resolved = (
            "Ah, entendi sobre as opções de pagamento. Isso ajuda!"
        )
        state_t2a_input = copy.deepcopy(state_after_first_rebuttal)
        state_t2a_input["current_user_input_text"] = user_input_obj_resolved
        state_t2a_input["messages"].append(
            HumanMessage(content=user_input_obj_resolved)
        )

        try:
            final_state_resolved = await graph_app.ainvoke(
                state_t2a_input, config=config_2a
            )

            logger.info(
                f"ObjCycle S2a - Agent Goal: {final_state_resolved.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"ObjCycle S2a - Agent Action Type: {final_state_resolved.get('last_agent_action',{}).get('action_type')}"
            )

            assert (
                final_state_resolved.get("current_agent_goal", {}).get("goal_type")
                == "PRESENTING_SOLUTION"
            )  # Retomou
            profile_resolved = final_state_resolved.get("customer_profile_dynamic", {})
            obj_resolved_entry = next(
                (
                    o
                    for o in profile_resolved.get("identified_objections", [])
                    if "preço é muito alto" in o.get("text", "").lower()
                ),
                None,
            )
            assert (
                obj_resolved_entry is not None
                and obj_resolved_entry.get("status") == "resolved"
            )
            logger.success("Objection Cycle - Scenario 2a (Resolved) PASSED")
        except Exception as e:
            logger.exception(f"Error during Objection Cycle Test (Scenario 2a): {e}")
            assert False, f"Objection Cycle Test (Scenario 2a) Failed: {e}"

        # --- Cenário 2d: Nova Objeção Levantada (Re-fazer com estado limpo) ---
        logger.info(
            "\n--- Objection Cycle - Scenario 2d (Re-test): New Objection Raised ---"
        )
        thread_id_2d = str(uuid4())
        config_2d = dict(config["configurable"])
        config_2d["thread_id"] = thread_id_2d

        # Estado após o primeiro rebuttal (similar ao S2a)
        state_after_first_rebuttal_for_new_obj = copy.deepcopy(
            state_after_first_rebuttal
        )  # Reutilizar estado base

        user_input_new_obj = (
            "Entendi o preço, mas agora estou preocupado com o tempo de implementação."
        )
        state_t2d_input = copy.deepcopy(state_after_first_rebuttal_for_new_obj)
        state_t2d_input["current_user_input_text"] = user_input_new_obj
        state_t2d_input["messages"].append(HumanMessage(content=user_input_new_obj))

        try:
            final_state_new_obj = await graph_app.ainvoke(
                state_t2d_input, config=config_2d
            )

            logger.info(
                f"ObjCycle S2d - Agent Goal: {final_state_new_obj.get('current_agent_goal',{}).get('goal_type')}"
            )
            logger.info(
                f"ObjCycle S2d - Agent Action Type: {final_state_new_obj.get('last_agent_action',{}).get('action_type')}"
            )

            profile_new_obj = final_state_new_obj.get("customer_profile_dynamic", {})
            objections_new_obj = profile_new_obj.get("identified_objections", [])

            original_obj_entry = next(
                (
                    o
                    for o in objections_new_obj
                    if "preço é muito alto" in o.get("text", "").lower()
                ),
                None,
            )
            new_raised_obj_entry = next(
                (
                    o
                    for o in objections_new_obj
                    if "tempo de implementação" in o.get("text", "").lower()
                ),
                None,
            )

            assert (
                original_obj_entry is not None
                and original_obj_entry.get("status") == "ignored"
            )
            assert (
                new_raised_obj_entry is not None
                and new_raised_obj_entry.get("status") == "addressing"
            )  # Pois o planner deve ter agendado rebuttal para ela

            # Verificar se o planner está agora focado na nova objeção
            assert (
                final_state_new_obj.get("current_agent_goal", {}).get("goal_type")
                == "HANDLING_OBJECTION"
            )
            assert (
                final_state_new_obj.get("current_agent_goal", {})
                .get("goal_details", {})
                .get("original_objection_text")
                == "preocupado com o tempo de implementação"
            )
            assert (
                final_state_new_obj.get("last_agent_action", {}).get("action_type")
                == "GENERATE_REBUTTAL"
            )  # Rebuttal para a NOVA objeção

            logger.success("Objection Cycle - Scenario 2d (New Objection) PASSED")
        except Exception as e:
            logger.exception(f"Error during Objection Cycle Test (Scenario 2d): {e}")
            assert False, f"Objection Cycle Test (Scenario 2d) Failed: {e}"

        finally:  # Fechar o checkpointer principal
            # await checkpointer.aclose()
            logger.info("Main checkpointer connection closed.")

    # --- Ponto de Entrada ---


if __name__ == "__main__":
    logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")
    logger.info("Starting integration test script (Full Cycle)...")
    try:
        asyncio.run(run_integration_test_full_cycle())
    except Exception as main_e:
        logger.exception(f"An error occurred during the main execution: {main_e}")
    logger.info("Integration test script (Full Cycle) finished.")
