# backend/app/core/embedding_utils.py

import os
from typing import List, Optional, Union

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer, util

from openai import OpenAI, APIConnectionError, RateLimitError, APIError

# --- Configuration ---
# Choose 'local' or 'openai'. Default to 'local'.
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
# Model for local embeddings
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
# Model for OpenAI embeddings (ensure compatibility with your API key/plan)
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# --- Initialize Models/Clients ---
local_model: Optional[SentenceTransformer] = None
openai_client: Optional[OpenAI] = None

if EMBEDDING_PROVIDER == "local":
    try:
        logger.info(f"Loading local embedding model: {LOCAL_EMBEDDING_MODEL}")
        local_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
        logger.info("Local embedding model loaded successfully.")
    except Exception as e:
        logger.error(
            f"Failed to load local SentenceTransformer model '{LOCAL_EMBEDDING_MODEL}': {e}"
        )
        logger.warning("Embeddings will not work in 'local' mode.")
elif EMBEDDING_PROVIDER == "openai":
    try:
        logger.info("Initializing OpenAI client for embeddings...")
        # Assumes OPENAI_API_KEY environment variable is set
        openai_client = OpenAI()
        # Optional: Test connection with a dummy call if needed, but usually handled on first real call
        logger.info("OpenAI client initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        logger.warning("Embeddings will not work in 'openai' mode.")
else:
    logger.error(
        f"Invalid EMBEDDING_PROVIDER: '{EMBEDDING_PROVIDER}'. Choose 'local' or 'openai'."
    )

# --- Core Functions ---


def get_embedding(text: str) -> Optional[np.ndarray]:
    """
    Generates an embedding for a single text string using the configured provider.

    Args:
        text: The text to embed.

    Returns:
        A numpy array representing the embedding, or None if an error occurs.
    """
    if EMBEDDING_PROVIDER == "local":
        if local_model:
            try:
                # Ensure output is numpy array
                embedding = local_model.encode(text, convert_to_numpy=True)
                return embedding
            except Exception as e:
                logger.exception(f"Error generating local embedding: {e}")
                return None
        else:
            logger.error("Local embedding model not available.")
            return None
    elif EMBEDDING_PROVIDER == "openai":
        if openai_client:
            try:
                response = openai_client.embeddings.create(
                    input=[text], model=OPENAI_EMBEDDING_MODEL
                )
                # Return as numpy array
                return np.array(response.data[0].embedding)
            except (APIConnectionError, RateLimitError, APIError) as api_err:
                logger.error(f"OpenAI API error during embedding: {api_err}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error generating OpenAI embedding: {e}")
                return None
        else:
            logger.error("OpenAI client not available.")
            return None
    else:
        logger.error("No valid embedding provider configured.")
        return None


def get_embeddings_batch(texts: List[str]) -> Optional[List[np.ndarray]]:
    """
    Generates embeddings for a batch of text strings using the configured provider.

    Args:
        texts: A list of text strings to embed.

    Returns:
        A list of numpy arrays representing the embeddings, or None if an error occurs.
        Returns an empty list if the input list is empty.
    """
    if not texts:
        return []

    if EMBEDDING_PROVIDER == "local":
        if local_model:
            try:
                embeddings = local_model.encode(texts, convert_to_numpy=True)
                return list(embeddings)  # Return as list of arrays
            except Exception as e:
                logger.exception(f"Error generating local embeddings batch: {e}")
                return None
        else:
            logger.error("Local embedding model not available.")
            return None
    elif EMBEDDING_PROVIDER == "openai":
        if openai_client:
            try:
                response = openai_client.embeddings.create(
                    input=texts, model=OPENAI_EMBEDDING_MODEL
                )
                # Return list of numpy arrays
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
            logger.error("OpenAI client not available.")
            return None
    else:
        logger.error("No valid embedding provider configured.")
        return None


def calculate_cosine_similarity(
    embedding1: np.ndarray, embedding2: np.ndarray
) -> float:
    """
    Calculates the cosine similarity between two embedding vectors (numpy arrays).

    Args:
        embedding1: The first embedding vector.
        embedding2: The second embedding vector.

    Returns:
        The cosine similarity score (between -1.0 and 1.0), or -1.0 on error.
    """
    try:
        # Using sentence-transformers util for potentially better handling of tensors/numpy
        # Ensure inputs are tensors if using pytorch_cos_sim
        # sim = util.pytorch_cos_sim(embedding1, embedding2)[0][0].item()

        # Or using numpy directly:
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        if norm1 == 0 or norm2 == 0:  # Avoid division by zero
            return 0.0
        similarity = dot_product / (norm1 * norm2)
        # Clamp similarity to [-1, 1] due to potential floating point inaccuracies
        return float(np.clip(similarity, -1.0, 1.0))
    except Exception as e:
        logger.exception(f"Error calculating cosine similarity: {e}")
        return -1.0  # Return a value indicating error or low similarity
