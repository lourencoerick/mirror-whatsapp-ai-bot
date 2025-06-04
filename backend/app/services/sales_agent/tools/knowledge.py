from typing import List, Optional, Any
from typing_extensions import Annotated
from loguru import logger

try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.error("KnowledgeRetriever: Embedding utils (get_embedding) not found.")

    async def get_embedding(*args, **kwargs):
        return None  # Fallback


try:
    from app.services.repository.knowledge_chunk import (
        search_similar_chunks,
        check_knowledge_chunks_exist_for_account,
    )
    from app.models.knowledge_chunk import KnowledgeChunk

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


from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import InjectedState


from ..agent_state import AgentState

RAG_CHUNK_LIMIT_DEFAULT = 3
RAG_SIMILARITY_THRESHOLD_DEFAULT = 0.5


@tool
async def query_knowledge_base(
    user_query: str,
    state: Annotated[AgentState, InjectedState],
    config: RunnableConfig,
) -> str:
    """Searches the company's knowledge base to answer user questions or find specific information.

    Use this tool when you need to find information that is likely documented
    by the company you represent. This includes details about products/services
    not covered in your initial summary, specific company policies (e.g., refund policy,
    terms of service), operational details (e.g., detailed shipping procedures if not
    in your general knowledge), troubleshooting steps, or answers to frequently asked questions (FAQs).

    To use this tool effectively, provide a clear and specific `user_query` that
    represents the information you are trying to find. For example, instead of
    just "refunds", ask "What is the company's refund policy for digital products?".

    The tool will search documents and data specifically uploaded for this company.
    The retrieved information will be returned as text chunks, which you should then
    synthesize into a natural, conversational answer for the user. Do not simply
    output the raw chunks.

    Args:
        user_query (str):
            The specific question or topic you want to find information about in the
            company's knowledge base. This should be a well-phrased query reflecting
            the user's need or your information gap. Must be non-empty.
        state (AgentState):
            (Injected by the system) The current agent state. This tool uses the
            `account_id` from the state to access the correct knowledge base.
            You do not need to provide this argument explicitly.
        config (RunnableConfig):
            (Injected by the system) The runnable configuration. This tool uses
            `db_session_factory`, `rag_chunk_limit`, and `rag_similarity_threshold`
            from this config. You do not need to provide this argument explicitly.

    Returns:
        str:
            A string containing relevant information chunks found in the knowledge base,
            prefixed with "Relevant context found:". If no relevant information is
            found, it will return a message like "No specific information found for
            your query '[user_query]'. You might try rephrasing or asking more broadly."
            In case of internal errors (e.g., misconfiguration), it will return an
            error message indicating the issue.
    """
    tool_name = "query_knowledge_base"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(f"[{tool_name}] Received query: '{user_query[:100]}...'")

    account_id = state.account_id
    logger.info(
        f"Printando company profile Bot agent:{state.company_profile.offering_overview}"
    )

    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = config.get(
        "configurable", {}
    ).get("db_session_factory")

    rag_limit = config.get("configurable", {}).get(
        "rag_chunk_limit", RAG_CHUNK_LIMIT_DEFAULT
    )
    rag_threshold = config.get("configurable", {}).get(
        "rag_similarity_threshold", RAG_SIMILARITY_THRESHOLD_DEFAULT
    )

    is_rag_active = state.agent_config.use_rag

    # --- Validações e Dependências ---
    if not is_rag_active:
        logger.warning(f"[{tool_name}] RAG is not active. Skipping retrieval.")
        return (
            f"Atualmente, não tenho informações documentadas específicas para a conta "
            f"'{state.company_profile.company_name if state.company_profile else account_id}'. "
        )
    if not user_query:
        logger.warning(f"[{tool_name}] No query text provided. Skipping retrieval.")
        return "Por favor, forneça uma pergunta para buscar na base de conhecimento."
    if not account_id:
        logger.error(f"[{tool_name}] Missing account_id. Cannot perform RAG.")
        return "Erro interno: Informação da conta ausente para buscar conhecimento."
    if not db_session_factory or not SQLALCHEMY_AVAILABLE:
        logger.error(
            f"[{tool_name}] Missing or invalid db_session_factory. Cannot perform RAG."
        )
        return "Erro interno: Configuração do banco de dados ausente para buscar conhecimento."
    if not EMBEDDING_AVAILABLE:
        logger.error(f"[{tool_name}] Embedding function unavailable.")
        return "Erro interno: Funcionalidade de busca indisponível no momento (embeddings)."
    if not CHUNK_REPO_AVAILABLE:
        logger.error(f"[{tool_name}] Chunk repository unavailable.")
        return "Erro interno: Funcionalidade de busca indisponível no momento (repositório)."

    try:
        async with db_session_factory() as db:
            knowledge_exists = await check_knowledge_chunks_exist_for_account(
                db=db, account_id=account_id
            )

        if not knowledge_exists:
            logger.info(
                f"[{tool_name}] No knowledge base content found for account_id: {account_id}. Skipping search."
            )
            return (
                f"Atualmente, não tenho informações documentadas específicas para a conta "
                f"'{state.company_profile.company_name if state.company_profile else account_id}' "
                f"que possam ser pesquisadas em relação a '{user_query}'."
            )
    except Exception as db_check_err:
        logger.error(
            f"[{tool_name}] Error checking for knowledge base existence: {db_check_err}"
        )
        return "Erro interno: Houve um problema ao acessar o status da base de conhecimento."

    # --- Executar RAG ---
    retrieved_context_str: str
    try:
        logger.debug(
            f"[{tool_name}] Generating embedding for query: '{user_query[:50]}...'"
        )
        query_embedding = await get_embedding(user_query)
        if query_embedding is None:
            logger.error(f"[{tool_name}] Failed to generate query embedding.")
            return "Não foi possível processar sua pergunta para a busca no momento."

        logger.debug(
            f"[{tool_name}] Searching for similar chunks (limit={rag_limit}, threshold={rag_threshold})..."
        )
        similar_chunks: List[KnowledgeChunk] = []
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
                f"[{tool_name}] Retrieved {len(similar_chunks)} relevant chunks for query."
            )
            context_parts = [
                "Contexto relevante encontrado em nossa base de conhecimento:"
            ]
            for i, chunk in enumerate(similar_chunks):
                chunk_text = getattr(chunk, "chunk_text", "Conteúdo não disponível.")
                context_parts.append(f"{i+1}. {chunk_text}")
            retrieved_context_str = "\n".join(context_parts)
            logger.debug(
                f"[{tool_name}] Formatted retrieved context: {retrieved_context_str[:300]}..."
            )
        else:
            logger.info(
                f"[{tool_name}] No relevant chunks found meeting threshold {rag_threshold} for query: '{user_query[:50]}...'"
            )
            retrieved_context_str = f"Não encontrei informações específicas em nossa base de conhecimento para '{user_query}'. Você poderia tentar reformular?"

    except Exception as e:
        logger.exception(f"[{tool_name}] Error during knowledge retrieval process: {e}")
        retrieved_context_str = "Ocorreu um erro ao tentar buscar informações em nossa base de conhecimento. Por favor, tente novamente mais tarde."

    return retrieved_context_str
