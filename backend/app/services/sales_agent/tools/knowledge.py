from langchain_core.tools import tool
from typing_extensions import Annotated
from typing import Dict, List, Optional, Any
from loguru import logger


from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import InjectedState  # Para anotar o parâmetro state
from ..agent_state import AgentState  # Ajuste o caminho

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


# --- Constantes (podem vir da configuração do agente ou do perfil da empresa) ---
RAG_CHUNK_LIMIT_DEFAULT = 3
RAG_SIMILARITY_THRESHOLD_DEFAULT = 0.5


@tool
async def query_knowledge_base(
    user_query: str,
    state: Annotated[AgentState, InjectedState],
    config: RunnableConfig,
) -> str:
    """
    Ferramenta para busca RAG (Retrieval-Augmented Generation) em uma base de conhecimento por conta de usuário.

    Descrição:
        Gera um embedding a partir de uma consulta de usuário (user_query), encontra trechos semelhantes
        na base de conhecimento vinculada ao “account_id” obtido do estado do agente (state) e retorna
        esses trechos formatados. Se não houver correspondência ou ocorrer algum erro, devolve mensagens
        de falha apropriadas.

    Argumentos:
        user_query (str):
            Pergunta ou texto fornecido pelo usuário. Deve ser não vazio. Será convertido em embedding
            para buscar similaridade.
        state (AgentState):
            Estado injetado pelo agente. Deve conter a chave “account_id” (ID da conta) usada para filtrar
            a pesquisa na base de conhecimento.
        config (RunnableConfig):
            Configuração executável. Espera-se que “config.configurable” inclua:
            - db_session_factory: async_sessionmaker[AsyncSession] do SQLAlchemy para abrir sessões de BD.
            - rag_chunk_limit (int, opcional): número máximo de chunks a recuperar (padrão: RAG_CHUNK_LIMIT_DEFAULT).
            - rag_similarity_threshold (float, opcional): limiar de similaridade (padrão: RAG_SIMILARITY_THRESHOLD_DEFAULT).

    Retorno:
        str:
            - Se user_query for vazio: mensagem solicitando consulta válida.
            - Se account_id ausente: mensagem de erro interno indicando falta de informação da conta.
            - Se db_session_factory não estiver configurado ou dependências (embeddings, repositório) indisponíveis:
              mensagem de erro interno apropriada.
            - Se chunks relevantes forem encontrados: string contendo “Contexto relevante encontrado...” seguida
              de lista numerada dos textos dos chunks.
            - Se nenhum chunk satisfizer o limiar: mensagem indicando que nada foi encontrado e sugerindo reformular.
            - Em caso de exceção: mensagem genérica de erro ao buscar informações.
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

    # --- Validações e Dependências ---
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
        async with db_session_factory() as db:  # type: ignore
            similar_chunks = await search_similar_chunks(
                db=db,  # type: ignore
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
