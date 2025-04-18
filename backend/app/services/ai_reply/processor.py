# backend/app/services/ai_reply/processor.py

from typing import Optional, List
from uuid import UUID

# Import Loguru's logger
from loguru import logger

# Import necessary components from within the service
from . import profile_loader, prompt_builder, llm_client

# Import schemas for type hinting
from app.api.schemas.company_profile import CompanyProfileSchema
from langchain_core.messages import BaseMessage

# --- Constants ---

# Default fallback message if profile loading fails or no specific fallback is defined
DEFAULT_FALLBACK_MESSAGE = (
    "Sorry, I'm currently unable to process your request. Please try again in a moment."
)

# --- Core Processing Function ---


async def process_message(
    account_id: UUID, message_text: str, conversation_id: str
) -> Optional[str]:
    """
    Orchestrates the process of generating an AI reply for a given message.

    This function coordinates loading the company profile, building the
    appropriate prompt messages for the LLM based on the profile and user
    message, calling the LLM to get a response, and handling potential
    errors or fallbacks.

    Args:
        company_id: The unique identifier for the company whose profile
                    should be used.
        message_text: The text content of the incoming user message.
        conversation_id: The identifier for the conversation thread (currently
                         unused but planned for future context).

    Returns:
        A string containing the generated AI response or a fallback message.
        Returns None only in rare cases where even fallback generation fails,
        though typically a fallback string is always returned on error.
    """
    logger.info(
        f"Starting AI reply processing for account='{account_id}', conversation='{conversation_id}'"
    )

    # 1. Load Company Profile
    # -----------------------
    profile_identifier = str(account_id)
    logger.debug(f"Using profile identifier: {profile_identifier}")

    profile: Optional[CompanyProfileSchema] = profile_loader.load_company_profile(
        profile_identifier
    )
    if not profile:
        logger.error(
            f"Critical failure: Could not load profile for account_id='{account_id}'. Using default fallback."
        )
        # If the profile doesn't load, we can't even get a specific fallback message.
        return DEFAULT_FALLBACK_MESSAGE

    # Determine fallback message early, using profile info if available
    fallback_message = profile.fallback_contact_info or DEFAULT_FALLBACK_MESSAGE
    logger.debug(f"Using fallback message: '{fallback_message}' if needed.")

    # 2. Build Prompt Messages
    # ------------------------
    prompt_messages: List[BaseMessage] = prompt_builder.build_llm_prompt_messages(
        profile, message_text
    )
    if not prompt_messages:
        logger.error(
            f"Failed to build prompt messages for account='{account_id}'. Using fallback."
        )
        # This indicates an issue with the builder or profile data structure.
        return fallback_message

    # 3. Generate Response via LLM
    # ----------------------------
    logger.debug(f"Calling LLM client for account='{account_id}'...")
    ai_response_content: Optional[str] = await llm_client.generate_llm_response(
        prompt_messages
    )

    # 4. Handle LLM Response and Fallback
    # -----------------------------------
    if ai_response_content is None:
        logger.warning(
            f"LLM generation failed or returned None for account='{account_id}'. Using fallback."
        )
        return fallback_message
    elif not ai_response_content.strip():
        # Handle cases where the LLM might return an empty string or just whitespace
        logger.warning(
            f"LLM returned empty or whitespace-only response for account='{account_id}'. Using fallback."
        )
        return fallback_message
    else:
        logger.info(f"Successfully generated AI response for account='{account_id}'.")
        # Return the valid response from the LLM
        return (
            ai_response_content.strip()
        )  # Ensure leading/trailing whitespace is removed
