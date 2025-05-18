# backend/app/services/ai_reply/new_agent/graph.py

from typing import Literal, Optional
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

# Definição do Estado Central
from .state_definition import RichConversationState, AgentActionType

# Importar os nós do grafo
from .components.input_processor import process_user_input_node
from .components.state_updater import update_conversation_state_node
from .components.planner import goal_and_action_planner_node
from .components.knowledge_retriever import knowledge_retriever_node
from .components.response_generator import response_generator_node
from .components.output_formatter import output_formatter_node
from .components.final_state_updater import finalize_turn_state_node
from .components.proactive_step_decider import proactive_step_decider_node

# --- Função de Roteamento Condicional ---


def route_action(
    state: RichConversationState,
) -> Literal["planner", "knowledge_retriever", "response_generator", "__end__"]:
    """
    Determines the next node based on the planned action command.

    Routes to:
    - 'planner': If the action is 'REPLAN_WITH_SUGGESTED_GOAL'.
    - 'knowledge_retriever': If the planned action requires RAG.
    - 'response_generator': If an action is planned but doesn't require RAG.
    - '__end__': If no action is planned (ends the turn).

    Args:
        state: The current conversation state.

    Returns:
        A literal string indicating the next node or the end state.
    """
    action_command: Optional[AgentActionType] = state.get("next_agent_action_command")
    logger.debug(f"[Router: route_action] Planned action: {action_command}")

    if action_command == "REPLAN_WITH_SUGGESTED_GOAL":
        logger.info(
            "[Router: route_action] Action is REPLAN_WITH_SUGGESTED_GOAL. Routing to planner."
        )
        return "planner"

    if action_command == "DECIDE_PROACTIVE_STEP":
        logger.warning(
            "[Router: route_action] Encountered DECIDE_PROACTIVE_STEP. This might indicate a routing loop if not handled by edge logic. Assuming it's a final action from proactive_decider for now."
        )
        pass  # Removed explicit handling of DECIDE_PROACTIVE_STEP here.

    actions_requiring_rag = [
        "ANSWER_DIRECT_QUESTION",
        "GENERATE_REBUTTAL",
        "PRESENT_SOLUTION_OFFER",
    ]

    if action_command in actions_requiring_rag:
        logger.info(
            f"[Router: route_action] Action '{action_command}' requires RAG. Routing to knowledge_retriever."
        )
        return "knowledge_retriever"
    elif action_command:
        # This includes simple actions from proactive_step_decider like SEND_FOLLOW_UP_MESSAGE
        logger.info(
            f"[Router: route_action] Action '{action_command}' does not require RAG. Routing to response_generator."
        )
        return "response_generator"
    else:
        logger.info("[Router: route_action] No action command found. Ending turn.")
        return END


# --- Função para Criar o Grafo Completo ---
def create_agent_graph(checkpointer: BaseCheckpointSaver) -> StateGraph:
    """
    Builds and compiles the complete LangGraph state machine for the AI sales agent.
    """
    workflow = StateGraph(RichConversationState)
    logger.info("Initializing AI Sales Agent Graph...")

    nodes_map = {
        "process_input": process_user_input_node,
        "update_state": update_conversation_state_node,
        "planner": goal_and_action_planner_node,
        "proactive_step_decider": proactive_step_decider_node,
        "knowledge_retriever": knowledge_retriever_node,
        "response_generator": response_generator_node,
        "output_formatter": output_formatter_node,
        "finalize_turn_state": finalize_turn_state_node,
    }

    for name, node_func in nodes_map.items():
        if not callable(node_func):
            logger.error(
                f"Node function '{name}' is not callable. Aborting graph creation."
            )
            raise TypeError(f"Node function '{name}' is not callable.")
        workflow.add_node(name, node_func)
        logger.debug(f"Added node: {name}")

    workflow.set_entry_point("process_input")
    logger.debug("Set entry point to 'process_input'")

    workflow.add_edge("process_input", "update_state")
    workflow.add_edge("update_state", "planner")

    # Conditional routing from planner
    # The planner can decide to:
    # 1. Go to proactive_step_decider (if it sets next_agent_action_command to "DECIDE_PROACTIVE_STEP")
    # 2. Go to knowledge_retriever (for RAG actions)
    # 3. Go to response_generator (for non-RAG actions)
    # 4. End the turn (if next_agent_action_command is None)
    def route_from_planner(
        state: RichConversationState,
    ) -> Literal[
        "proactive_step_decider", "knowledge_retriever", "response_generator", "__end__"
    ]:
        action_command = state.get("next_agent_action_command")
        if action_command == "DECIDE_PROACTIVE_STEP":
            logger.info(
                "[Router: route_from_planner] Planner decided to take initiative. Routing to proactive_step_decider."
            )
            return "proactive_step_decider"
        # If not DECIDE_PROACTIVE_STEP, use the main route_action logic
        # which will handle RAG, non-RAG, or END.
        # Crucially, route_action does NOT route to proactive_step_decider itself.
        # It also doesn't route to "planner" unless action is REPLAN_WITH_SUGGESTED_GOAL (which planner won't output directly)
        # So we cast its output here.
        return route_action(state)  # type: ignore

    workflow.add_conditional_edges(
        "planner",
        route_from_planner,  # Use the specialized router for planner's output
        {
            "proactive_step_decider": "proactive_step_decider",  # Explicitly route to proactive if planner says so
            "knowledge_retriever": "knowledge_retriever",  # From route_action
            "response_generator": "response_generator",  # From route_action
            "planner": "planner",  # From route_action (if REPLAN - though planner won't output this directly)
            END: END,  # From route_action
        },
    )
    logger.debug("Added conditional edges from 'planner'")

    # Conditional routing from proactive_step_decider
    # The proactive_step_decider will set next_agent_action_command to:
    # 1. A simple action (e.g., SEND_FOLLOW_UP_MESSAGE) -> route_action handles RAG/non-RAG
    # 2. "REPLAN_WITH_SUGGESTED_GOAL" -> route_action routes to "planner"
    # 3. None (if LLM decides no action) -> route_action routes to END
    workflow.add_conditional_edges(
        "proactive_step_decider",
        route_action,  # The main route_action can handle all outputs of proactive_step_decider
        {
            "planner": "planner",  # If REPLAN_WITH_SUGGESTED_GOAL
            "knowledge_retriever": "knowledge_retriever",
            "response_generator": "response_generator",
            END: END,
        },
    )
    logger.debug(
        "Added conditional edges from 'proactive_step_decider' using main route_action"
    )

    workflow.add_edge("knowledge_retriever", "response_generator")
    workflow.add_edge("response_generator", "output_formatter")
    workflow.add_edge("output_formatter", "finalize_turn_state")
    workflow.add_edge("finalize_turn_state", END)

    logger.info("Compiling AI Sales Agent Graph...")
    try:
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        logger.info("AI Sales Agent Graph compiled successfully.")
        return compiled_graph
    except Exception as e:
        logger.exception(f"Failed to compile the graph: {e}")
        raise
