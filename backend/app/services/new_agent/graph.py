# backend/app/services/ai_reply/new_agent/graph.py

from typing import Literal
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

# Definição do Estado Central
from .state_definition import RichConversationState

# Importar os nós do grafo
from .components.input_processor import process_user_input_node
from .components.state_updater import update_conversation_state_node
from .components.planner import goal_and_action_planner_node
from .components.knowledge_retriever import knowledge_retriever_node
from .components.response_generator import response_generator_node
from .components.output_formatter import output_formatter_node
from .components.final_state_updater import finalize_turn_state_node

# --- Função de Roteamento Condicional ---


def route_action(
    state: RichConversationState,
) -> Literal["knowledge_retriever", "response_generator", "__end__"]:
    """
    Determines the next node based on the planned action command.

    Routes to the knowledge retriever if the planned action requires RAG,
    directly to the response generator if an action is planned but doesn't
    require RAG, or ends the turn if no action is planned.

    Args:
        state: The current conversation state, containing
               `next_agent_action_command`.

    Returns:
        A literal string indicating the next node ('knowledge_retriever',
        'response_generator') or the end state ('__end__').
    """
    action_command = state.get("next_agent_action_command")
    logger.debug(f"[Router: route_action] Planned action: {action_command}")

    # Define actions that require fetching knowledge from the vector store
    actions_requiring_rag = [
        "ANSWER_DIRECT_QUESTION",
        "GENERATE_REBUTTAL",
        "PRESENT_SOLUTION_OFFER",  # Added: Presentation might benefit from RAG
    ]

    if action_command in actions_requiring_rag:
        logger.info("[Router: route_action] Routing to knowledge_retriever.")
        return "knowledge_retriever"
    elif action_command:
        # Action planned, but doesn't need RAG (e.g., ASK_SPIN_QUESTION, INITIATE_CLOSING)
        logger.info("[Router: route_action] Routing directly to response_generator.")
        return "response_generator"
    else:
        # No action planned by the planner (e.g., waiting for user, impasse handled)
        logger.info("[Router: route_action] No action planned. Ending turn.")
        return END


# --- Função para Criar o Grafo Completo ---


def create_agent_graph(checkpointer: BaseCheckpointSaver) -> StateGraph:
    """
    Builds and compiles the complete LangGraph state machine for the AI sales agent.

    This graph orchestrates the flow of information and decision-making through
    various processing nodes, starting from user input and ending with the final
    agent response and state update.

    Args:
        checkpointer: An instance of a LangGraph checkpointer (e.g.,
                      AsyncSqliteSaver) used for persisting conversation state,
                      enabling resumability.

    Returns:
        A compiled StateGraph application ready to process conversation states.
        Returns None if essential node functions are not callable.
    """
    workflow = StateGraph(RichConversationState)
    logger.info("Initializing AI Sales Agent Graph...")

    # Define the nodes in the graph
    nodes = [
        ("process_input", process_user_input_node),
        ("update_state", update_conversation_state_node),
        ("planner", goal_and_action_planner_node),
        ("knowledge_retriever", knowledge_retriever_node),
        ("response_generator", response_generator_node),
        ("output_formatter", output_formatter_node),
        ("finalize_turn_state", finalize_turn_state_node),
    ]

    # Add nodes to the graph, checking if they are callable
    for name, node_func in nodes:
        if not callable(node_func):
            logger.error(
                f"Node function '{name}' is not callable. Aborting graph creation."
            )
            # Consider raising an error instead of returning None for clearer failure
            raise TypeError(f"Node function '{name}' is not callable.")
        workflow.add_node(name, node_func)
        logger.debug(f"Added node: {name}")

    # Define the edges and control flow
    workflow.set_entry_point("process_input")
    logger.debug("Set entry point to 'process_input'")

    workflow.add_edge("process_input", "update_state")
    logger.debug("Added edge: process_input -> update_state")

    workflow.add_edge("update_state", "planner")
    logger.debug("Added edge: update_state -> planner")

    # Conditional routing based on the planner's decision
    workflow.add_conditional_edges(
        "planner",
        route_action,
        {
            "knowledge_retriever": "knowledge_retriever",
            "response_generator": "response_generator",
            END: END,
        },
    )
    logger.debug("Added conditional edges from 'planner' based on route_action")

    workflow.add_edge("knowledge_retriever", "response_generator")
    logger.debug("Added edge: knowledge_retriever -> response_generator")

    workflow.add_edge("response_generator", "output_formatter")
    logger.debug("Added edge: response_generator -> output_formatter")

    workflow.add_edge("output_formatter", "finalize_turn_state")
    logger.debug("Added edge: output_formatter -> finalize_turn_state")

    # The final state updater leads to the end of the current graph invocation
    workflow.add_edge("finalize_turn_state", END)
    logger.debug("Added edge: finalize_turn_state -> END")

    # Compile the graph with the checkpointer
    logger.info("Compiling AI Sales Agent Graph...")
    try:
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        logger.info("AI Sales Agent Graph compiled successfully.")
        return compiled_graph
    except Exception as e:
        logger.exception(f"Failed to compile the graph: {e}")
        raise  # Re-raise the exception after logging
