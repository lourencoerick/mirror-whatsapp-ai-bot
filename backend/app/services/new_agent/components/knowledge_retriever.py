# backend/app/services/ai_reply/new_agent/components/knowledge_retriever.py

from typing import Dict, List, Optional, Any
from loguru import logger

# Importar definições de estado e tipos
from ..state_definition import RichConversationState

# Importar dependências de RAG (Embeddings, Repositório)
try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.error("KnowledgeRetriever: Embedding utils (get_embedding) not found.")

    async def get_embedding(*args, **kwargs):
        return None  # Fallback


try:
    from app.services.repository.knowledge_chunk import search_similar_chunks
    from app.models.knowledge_chunk import KnowledgeChunk  # Para type hint

    CHUNK_REPO_AVAILABLE = True
except ImportError:
    CHUNK_REPO_AVAILABLE = False
    logger.error(
        "KnowledgeRetriever: Chunk repository (search_similar_chunks) not found."
    )

    async def search_similar_chunks(*args, **kwargs) -> List:
        return []  # Fallback

    class KnowledgeChunk:
        pass  # Dummy


try:
    # Para obter a sessão do DB da configuração do grafo
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.warning(
        "KnowledgeRetriever: SQLAlchemy components not found. DB operations will fail."
    )
    AsyncSession = Any  # type: ignore
    async_sessionmaker = Any  # type: ignore


# --- Constantes ---
RAG_CHUNK_LIMIT_DEFAULT = 3
RAG_SIMILARITY_THRESHOLD_DEFAULT = 0.5  # Ajustar conforme necessário


# --- Nó Principal ---
async def knowledge_retriever_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Retrieves relevant knowledge chunks based on the planned agent action.

    This node performs Retrieval-Augmented Generation (RAG). It determines the
    query text based on the 'next_agent_action_command' and 'action_parameters'
    (e.g., the user's question text or the objection text). It then generates
    an embedding for the query, searches the vector database for similar
    knowledge chunks associated with the account, and formats the retrieved
    chunks into a context string.

    Args:
        state: The current conversation state dictionary. Expected keys:
               'account_id', 'next_agent_action_command', 'action_parameters'.
        config: The graph configuration dictionary. Expected keys:
                'configurable': {
                    'db_session_factory': async_sessionmaker[AsyncSession],
                    'rag_chunk_limit': Optional[int],
                    'rag_similarity_threshold': Optional[float]
                }

    Returns:
        A dictionary containing the state update:
            - 'retrieved_knowledge_for_next_action': A formatted string
              containing the retrieved context, or a message indicating no
              relevant information was found or an error occurred.
            - 'last_processing_error': An error message if a critical dependency
              (like DB session factory or embedding function) is missing,
              otherwise None.
    """
    node_name = "knowledge_retriever_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    # Obter informações do estado e configuração
    account_id = state.get("account_id")
    action_params = state.get("action_parameters", {})
    # A query pode vir de diferentes parâmetros dependendo da ação planejada
    query_text: Optional[str] = None
    action_command = state.get(
        "next_agent_action_command"
    )  # Para saber por que estamos buscando

    if action_command == "ANSWER_DIRECT_QUESTION":
        query_text = action_params.get("question_to_answer_text")
        log_query_text = (
            query_text[:50] + "..."
            if query_text and len(query_text) > 50
            else query_text
        )
        logger.info(
            f"[{node_name}] Retrieving knowledge to answer question: '{log_query_text}...'"
        )
    elif action_command == "GENERATE_REBUTTAL":
        query_text = action_params.get("objection_text_to_address")
        # Poderíamos refinar a query para RAG aqui
        query_text = (
            f"Como responder à objeção do cliente sobre: {query_text}"
            if query_text
            else None
        )
        logger.info(
            f"[{node_name}] Retrieving knowledge to address objection: '{query_text[:50]}...'"
        )
    # Adicionar outros casos se outras ações precisarem de RAG
    # elif action_command == "SOME_OTHER_ACTION":
    #     query_text = action_params.get("relevant_topic")

    # Obter dependências da configuração
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = config.get(
        "configurable", {}
    ).get("db_session_factory")
    # Poderíamos também passar limites/thresholds pela config se quisermos torná-los dinâmicos
    rag_limit = config.get("configurable", {}).get(
        "rag_chunk_limit", RAG_CHUNK_LIMIT_DEFAULT
    )
    rag_threshold = config.get("configurable", {}).get(
        "rag_similarity_threshold", RAG_SIMILARITY_THRESHOLD_DEFAULT
    )

    # --- Validações e Dependências ---
    error_message: Optional[str] = None
    if not query_text:
        logger.warning(
            f"[{node_name}] No query text determined for action '{action_command}'. Skipping retrieval."
        )
        return {"retrieved_knowledge_for_next_action": None}
    if not account_id:
        error_message = "Missing account_id in state."
    elif not db_session_factory or not SQLALCHEMY_AVAILABLE:
        error_message = "Missing or invalid db_session_factory in config."
    elif not EMBEDDING_AVAILABLE:
        error_message = "Embedding function unavailable."
    elif not CHUNK_REPO_AVAILABLE:
        error_message = "Chunk repository unavailable."

    if error_message:
        logger.error(f"[{node_name}] Cannot perform RAG: {error_message}")
        return {
            "retrieved_knowledge_for_next_action": None,
            "last_processing_error": f"Knowledge retrieval failed: {error_message}",
        }

    # --- Executar RAG ---
    retrieved_context: Optional[str] = None
    try:
        logger.debug(
            f"[{node_name}] Generating embedding for query: '{query_text[:50]}...'"
        )
        query_embedding = await get_embedding(query_text)
        if query_embedding is None:
            raise ValueError("Failed to generate query embedding.")

        logger.debug(
            f"[{node_name}] Searching for similar chunks (limit={rag_limit}, threshold={rag_threshold})..."
        )
        similar_chunks: List[KnowledgeChunk] = []
        # Usar a factory para criar uma sessão async
        async with db_session_factory() as db:
            similar_chunks = await search_similar_chunks(
                db=db,
                account_id=account_id,
                query_embedding=query_embedding,
                limit=rag_limit,
                similarity_threshold=rag_threshold,
            )

        if similar_chunks:
            logger.info(
                f"[{node_name}] Retrieved {len(similar_chunks)} relevant chunks for query."
            )
            # Formatar o contexto para o LLM
            context_parts = ["Contexto Relevante Encontrado:"]
            for i, chunk in enumerate(similar_chunks):
                # Tentar obter metadados úteis
                metadata = getattr(chunk, "metadata_", {}) or {}
                source_info = metadata.get("original_source", "Fonte desconhecida")
                page_info = (
                    f"(Página: {metadata.get('page_number')})"
                    if "page_number" in metadata
                    else ""
                )
                chunk_text = getattr(chunk, "chunk_text", "N/A")
                context_parts.append(
                    f"{i+1}. [Fonte: {source_info} {page_info}]:\n{chunk_text}\n---"
                )
            retrieved_context = "\n".join(context_parts)
            logger.debug(
                f"[{node_name}] Formatted retrieved context: {retrieved_context[:300]}..."
            )  # Logar início do contexto
        else:
            logger.info(
                f"[{node_name}] No relevant chunks found meeting threshold {rag_threshold}."
            )
            retrieved_context = "Nenhuma informação específica encontrada na base de conhecimento para esta consulta."  # Informar ao LLM

    except Exception as e:
        logger.exception(f"[{node_name}] Error during knowledge retrieval process: {e}")
        retrieved_context = "Ocorreu um erro ao tentar buscar informações adicionais."  # Informar ao LLM sobre o erro
        # Definir erro no estado para possível tratamento posterior?
        # return {"retrieved_knowledge_for_next_action": retrieved_context, "last_processing_error": f"RAG failed: {e}"}

    # Retornar o contexto para ser adicionado ao estado
    # O ResponseGenerator usará state.get("retrieved_knowledge_for_next_action")
    return {
        "retrieved_knowledge_for_next_action": retrieved_context,
        "last_processing_error": None,  # Limpar erro anterior se RAG rodou (mesmo que não encontrou chunks)
    }
