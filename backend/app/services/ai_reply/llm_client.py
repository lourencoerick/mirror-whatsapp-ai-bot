# backend/app/services/ai_reply/llm_client.py

import os
from typing import List, Optional

# LangChain components
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.exceptions import (
    OutputParserException,
)

# Import other potential exceptions like AuthenticationError, RateLimitError if needed
# from openai import AuthenticationError, RateLimitError # If using openai directly or if langchain exposes them

# Import Loguru's logger
from loguru import logger

# Import settings if using Pydantic-settings for API keys, otherwise rely on env vars
# from app.core.config import settings # Example if you have a settings module

# --- Configuration ---

# API Key is typically handled by ChatOpenAI reading the OPENAI_API_KEY env var.
# Ensure OPENAI_API_KEY is set in your environment (.env file loaded by dotenv).

# You can centralize model name and other parameters in config later
LLM_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
LLM_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", 500))


# --- LLM Client Initialization ---
# Initialize the client once when the module is loaded.
# This is generally more efficient than creating it on every call.
try:
    # Ensure API key is available before trying to instantiate
    if not os.getenv("OPENAI_API_KEY"):
        logger.critical("OPENAI_API_KEY environment variable not set!")
        # Raise an error or handle appropriately depending on desired startup behavior
        # raise EnvironmentError("OPENAI_API_KEY environment variable not set!")
        chat_model = None  # Set to None if key is missing
    else:
        chat_model = ChatOpenAI(
            model=LLM_MODEL_NAME,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            # Add other parameters like max_retries if needed
            # request_timeout=60, # Example timeout
        )
        logger.info(f"ChatOpenAI client initialized with model: {LLM_MODEL_NAME}")

except Exception as e:
    logger.exception("Failed to initialize ChatOpenAI client!")
    chat_model = None  # Ensure chat_model is None if init fails

# --- Core Function ---


async def generate_llm_response(messages: List[BaseMessage]) -> Optional[str]:
    """
    Generates a response from the configured LLM using the provided messages.

    Args:
        messages: A list of BaseMessage objects (SystemMessage, HumanMessage)
                  representing the conversation history and prompt.

    Returns:
        The content of the AI's response as a string, or None if an error occurs
        during the LLM call or if the client wasn't initialized.
    """
    if not chat_model:
        logger.error(
            "ChatOpenAI client is not available (failed initialization or missing API key)."
        )
        return None

    if not messages:
        logger.warning("generate_llm_response called with empty messages list.")
        return None

    try:
        logger.debug(f"Sending {len(messages)} messages to LLM model {LLM_MODEL_NAME}.")
        logger.trace(f"Messages sent: {messages}")  # Verbose logging

        # Use ainvoke for asynchronous operation
        response: BaseMessage = await chat_model.ainvoke(messages)

        # Extract the content from the response message
        response_content = response.content
        if isinstance(response_content, str):
            logger.debug(
                f"Received response from LLM. Length: {len(response_content)} chars."
            )
            # logger.trace(f"LLM Response content: {response_content}")
            return response_content.strip()
        else:
            # Should typically be a string, but handle unexpected types just in case
            logger.error(
                f"LLM response content was not a string: {type(response_content)}"
            )
            return None

    # Specific LangChain/OpenAI exceptions can be caught here if needed
    # except AuthenticationError as e:
    #    logger.error(f"OpenAI Authentication Error: {e}")
    #    return None
    # except RateLimitError as e:
    #    logger.error(f"OpenAI Rate Limit Error: {e}")
    #    # Consider adding retry logic here or in the worker
    #    return None
    except Exception as e:
        # Catch general exceptions during the API call
        logger.exception(f"An error occurred during the LLM call to {LLM_MODEL_NAME}")
        return None
