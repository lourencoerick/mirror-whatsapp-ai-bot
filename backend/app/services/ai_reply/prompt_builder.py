# backend/app/services/ai_reply/prompt_builder.py

from typing import List, Dict, Any, Sequence

# Schemas and Models
from app.api.schemas.company_profile import CompanyProfileSchema, OfferingInfo
from app.models.message import Message

# LangChain components
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
)


from loguru import logger

# --- Template Strings ---
SYSTEM_MESSAGE_TEMPLATE = """
You are an AI Sales Assistant for '{company_name}'.
Your goal is: {ai_objective}.
Communicate in {language} with a {sales_tone} tone.

Company Description: {business_description}
{target_audience_info}

Key Selling Points:
{key_selling_points}

Our Offerings:
{offering_summary}
IMPORTANT: Only offer products or services listed in the 'Our Offerings' section above. Do not mention or suggest items not listed here.

Communication Guidelines:
{communication_guidelines}

{fallback_instructions}

Use the provided conversation history to understand the context, but respond only to the latest customer message.
Always adhere to these instructions and guidelines when responding to the user.
"""

HUMAN_MESSAGE_TEMPLATE = "{customer_message}"


# --- Helper Functions ---
def _format_offerings(offerings: List[OfferingInfo]) -> str:
    if not offerings:
        return "No specific offerings listed."
    lines = []
    for offer in offerings:
        features = ", ".join(offer.key_features) if offer.key_features else "N/A"
        price = offer.price_info if offer.price_info else "N/A"
        lines.append(
            f"- {offer.name}: {offer.short_description} (Features: {features}, Price: {price})"
        )
    return "\\n".join(lines)


def _format_list_items(items: List[str], prefix: str = "- ") -> str:
    if not items:
        return "N/A"
    return "\\n".join([f"{prefix}{item}" for item in items])


def _format_history_messages(history: List[Message]) -> List[BaseMessage]:
    """Converts database Message objects into LangChain BaseMessage objects."""
    formatted_history: List[BaseMessage] = []
    for msg in reversed(history):
        if msg.direction == "in":
            if msg.content:
                formatted_history.append(HumanMessage(content=msg.content))
        elif msg.direction == "out":
            if msg.content:
                # TODO: How to know if an 'out' message was from AI or Human Agent?
                # Assuming 'out' means AI for now. Might need a 'sender_type' field later.
                formatted_history.append(AIMessage(content=msg.content))
    logger.debug(f"Formatted {len(formatted_history)} messages for chat history.")
    return formatted_history


# --- Main Function ---


def build_llm_prompt_messages(
    profile: CompanyProfileSchema,
    message_text: str,
    chat_history: List[Message],
) -> List[BaseMessage]:
    """
    Constructs the list of messages for the LLM using ChatPromptTemplate,
    including conversation history.

    Args:
        profile: The loaded CompanyProfileSchema object.
        message_text: The current incoming message text from the user.
        chat_history: List of previous Message objects from the database.

    Returns:
        A list of BaseMessage objects ready for the chat model. Empty list on error.
    """
    if not profile:
        logger.error("Cannot build prompt messages with invalid profile.")
        return []

    # Prepare variables for the template
    try:
        system_vars: Dict[str, Any] = {
            "company_name": profile.company_name,
            "ai_objective": profile.ai_objective,
            "language": profile.language,
            "sales_tone": profile.sales_tone,
            "business_description": profile.business_description,
            "target_audience_info": (
                f"Target Audience: {profile.target_audience}"
                if profile.target_audience
                else ""
            ),
            "key_selling_points": _format_list_items(profile.key_selling_points),
            "offering_summary": _format_offerings(profile.offering_overview),
            "communication_guidelines": _format_list_items(
                profile.communication_guidelines
            ),
            "fallback_instructions": (
                f"If you cannot answer the query, direct the user with: '{profile.fallback_contact_info}'"
                if profile.fallback_contact_info
                else "If you cannot answer the query, politely state that you cannot help with that specific request."
            ),
        }

        formatted_history = _format_history_messages(chat_history)

        # All variables needed by the combined templates
        logger.info(f"Chat history Messages: {formatted_history}")
        all_input_vars = {
            **system_vars,
            "chat_history": formatted_history,
            "customer_message": message_text,
        }

        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_MESSAGE_TEMPLATE),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", HUMAN_MESSAGE_TEMPLATE),
            ]
        )

        # Ensure all expected variables are present before formatting
        # Note: 'chat_history' is now an expected variable for the placeholder
        expected_vars = list(system_vars.keys()) + ["chat_history", "customer_message"]
        # Simple check (can be more robust)
        missing_keys = [key for key in expected_vars if key not in all_input_vars]
        if missing_keys:
            logger.error(f"Missing keys required by prompt template: {missing_keys}")
            raise KeyError(f"Missing keys: {missing_keys}")

        # Format the template to get the list of messages
        formatted_messages = chat_template.format_messages(**all_input_vars)

        logger.debug(
            f"Generated prompt messages for account {profile.company_name} including history."
        )
        return formatted_messages

    except KeyError as e:
        logger.error(
            f"Missing key when formatting chat prompt for account {profile.company_name}: {e}. Check templates and input variables."
        )
        return []
    except Exception as e:
        logger.exception(
            f"Error formatting chat prompt for account {profile.company_name}"
        )
        return []
