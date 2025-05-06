import os
import asyncio
from typing import List, Optional, Union
import numpy as np
from loguru import logger
from app.config import get_settings, Settings

settings: Settings = get_settings()
# --- Configuration ---
OPENAI_API_VERSION = settings.OPENAI_API_VERSION
AZURE_OPENAI_API_KEY = settings.AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT = settings.AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_EMBEDDING_MODEL = settings.AZURE_OPENAI_EMBEDDING_MODEL
EMBEDDING_PROVIDER = settings.EMBEDDING_PROVIDER.lower()
LOCAL_EMBEDDING_MODEL = settings.LOCAL_EMBEDDING_MODEL.lower()

# --- Initialize Models/Clients ---
local_model: Optional["SentenceTransformer"] = None
openai_async_client: Optional["AsyncAzureOpenAI"] = None

if EMBEDDING_PROVIDER == "local":
    try:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading local embedding model: {LOCAL_EMBEDDING_MODEL}")

        local_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
        logger.info("Local embedding model loaded successfully.")
    except ImportError:
        logger.error(
            "sentence-transformers library not found. pip install sentence-transformers"
        )
        local_model = None
    except Exception as e:
        logger.error(f"Failed to load local model '{LOCAL_EMBEDDING_MODEL}': {e}")
        local_model = None

elif EMBEDDING_PROVIDER == "openai":
    try:

        from openai import (
            APIConnectionError,
            RateLimitError,
            APIError,
            AsyncAzureOpenAI,
        )

        logger.info("Initializing AsyncAzureOpenAI client for embeddings...")
        if not AZURE_OPENAI_API_KEY:
            raise EnvironmentError(
                "API key not found. Please set the 'AZURE_OPENAI_API_KEY' environment variable."
            )

        if not AZURE_OPENAI_ENDPOINT:
            raise EnvironmentError(
                "Azure Endpoint not found. Please set the 'AZURE_OPENAI_ENDPOINT' environment variable."
            )

        if not OPENAI_API_VERSION:
            raise EnvironmentError(
                "Openai api version not found. Please set the 'AZURE_OPENAI_ENDPOINT' environment variable."
            )

        # openai_async_client = AsyncAzureOpenAI()
        openai_async_client = AsyncAzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
        )

        logger.info("AsyncAzureOpenAI client initialized.")
    except ImportError as import_error:
        logger.error(
            "openai library not found or version < 1.0. pip install --upgrade openai, {e}"
        )
        openai_async_client = None
    except Exception as e:
        logger.error(f"Failed to initialize AsyncAzureOpenAI client: {e}")
        openai_async_client = None
else:
    logger.error(
        f"Invalid EMBEDDING_PROVIDER: '{EMBEDDING_PROVIDER}'. Choose 'local' or 'openai'."
    )

# --- Core Async Functions ---


async def get_embedding(text: str) -> Optional[np.ndarray]:
    """
    Generates an embedding for a single text string using the configured provider (async).

    Args:
        text: The text to embed.

    Returns:
        A numpy array representing the embedding, or None if an error occurs.
    """
    if EMBEDDING_PROVIDER == "local":
        if local_model:
            try:

                embedding = await asyncio.to_thread(
                    local_model.encode, text, convert_to_numpy=True
                )

                if isinstance(embedding, np.ndarray):
                    return embedding
                else:
                    logger.error(
                        f"Local model encode did not return np.ndarray, got {type(embedding)}"
                    )
                    return None
            except Exception as e:
                logger.exception(f"Error generating local embedding via thread: {e}")
                return None
        else:
            logger.error("Local embedding model not available.")
            return None

    elif EMBEDDING_PROVIDER == "openai":
        if openai_async_client:
            try:

                response = await openai_async_client.embeddings.create(
                    input=[text], model=AZURE_OPENAI_EMBEDDING_MODEL
                )
                return np.array(response.data[0].embedding)
            except (APIConnectionError, RateLimitError, APIError) as api_err:
                logger.error(f"OpenAI API error during embedding: {api_err}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error generating OpenAI embedding: {e}")
                return None
        else:
            logger.error("AsyncAzureOpenAI client not available.")
            return None
    else:
        logger.error("No valid embedding provider configured.")
        return None


async def get_embeddings_batch(texts: List[str]) -> Optional[List[np.ndarray]]:
    """
    Generates embeddings for a batch of texts using the configured provider (async).

    Args:
        texts: A list of text strings to embed.

    Returns:
        A list of numpy arrays (embeddings), or None if a fatal error occurs.
        Returns empty list for empty input.
    """
    if not texts:
        return []

    if EMBEDDING_PROVIDER == "local":
        if local_model:
            try:

                embeddings = await asyncio.to_thread(
                    local_model.encode, texts, convert_to_numpy=True
                )

                if isinstance(embeddings, np.ndarray):
                    return list(embeddings)
                else:
                    logger.error(
                        f"Local model batch encode did not return np.ndarray, got {type(embeddings)}"
                    )
                    return None
            except Exception as e:
                logger.exception(
                    f"Error generating local embeddings batch via thread: {e}"
                )
                return None
        else:
            logger.error("Local embedding model not available.")
            return None

    elif EMBEDDING_PROVIDER == "openai":
        if openai_async_client:
            try:

                response = await openai_async_client.embeddings.create(
                    input=texts, model=AZURE_OPENAI_EMBEDDING_MODEL
                )
                return [np.array(data.embedding) for data in response.data]
            except (APIConnectionError, RateLimitError, APIError) as api_err:
                logger.error(f"OpenAI API error during batch embedding: {api_err}")
                return None
            except Exception as e:
                logger.exception(
                    f"Unexpected error generating OpenAI embeddings batch: {e}"
                )
                return None
        else:
            logger.error("AsyncAzureOpenAI client not available.")
            return None
    else:
        logger.error("No valid embedding provider configured.")
        return None


async def calculate_cosine_similarity(
    embedding1: np.ndarray, embedding2: np.ndarray
) -> float:
    """
    Calculates cosine similarity between two numpy arrays (async wrapper).

    Returns:
        Similarity score [-1.0, 1.0], or -1.0 on error.
    """

    def _sync_calc():
        try:
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            similarity = dot_product / (norm1 * norm2)
            return float(np.clip(similarity, -1.0, 1.0))
        except Exception as e:
            logger.exception(f"Error calculating cosine similarity: {e}")
            return -1.0

    return await asyncio.to_thread(_sync_calc)
