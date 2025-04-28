# backend/app/services/ai_reply/graph_nodes.py

from typing import Dict, Any, List, Optional
from loguru import logger
from uuid import UUID

# Importar estado e dependências necessárias
from .graph_state import ConversationState # Importar o estado da conversa
try:
    # Cliente de Embedding
    from app.core.embedding_utils import get_embedding
    EMBEDDING_AVAILABLE = True
except ImportError: EMBEDDING_AVAILABLE = False; logger.error("Embedding utils not found."); async def get_embedding(*args, **kwargs): return None

try:
    # Repositório de Conhecimento
    from app.services.repository.knowledge_repo import search_similar_chunks
    from app.models.knowledge_chunk import KnowledgeChunk # Importar modelo para type hint
    CHUNK_REPO_AVAILABLE = True
except ImportError:
    CHUNK_REPO_AVAILABLE = False; logger.error("Knowledge repository not found.")
    async def search_similar_chunks(*args, **kwargs) -> List: return []
    class KnowledgeChunk: pass # Dummy

# Importar DB Session para type hint (fábrica virá do config)
try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    SQLALCHEMY_AVAILABLE = True
except ImportError: SQLALCHEMY_AVAILABLE = False; AsyncSession = None; async_sessionmaker = None


# --- Configurações RAG ---
RAG_CHUNK_LIMIT = 3 # Quantos chunks recuperar
RAG_SIMILARITY_THRESHOLD = 0.75 # Limiar de similaridade cosseno (0 a 1) - Ajustar conforme testes


# --- Nó: rag_node ---

async def rag_node(state: ConversationState, config: dict) -> Dict[str, Any]:
    """
    Node to perform Retrieval-Augmented Generation (RAG).
    Fetches relevant knowledge chunks based on the user's input message.

    Args:
        state: The current conversation state. Requires 'input_message', 'account_id'.
        config: The graph configuration. Requires 'db_session_factory'.

    Returns:
        A dictionary with the 'retrieved_context' update for the state.
    """
    node_name = "rag_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    # --- Obter dados do estado e config ---
    user_input = state.get("input_message")
    account_id = state.get("account_id")
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = config.get("configurable", {}).get("db_session_factory")

    # --- Validações ---
    if not user_input:
        logger.warning(f"[{node_name}] No input message found in state. Skipping RAG.")
        return {"retrieved_context": None} # Retorna None se não há input
    if not account_id:
        logger.error(f"[{node_name}] Account ID missing from state. Cannot perform RAG.")
        return {"error": "RAG failed: Missing account ID.", "retrieved_context": None}
    if not EMBEDDING_AVAILABLE:
        logger.error(f"[{node_name}] Embedding client unavailable. Cannot perform RAG.")
        return {"error": "RAG failed: Embedding client unavailable.", "retrieved_context": None}
    if not CHUNK_REPO_AVAILABLE:
        logger.error(f"[{node_name}] Knowledge repository unavailable. Cannot perform RAG.")
        return {"error": "RAG failed: Knowledge repository unavailable.", "retrieved_context": None}
    if not db_session_factory:
         logger.error(f"[{node_name}] DB Session Factory unavailable. Cannot perform RAG.")
         return {"error": "RAG failed: DB Session Factory unavailable.", "retrieved_context": None}

    retrieved_context: Optional[str] = None # Inicializa como None

    try:
        # 1. Gerar Embedding da Query (Mensagem do Usuário)
        logger.debug(f"[{node_name}] Generating embedding for input: '{user_input[:50]}...'")
        query_embedding = await get_embedding(user_input)

        if query_embedding is None:
            logger.error(f"[{node_name}] Failed to generate embedding for the input message.")
            # Não definir erro fatal, talvez o LLM consiga responder sem RAG
            return {"retrieved_context": None}

        # 2. Buscar Chunks Similares no Banco
        logger.debug(f"[{node_name}] Searching for similar chunks (limit={RAG_CHUNK_LIMIT}, threshold={RAG_SIMILARITY_THRESHOLD})...")
        similar_chunks: List[KnowledgeChunk] = []
        async with db_session_factory() as db: # Criar sessão para busca
            similar_chunks = await search_similar_chunks(
                db=db,
                account_id=account_id,
                query_embedding=query_embedding,
                limit=RAG_CHUNK_LIMIT,
                similarity_threshold=RAG_SIMILARITY_THRESHOLD
            )

        # 3. Formatar Contexto Recuperado
        if similar_chunks:
            logger.info(f"[{node_name}] Retrieved {len(similar_chunks)} relevant chunks.")
            context_parts = ["Retrieved Knowledge Snippets (use this information to answer):"]
            for i, chunk in enumerate(similar_chunks):
                source_info = chunk.metadata_.get("original_source", "Unknown source") if chunk.metadata_ else "Unknown source"
                page_info = f"(Page: {chunk.metadata_.get('page_number')})" if chunk.metadata_ and 'page_number' in chunk.metadata_ else ""
                context_parts.append(f"{i+1}. [Source: {source_info} {page_info}]:\n{chunk.chunk_text}\n")
            retrieved_context = "\n".join(context_parts)
            logger.debug(f"[{node_name}] Formatted retrieved context: {retrieved_context[:200]}...")
        else:
            logger.info(f"[{node_name}] No relevant chunks found meeting the criteria.")
            retrieved_context = None # Garante que seja None se nada for encontrado

    except Exception as e:
        logger.exception(f"[{node_name}] Error during RAG process: {e}")
        # Não definir erro fatal no estado, apenas logar. O próximo nó lidará com a ausência de contexto.
        retrieved_context = None # Garante None em caso de erro

    # Retorna a atualização para o estado
    return {"retrieved_context": retrieved_context}

# --- Outros Nós (generate_response_node, etc. virão depois) ---