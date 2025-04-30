# backend/app/services/ai_reply/graph_nodes.py

import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from uuid import UUID
from datetime import datetime, timezone


from .graph_state import (
    ConversationState,
    CompanyProfileSchema,
    BotAgentRead,
)

try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.error("Embedding utils not found.")

    async def get_embedding(*args, **kwargs):
        return None


try:
    from app.services.repository.knowledge_chunk import search_similar_chunks
    from app.models.knowledge_chunk import KnowledgeChunk

    CHUNK_REPO_AVAILABLE = True
except ImportError:
    CHUNK_REPO_AVAILABLE = False
    logger.error("Knowledge repository not found.")

    async def search_similar_chunks(*args, **kwargs) -> List:
        return []

    class KnowledgeChunk:
        pass


try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    AsyncSession = None
    async_sessionmaker = None


try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage, AIMessage

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    logger.error("LangChain core not found.")

    class BaseChatModel:
        pass

    class BaseMessage:
        pass

    class AIMessage:
        content: Optional[str] = None


try:
    from app.services.ai_reply.prompt_builder import build_llm_prompt_messages

    PROMPT_BUILDER_AVAILABLE = True
except ImportError:
    PROMPT_BUILDER_AVAILABLE = False
    logger.error("Prompt builder not found.")

    def build_llm_prompt_messages(*args, **kwargs) -> List[BaseMessage]:
        return []


# --- RAG Config ---
RAG_CHUNK_LIMIT = 3
RAG_SIMILARITY_THRESHOLD = 0.5


async def rag_node(state: ConversationState, config: dict) -> Dict[str, Any]:
    node_name = "rag_node"
    logger.info(f"--- Starting Node: {node_name} ---")
    user_input = state.get("input_message")
    account_id = state.get("account_id")
    db_session_factory: Optional[Any] = config.get("configurable", {}).get(
        "db_session_factory"
    )
    if not user_input:
        logger.warning(f"[{node_name}] No input message. Skipping RAG.")
        return {"retrieved_context": None}
    if (
        not account_id
        or not db_session_factory
        or not EMBEDDING_AVAILABLE
        or not CHUNK_REPO_AVAILABLE
    ):
        logger.error(f"[{node_name}] Missing dependencies. Cannot perform RAG.")
        return {"error": "RAG failed: Missing dependencies.", "retrieved_context": None}
    retrieved_context: Optional[str] = None
    try:
        logger.debug(
            f"[{node_name}] Generating embedding for input: '{user_input[:50]}...'"
        )
        query_embedding = await get_embedding(user_input)
        if query_embedding is None:
            raise ValueError("Failed to generate query embedding.")
        logger.debug(f"[{node_name}] Searching for similar chunks...")
        similar_chunks: List[KnowledgeChunk] = []
        async with db_session_factory() as db:
            similar_chunks = await search_similar_chunks(
                db=db,
                account_id=account_id,
                query_embedding=query_embedding,
                limit=RAG_CHUNK_LIMIT,
                similarity_threshold=RAG_SIMILARITY_THRESHOLD,
            )
        if similar_chunks:
            logger.info(
                f"[{node_name}] Retrieved {len(similar_chunks)} relevant chunks."
            )
            context_parts = [
                "Retrieved Knowledge Snippets (use this information to answer):"
            ]
            for i, chunk in enumerate(similar_chunks):
                source_info = (
                    chunk.metadata_.get("original_source", "Unknown source")
                    if chunk.metadata_
                    else "Unknown source"
                )
                page_info = (
                    f"(Page: {chunk.metadata_.get('page_number')})"
                    if chunk.metadata_ and "page_number" in chunk.metadata_
                    else ""
                )
                context_parts.append(
                    f"{i+1}. [Source: {source_info} {page_info}]:\n{chunk.chunk_text}\n"
                )
            retrieved_context = "\n".join(context_parts)
            logger.debug(
                f"[{node_name}] Formatted retrieved context: {retrieved_context[:200]}..."
            )
        else:
            logger.info(f"[{node_name}] No relevant chunks found.")
    except Exception as e:
        logger.exception(f"[{node_name}] Error during RAG process: {e}")
    return {"retrieved_context": retrieved_context}


async def generate_response_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates the AI's response based on the conversation history,
    profile, agent config, and retrieved RAG context.

    Args:
        state: The current conversation state. Requires 'messages', 'company_profile',
               'agent_config', 'retrieved_context'.
        config: The graph configuration. Requires 'llm_primary_instance'.

    Returns:
        A dictionary containing the 'generation' (the AI's response text)
        and potentially updates 'messages' via the add_messages reducer.
    """
    node_name = "generate_response_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    profile = state.get("company_profile")
    agent_config = state.get("agent_config")
    retrieved_context = state.get("retrieved_context")
    llm_primary_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    if not messages:
        logger.error(
            f"[{node_name}] Message history is empty. Cannot generate response."
        )
        return {"error": "Generation failed: Empty message history."}
    if not profile or not isinstance(profile, CompanyProfileSchema):
        logger.error(
            f"[{node_name}] Invalid or missing Company Profile. Cannot generate response."
        )
        return {"error": "Generation failed: Invalid company profile."}
    if not llm_primary_instance:
        logger.error(f"[{node_name}] LLM instance not found in config.")
        return {"error": "Generation failed: LLM unavailable."}
    if not PROMPT_BUILDER_AVAILABLE:
        logger.error(f"[{node_name}] Prompt builder unavailable.")
        return {"error": "Generation failed: Prompt builder unavailable."}

    # --- Build Prompt ---
    try:
        current_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        prompt_messages = build_llm_prompt_messages(
            profile=profile,
            chat_history_lc=messages,
            current_datetime=current_time_str,
            retrieved_context=retrieved_context,
        )
        if not prompt_messages:
            raise ValueError("Prompt builder returned empty messages.")
        logger.debug(f"[{node_name}] Prompt messages built successfully.")
        logger.trace(f"System Prompt: {prompt_messages[0].content}")

    except Exception as e:
        logger.exception(f"[{node_name}] Error building prompt messages: {e}")
        return {"error": f"Prompt building failed: {e}"}

    # --- Chamar LLM ---
    try:
        logger.debug(f"[{node_name}] Invoking LLM...")
        ai_response: BaseMessage = await llm_primary_instance.ainvoke(prompt_messages)

        if not isinstance(ai_response, AIMessage) or not ai_response.content:
            logger.error(
                f"[{node_name}] LLM returned invalid response type or empty content: {ai_response}"
            )
            raise ValueError("LLM response invalid or empty.")

        generated_text = ai_response.content
        logger.info(
            f"[{node_name}] LLM generated response: '{generated_text[:100]}...'"
        )

        return {
            "generation": generated_text,
            "messages": [ai_response],
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error invoking LLM: {e}")
        return {"error": f"LLM invocation failed: {e}"}
