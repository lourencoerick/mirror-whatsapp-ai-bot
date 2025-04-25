# backend/app/services/ai_reply/prompt_builder.py
from typing import List, Dict, Any, Sequence


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

# --- Template Strings  ---
SYSTEM_MESSAGE_TEMPLATE = """
You are an AI Sales Assistant for '{company_name}'.
Your goal is: {ai_objective}.
Communicate in {language} with a {sales_tone} tone.

Company Description: {business_description}
{company_address_info}
{target_audience_info}
{opening_hours_info}

Key Selling Points:
{key_selling_points}

Our Offerings:
{offering_summary}
IMPORTANT: Only offer products or services listed in the 'Our Offerings' section above. Do not mention or suggest items not listed here.

Delivery/Pickup Options:
{delivery_options_info}

Communication Guidelines:
{communication_guidelines}
IMPORTANT: Only provide information explicitly given in your instructions (company profile, offerings, guidelines,) or in the conversation history. Do NOT invent details like addresses, phone numbers, specific opening hours, or prices unless they are provided here.

{fallback_instructions}

Current Date and Time: {current_datetime}. Use this information to answer time-sensitive questions like opening hours.

Use the provided conversation history to understand the context, but respond only to the latest customer message.
Always adhere to these instructions and guidelines when responding to the user.
"""

HUMAN_MESSAGE_TEMPLATE = "{customer_message}"


# --- Helper Functions  ---
def _format_offerings(offerings: List[OfferingInfo]) -> str:
    """Formats the list of offerings, including the link if available."""
    if not offerings:
        return "No specific offerings listed."
    lines = []
    for offer in offerings:
        features = ", ".join(offer.key_features) if offer.key_features else "N/A"
        price = offer.price_info if offer.price_info else "N/A"
        link_info = f", Link: {offer.link}" if offer.link else ""
        lines.append(
            f"- {offer.name}: {offer.short_description} (Features: {features}, Price: {price}{link_info})"
        )
    return "\n".join(lines)


def _format_list_items(items: List[str], prefix: str = "- ") -> str:
    if not items:
        return "N/A"
    return "\\n".join([f"{prefix}{item}" for item in items])


def _format_history_messages(history: List[Message]) -> List[BaseMessage]:
    formatted_history: List[BaseMessage] = []
    for msg in reversed(history):
        if msg.direction == "in":
            if msg.content:
                formatted_history.append(HumanMessage(content=msg.content))
        elif msg.direction == "out":
            if msg.content:
                formatted_history.append(AIMessage(content=msg.content))
    logger.debug(f"Formatted {len(formatted_history)} messages for chat history.")
    return formatted_history


# --- Main Function  ---
def build_llm_prompt_messages(
    profile: CompanyProfileSchema,
    message_text: str,
    chat_history: List[Message],
    current_datetime: str,
) -> List[BaseMessage]:
    """
    Constructs the list of messages for the LLM using ChatPromptTemplate,
    including conversation history, address, and delivery options.

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
            "company_address_info": (
                f"Company Address: {profile.address}"
                if profile.address
                else "Company address not specified."
            ),
            "opening_hours_info": (
                f"Opening Hours: {profile.opening_hours}"
                if profile.opening_hours
                else "Opening hours not specified."
            ),
            "current_datetime": current_datetime,
            "delivery_options_info": (
                _format_list_items(profile.delivery_options)
                if profile.delivery_options
                else "Delivery/pickup options not specified."
            ),
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
        logger.info(f"prompt variables: {system_vars}")

        formatted_history = _format_history_messages(chat_history)

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

        expected_vars = list(system_vars.keys()) + ["chat_history", "customer_message"]

        # Simple check (can be more robust)
        missing_keys = [key for key in expected_vars if key not in all_input_vars]
        if missing_keys:
            logger.error(f"Missing keys required by prompt template: {missing_keys}")
            raise KeyError(f"Missing keys: {missing_keys}")

        # Format the template to get the list of messages
        formatted_messages = chat_template.format_messages(**all_input_vars)

        logger.debug(
            f"Generated prompt messages for account {profile.company_name} including history, address, delivery."
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
