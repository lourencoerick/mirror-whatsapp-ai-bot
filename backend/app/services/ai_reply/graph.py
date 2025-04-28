# backend/app/services/ai_reply/graph.py

from langgraph.graph import StateGraph, END
from loguru import logger

try:
    from .graph_state import ConversationState
    from .graph_nodes import rag_node, generate_response_node

    NODES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import ConversationState or nodes: {e}")
    NODES_AVAILABLE = False

    from typing import TypedDict, List, Any, Optional

    class ConversationState(TypedDict):
        pass

    async def rag_node(state: ConversationState, config: dict) -> dict:
        return {}

    async def generate_response_node(state: ConversationState, config: dict) -> dict:
        return {}


def create_reply_graph() -> StateGraph:
    """
    Builds and compiles the basic LangGraph StateGraph for generating AI replies
    using RAG.
    """
    if not NODES_AVAILABLE:
        raise RuntimeError(
            "Cannot create reply graph: Required state or nodes are missing."
        )

    workflow = StateGraph(ConversationState)

    logger.debug("Adding nodes to the reply graph...")
    workflow.add_node("retrieve_knowledge", rag_node)
    workflow.add_node("generate_response", generate_response_node)

    # Entry point
    workflow.set_entry_point("retrieve_knowledge")

    # Edges
    logger.debug("Defining edges for the reply graph...")
    workflow.add_edge("retrieve_knowledge", "generate_response")
    workflow.add_edge("generate_response", END)

    # Graph
    logger.info("Compiling the reply graph...")
    compiled_graph = workflow.compile()
    logger.info("Reply graph compiled successfully.")

    return compiled_graph
