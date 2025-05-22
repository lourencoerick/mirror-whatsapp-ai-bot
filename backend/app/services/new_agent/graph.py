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
from .components.offer_selector import select_offer_node
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
    - 'select_offer_node': If the action is 'SELECT_AVAILABLE_OFFER'.
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

    if action_command == "SELECT_AVAILABLE_OFFER":
        logger.info(
            "[Router: route_after_planning_or_proactive_step] Action is SELECT_AVAILABLE_OFFER. Routing to select_offer_node."
        )
        return "select_offer_node"

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


def route_after_offer_selection(
    state: RichConversationState,
) -> Literal["planner", "knowledge_retriever", "response_generator", "__end__"]:
    """
    Determines the next node after the offer_selector has run.
    - If an offer is selected, it proceeds to generate a presentation (possibly via RAG).
    - If no offer is selected or clarification is needed, it routes back to the planner.
    - If an error occurred in offer selection, it also routes back to planner.
    """
    offer_selection_result = state.get("offer_selection_result")
    processing_error = state.get("last_processing_error")

    if processing_error and "Offer selection" in processing_error:
        logger.warning(
            f"[Router: route_after_offer_selection] Error during offer selection: {processing_error}. Routing to planner."
        )
        # The planner will need to see this error and decide (e.g., try again, ask generic q)
        # For now, we clear next_agent_action_command so planner doesn't try to use a failed selection
        state["next_agent_action_command"] = None
        return "planner"

    if not offer_selection_result:
        logger.warning(
            "[Router: route_after_offer_selection] No offer_selection_result found. Routing to planner."
        )
        state["next_agent_action_command"] = None
        return "planner"

    # Assuming OfferSelectionOutput schema is used for offer_selection_result (it's a dict here)
    selected_offer_details = offer_selection_result.get("selected_offer")
    no_suitable_offer = offer_selection_result.get("no_suitable_offer_found", False)
    clarifying_questions_needed = bool(
        offer_selection_result.get("clarifying_questions_to_ask")
    )

    if (
        selected_offer_details
        and isinstance(selected_offer_details, dict)
        and selected_offer_details.get("product_name")
    ):
        logger.info(
            f"[Router: route_after_offer_selection] Offer '{selected_offer_details['product_name']}' selected. Proceeding to present."
        )
        # The planner should have set the next action to PRESENT_SOLUTION_OFFER
        # and populated action_parameters based on selected_offer_details.
        # We now decide if PRESENT_SOLUTION_OFFER needs RAG.
        # For now, let's assume PRESENT_SOLUTION_OFFER always goes to knowledge_retriever
        # to fetch full product details or related info, even if LLM selected it.
        # The planner will set next_agent_action_command to "PRESENT_SOLUTION_OFFER"
        # if an offer was selected by select_offer_node.
        # So, we re-evaluate based on this *new* action_command.

        # The planner will update next_agent_action_command based on offer_selection_result.
        # Here, we assume the planner has already done that if an offer was selected.
        # The next action should be PRESENT_SOLUTION_OFFER.
        current_planned_action = state.get("next_agent_action_command")
        if current_planned_action == "PRESENT_SOLUTION_OFFER":
            logger.info(
                f"[Router: route_after_offer_selection] Action is PRESENT_SOLUTION_OFFER. Routing to knowledge_retriever."
            )
            return "knowledge_retriever"  # PRESENT_SOLUTION_OFFER uses RAG
        else:
            logger.warning(
                f"[Router: route_after_offer_selection] Offer selected, but next action is not PRESENT_SOLUTION_OFFER (it's {current_planned_action}). Routing to planner."
            )
            return "planner"

    elif no_suitable_offer or clarifying_questions_needed:
        logger.info(
            "[Router: route_after_offer_selection] No suitable offer found or clarification needed. Routing to planner for replan."
        )
        # Planner will see offer_selection_result and decide next step (e.g., ask clarification, inform no offer)
        # Clear the current action command so planner starts fresh based on this new info.
        state["next_agent_action_command"] = None
        return "planner"
    else:
        logger.warning(
            "[Router: route_after_offer_selection] Offer selection result in unexpected state. Routing to planner."
        )
        state["next_agent_action_command"] = None
        return "planner"


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
        "select_offer_node": select_offer_node,
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
            "select_offer_node": "select_offer_node",
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
            "select_offer_node": "select_offer_node",
            "knowledge_retriever": "knowledge_retriever",
            "response_generator": "response_generator",
            END: END,
        },
    )
    logger.debug(
        "Added conditional edges from 'proactive_step_decider' using main route_action"
    )

    workflow.add_conditional_edges(
        "select_offer_node",
        route_after_offer_selection,
        {
            "planner": "planner",  # If no offer / error / clarification needed
            "knowledge_retriever": "knowledge_retriever",  # If offer selected and PRESENT_SOLUTION_OFFER needs RAG
            "response_generator": "response_generator",  # If offer selected and PRESENT_SOLUTION_OFFER does not need RAG (less likely for now)
            END: END,  # Should not happen directly from here, planner would end.
        },
    )
    logger.debug("Added conditional edges from 'select_offer_node'")

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
