# backend/app/services/researcher/graph.py

from langgraph.graph import StateGraph, END
from loguru import logger

# Import the state definition and all node functions
from .graph_state import ResearchState
from .graph_nodes import (
    start_research,
    scrape_website,
    perform_search,
    update_company_profile,
    analyze_completeness,
    plan_next_step,
    finish_research,
    # Add error handling node if implemented later
)

# --- Conditional Routing Function ---


def route_after_planning(state: ResearchState) -> str:
    """
    Determines the next node to execute based on the planner's decision.

    Args:
        state: The current graph state.

    Returns:
        The name of the next node ('scrape_website', 'perform_search',
        'finish_research') or 'error'.
    """
    next_action = state.get("next_action")
    error_message = state.get("error_message")

    if error_message:
        logger.warning(f"Routing to finish due to error: {error_message}")
        # In a more complex setup, could route to a specific error handler node
        return "finish_research"  # Go to finish even on error to attempt saving

    logger.info(f"Router received planner action: {next_action}")
    if next_action == "scrape":
        return "scrape_website"
    elif next_action == "search":
        return "perform_search"
    elif next_action == "finish":
        return "finish_research"
    else:
        # Default or unexpected action, treat as error or finish
        logger.error(f"Unexpected next_action '{next_action}' from planner. Finishing.")
        # Update state to reflect this unexpected situation?
        # state["error_message"] = f"Unexpected planner action: {next_action}" # Modifying state here is tricky
        return "finish_research"  # Route to finish as a fallback


# --- Graph Definition ---


def create_research_graph() -> StateGraph:
    """
    Builds and compiles the LangGraph StateGraph for the research agent.
    """
    workflow = StateGraph(ResearchState)

    # Add nodes to the graph
    logger.debug("Adding nodes to the research graph...")
    workflow.add_node("start_research", start_research)
    workflow.add_node("scrape_website", scrape_website)
    workflow.add_node("perform_search", perform_search)
    workflow.add_node("update_company_profile", update_company_profile)
    workflow.add_node("analyze_completeness", analyze_completeness)
    workflow.add_node("plan_next_step", plan_next_step)
    workflow.add_node("finish_research", finish_research)
    # workflow.add_node("handle_error", handle_error_node) # If implementing error node

    # Define the edges (flow)
    logger.debug("Defining edges for the research graph...")

    # Start -> Scrape Initial URL
    workflow.set_entry_point("start_research")
    workflow.add_edge("start_research", "scrape_website")

    # After scraping or searching, update the profile
    workflow.add_edge("scrape_website", "update_company_profile")
    workflow.add_edge("perform_search", "update_company_profile")

    # After updating profile, analyze completeness
    workflow.add_edge("update_company_profile", "analyze_completeness")

    # After analyzing, plan the next step
    workflow.add_edge("analyze_completeness", "plan_next_step")

    # Conditional branching after planning
    workflow.add_conditional_edges(
        "plan_next_step",  # Source node
        route_after_planning,  # Function to determine the route
        {
            # Mapping: Output of router function -> Destination node name
            "scrape_website": "scrape_website",
            "perform_search": "perform_search",
            "finish_research": "finish_research",
            # Add "error": "handle_error_node" if implementing
        },
    )

    # Define the end point (after finishing)
    workflow.add_edge("finish_research", END)

    # Compile the graph
    logger.info("Compiling the research graph...")
    compiled_graph = workflow.compile()
    logger.info("Research graph compiled successfully.")

    return compiled_graph


# --- Optional: Get a singleton instance ---
# research_graph_instance = create_research_graph()
# def get_research_graph():
#     return research_graph_instance
