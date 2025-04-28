# backend/app/services/ai_reply/prompt_builder.py
from typing import List, Dict, Any, Sequence, Optional

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


SYSTEM_MESSAGE_TEMPLATE = """
You are an AI Sales Assistant for '{company_name}'.
Your goal is: {ai_objective}.
Communicate in {language} with a {sales_tone} tone.

**Knowledge Base Context:**
{retrieved_knowledge}
--- End Knowledge Base Context ---

**Company Profile Information:**
Company Description: {business_description}
{company_address_info}
{target_audience_info}
{opening_hours_info}

Key Selling Points:
{key_selling_points}

Our Offerings:
{offering_summary}
IMPORTANT: Only offer products or services listed in 'Our Offerings'.

Delivery/Pickup Options:
{delivery_options_info}

Communication Guidelines:
{communication_guidelines}
--- End Company Profile Information ---

**Instructions:**
1.  **Prioritize Knowledge Base:** Base your answer primarily on the information provided in the 'Knowledge Base Context' section above, if relevant to the user's query.
2.  **Use Company Profile:** If the Knowledge Base doesn't contain the answer, use the 'Company Profile Information' provided.
3.  **Adhere to Guidelines:** Always follow the 'Communication Guidelines'.
4.  **Be Honest:** If the information is not found in either the Knowledge Base or the Company Profile, state that you don't have that specific detail. DO NOT invent information (addresses, phone numbers, prices, features, etc.).
5.  **Use History:** Refer to the 'Conversation History' below for context.
6.  **Current Time:** Use the current date and time ({current_datetime}) for time-sensitive questions.
7.  **Respond to Last Message:** Focus your response on the latest customer message.

{fallback_instructions}
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
    """Formats list items with a prefix and newline separators for the prompt."""
    if not items:
        return "N/A"
    return "\n".join([f"{prefix}{item}" for item in items])


def _format_history_lc_messages(history: List[BaseMessage]) -> List[BaseMessage]:
    """Passes through LangChain BaseMessages, potentially reversing if needed."""
    logger.debug(f"Using {len(history)} messages for chat history placeholder.")
    return history


# --- Main Function  ---
def build_llm_prompt_messages(
    profile: CompanyProfileSchema,
    chat_history_lc: List[BaseMessage],
    current_datetime: str,
    retrieved_context: Optional[str] = None,
) -> List[BaseMessage]:
    """
    Constructs the list of messages for the LLM using ChatPromptTemplate,
    incorporating RAG context.

    Args:
        profile: The loaded CompanyProfileSchema object.
        chat_history_lc: List of previous BaseMessage objects (Human/AI).
                         The last message is assumed to be the user's input.
        current_datetime: The current date and time as a string.
        retrieved_context: Optional string containing relevant snippets from the knowledge base.

    Returns:
        A list of BaseMessage objects ready for the chat model. Empty list on error.
    """
    if not profile:
        logger.error("Cannot build prompt messages with invalid profile.")
        return []
    if not chat_history_lc:
        logger.error("Cannot build prompt messages with empty chat history.")
        return []

    knowledge_text = (
        "No specific context retrieved from the knowledge base for this query."
    )
    if retrieved_context and retrieved_context.strip():
        knowledge_text = retrieved_context

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
            "retrieved_knowledge": knowledge_text,
        }

        all_input_vars = {
            **system_vars,
            "chat_history": chat_history_lc,
        }

        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_MESSAGE_TEMPLATE),
                MessagesPlaceholder(variable_name="chat_history"),
            ]
        )

        formatted_messages = chat_template.format_messages(**all_input_vars)

        logger.debug(
            f"Generated prompt messages for company {profile.company_name} including RAG context."
        )
        return formatted_messages

    except KeyError as e:
        logger.error(
            f"Missing key when formatting chat prompt for company {profile.company_name}: {e}."
        )
        return []
    except Exception as e:
        logger.exception(
            f"Error formatting chat prompt for company {profile.company_name}"
        )
        return []
