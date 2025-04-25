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
        return "finish_research"

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
        return "finish_research"


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
    # workflow.add_node("handle_error", handle_error_node) #TODO If implementing error node

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
        "plan_next_step",
        route_after_planning,
        {
            # Mapping: Output of router function -> Destination node name
            "scrape_website": "scrape_website",
            "perform_search": "perform_search",
            "finish_research": "finish_research",
        },
    )

    # Define the end point (after finishing)
    workflow.add_edge("finish_research", END)

    # Compile the graph
    logger.info("Compiling the research graph...")
    compiled_graph = workflow.compile()
    logger.info("Research graph compiled successfully.")

    return compiled_graph
