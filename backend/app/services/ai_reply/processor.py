# backend/app/services/ai_reply/processor.py

import os
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from uuid import UUID

# Import necessary components from within the service
from . import profile_loader, prompt_builder, llm_client

# Import schemas and models for type hinting
from app.api.schemas.company_profile import CompanyProfileSchema
from app.models.message import Message
from langchain_core.messages import BaseMessage


from app.services.repository import message as message_repo

# --- Constants ---
DEFAULT_FALLBACK_MESSAGE = (
    "Sorry, I'm currently unable to process your request. Please try again in a moment."
)

AI_HISTORY_LIMIT = int(os.getenv("AI_HISTORY_LIMIT", 50))


# --- Core Processing Function ---


async def process_message(
    db: AsyncSession, account_id: UUID, message_text: str, conversation_id: UUID
) -> Optional[str]:
    """
    Orchestrates the process of generating an AI reply for a given message.

    This function coordinates loading the company profile, building the
    appropriate prompt messages for the LLM based on the profile and user
    message, calling the LLM to get a response, and handling potential
    errors or fallbacks.

    Args:
        db: The SQLAlchemy AsyncSession.
        account_id: The identifier for the company (UUID).
        message_text: The text content of the user's message.
        conversation_id: The identifier for the conversation thread (UUID).

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

    chat_history: List[Message] = []
    try:
        logger.debug(
            f"Fetching last {AI_HISTORY_LIMIT} messages for conversation {conversation_id}"
        )

        chat_history = await message_repo.find_messages_by_conversation(
            db=db,
            conversation_id=conversation_id,
            account_id=account_id,
            limit=AI_HISTORY_LIMIT,
            offset=1,  # Fetch the very latest including the current one if already saved
            # Or use offset=1 if the current message_text is not yet in DB when this runs
        )
        # The list is currently newest-to-oldest. We'll reverse it in the prompt builder helper.
        logger.debug(f"Fetched {len(chat_history)} messages for history.")

    except Exception as history_exc:
        logger.warning(
            f"Failed to fetch chat history for conversation {conversation_id}: {history_exc}. Proceeding without history."
        )
        chat_history = []

    prompt_messages: List[BaseMessage] = prompt_builder.build_llm_prompt_messages(
        profile=profile, message_text=message_text, chat_history=chat_history
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
