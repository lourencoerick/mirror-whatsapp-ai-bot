# backend/app/services/ai_reply/graph.py

from langgraph.graph import StateGraph, END
from loguru import logger

# Importar o estado e os nós definidos
try:
    from .graph_state import ConversationState
    from .graph_nodes import rag_node, generate_response_node

    NODES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import ConversationState or nodes: {e}")
    NODES_AVAILABLE = False
    # Definir dummies se necessário para permitir a compilação básica
    from typing import TypedDict, List, Any, Optional

    class ConversationState(TypedDict):
        pass

    async def rag_node(state: ConversationState, config: dict) -> dict:
        return {}

    async def generate_response_node(state: ConversationState, config: dict) -> dict:
        return {}


# --- Definição do Grafo de Resposta ---


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

    # 1. Adicionar os Nós
    logger.debug("Adding nodes to the reply graph...")
    workflow.add_node("retrieve_knowledge", rag_node)  # Nó RAG
    workflow.add_node("generate_response", generate_response_node)  # Nó de Geração

    # 2. Definir o Ponto de Entrada
    # O fluxo começa com a recuperação de conhecimento (RAG)
    workflow.set_entry_point("retrieve_knowledge")

    # 3. Definir as Arestas (Edges)
    logger.debug("Defining edges for the reply graph...")
    # Após recuperar conhecimento, gerar a resposta
    workflow.add_edge("retrieve_knowledge", "generate_response")

    # Após gerar a resposta, o fluxo termina (por enquanto)
    workflow.add_edge("generate_response", END)

    # 4. Compilar o Grafo
    logger.info("Compiling the reply graph...")
    compiled_graph = workflow.compile()
    logger.info("Reply graph compiled successfully.")

    return compiled_graph


# --- Opcional: Instância Singleton ---
# Pode ser útil para evitar recompilar a cada chamada se a definição for estática
# reply_graph_instance = create_reply_graph()
# def get_reply_graph():
#     # Adicionar verificação se a instância foi criada com sucesso
#     if not reply_graph_instance:
#          raise RuntimeError("Reply graph instance not available.")
#     return reply_graph_instance
