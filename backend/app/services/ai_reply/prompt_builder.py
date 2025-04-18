from typing import List, Dict, Any, Sequence


from app.api.schemas.company_profile import CompanyProfileSchema, OfferingInfo


from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
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

Communication Guidelines:
{communication_guidelines}

{fallback_instructions}

Always adhere to these instructions and guidelines when responding to the user.
"""

HUMAN_MESSAGE_TEMPLATE = "{customer_message}"


# --- Helper Functions (remain the same) ---
def _format_offerings(offerings: List[OfferingInfo]) -> str:
    """Formats the list of offerings into a concise string for the prompt."""
    if not offerings:
        return "No specific offerings listed."
    lines = []
    for offer in offerings:
        features = ", ".join(offer.key_features) if offer.key_features else "N/A"
        price = offer.price_info if offer.price_info else "N/A"
        lines.append(
            f"- {offer.name}: {offer.short_description} (Features: {features}, Price: {price})"
        )
    return "\n".join(lines)


def _format_list_items(items: List[str], prefix: str = "- ") -> str:
    """Formats a list of strings into a newline-separated string."""
    if not items:
        return "N/A"
    return "\n".join([f"{prefix}{item}" for item in items])


# --- Main Function ---


def build_llm_prompt_messages(
    profile: CompanyProfileSchema, message_text: str
) -> List[BaseMessage]:
    """
    Constructs the list of messages for the LLM using ChatPromptTemplate.

    Args:
        profile: The loaded and validated CompanyProfileSchema object.
        message_text: The incoming message text from the user.

    Returns:
        A list of BaseMessage objects (SystemMessage, HumanMessage) ready
        to be passed to a chat model. Returns an empty list on error.
    """
    if not profile:
        logger.error("Cannot build prompt messages with invalid profile.")
        return []

    # Prepare variables for the template (mostly for the system message)
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

        # All variables needed by the combined templates
        all_input_vars = {
            **system_vars,
            "customer_message": message_text,
        }

        # Create the ChatPromptTemplate using from_messages
        chat_template = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_MESSAGE_TEMPLATE), ("human", HUMAN_MESSAGE_TEMPLATE)]
        )

        # Format the template to get the list of messages
        # Using .format_messages() is convenient as it directly returns the list
        formatted_messages = chat_template.format_messages(**all_input_vars)

        logger.debug(f"Generated prompt messages for company {profile.company_name}")
        # logger.trace(f"Messages: {formatted_messages}") # For verbose debugging

        return formatted_messages

    except KeyError as e:
        logger.error(
            f"Missing key when formatting chat prompt for company {profile.company_name}: {e}. Check templates and input variables."
        )
        return []
    except Exception as e:
        logger.exception(
            f"Error formatting chat prompt for company {profile.company_name}"
        )
        return []
