from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing_extensions import Annotated, List, Optional, Literal, Dict, Any
from langgraph.graph import add_messages
from langgraph.managed.is_last_step import RemainingSteps
from langchain_core.messages import BaseMessage

from app.api.schemas.company_profile import CompanyProfileSchema
from app.api.schemas.bot_agent import BotAgentRead

TriggerEventType = Literal["user_message", "follow_up_timeout"]

SalesStageLiteral = Literal[
    "initial_contact",  # First interaction with the customer.
    "qualification",  # Assessing customer needs and fit.
    "discovery",  # Deep diving into customer's problems and goals.
    "offering_presentation",  # Presenting relevant products/services.
    "cart_management",  # Customer is adding/modifying items in the shopping cart.
    "objection_handling",  # Addressing customer concerns or objections.
    "checkout_initiated",  # Customer has confirmed intent to purchase, preparing for payment.
    "checkout_link_sent",  # Payment link or instructions have been provided.
    "appointment_scheduling_in_progress",  # Cliente pediu para agendar, IA está buscando horários.
    "appointment_booked",  # Agendamento confirmado e criado no calendário.
    "appointment_rescheduled",  # Um agendamento existente foi remarcado.
    "appointment_cancelled",  # Um agendamento foi cancelado.
    "follow_up_scheduled",
    "follow_up_pending",  # A follow-up action has been scheduled and is waiting for its trigger time.
    "follow_up_in_progress",  # A follow-up message has been sent, awaiting customer response or next step.
    # "human_handoff_requested",  # Customer requested or agent decided to escalate to a human agent.
    # "human_handoff_in_progress",# The process of transferring to a human agent is underway.
    "closed_won",  # Sale successfully completed.
    "closed_lost",  # Customer decided not to purchase or engagement ended without a sale.
    # "dormant"                   # Conversation is inactive for a significant period.
]


class ShoppingCartItem(BaseModel):
    """Represents an item эмодзи within the customer's shopping cart."""

    offering_id: UUID = Field(
        description="Unique ID of the offering from CompanyProfile.OfferingInfo."
    )
    name: str = Field(description="Name of the offering in the cart.")
    checkout_link: Optional[HttpUrl] = Field(
        None, description="Checkout link of the offering."
    )
    quantity: int = Field(description="Quantity of this offering in the cart.")
    unit_price: Optional[float] = Field(
        None,
        description="Unit price of the offering at the time it was added to the cart.",
    )
    item_total: Optional[float] = Field(
        None,
        description="Total price for this item in the cart (quantity * unit_price).",
    )


FollowUpTypeLiteral = Literal[
    "cart_abandonment",
    "post_interaction_check_in",
    "no_response_to_offer",
    "custom_reminder",
]


class PendingFollowUpTrigger(BaseModel):
    """
    Represents a scheduled follow-up action that needs to be triggered.
    This model would typically be stored within the AgentState.
    """

    trigger_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this specific follow-up trigger instance.",
    )
    follow_up_type: FollowUpTypeLiteral = Field(
        ...,
        description="The specific type or reason for this follow-up.",
    )
    due_timestamp: float = Field(
        ...,
        description="The epoch timestamp (seconds since epoch) when this follow-up is due to be triggered.",
    )

    defer_by: float = Field(
        ...,
        description="The difference between current datetime and due_timestamp in seconds.",
    )

    target_conversation_id: UUID = Field(
        ...,
        description="Identifier of the conversation or user this follow-up pertains to.",
    )

    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dictionary palavras-chave containing relevant context for the follow-up. "
        "E.g., {'last_offering_discussed': 'Product X', 'cart_items_count': 2, "
        "'previous_stage': 'checkout_link_sent'}",
    )

    model_config = {"validate_assignment": True}


class AgentState(BaseModel):
    """
    The central state representation for an AI sales agent conversation.
    Manages all aspects of the dialogue, agent's strategy, customer understanding,
    and operational metadata required for the LangGraph execution flow.
    """

    # --- Core Identifiers & Configuration ---
    account_id: UUID = Field(
        description="Unique identifier for the account this conversation belongs to (e.g., the client's business account)."
    )
    conversation_id: UUID = Field(
        description="Unique identifier for this specific conversation."
    )
    bot_agent_id: UUID = Field(
        description="Identifier for the specific bot agent configuration being used for this conversation."
    )

    customer_phone: str = Field(
        description="Customer Phone Number used in the converastion."
    )

    company_profile: CompanyProfileSchema = Field(
        description="The static profile of the company the sales agent is representing. Loaded at the start of the conversation."
    )
    agent_config: BotAgentRead = Field(
        description="Configuration settings specific to this bot agent instance (e.g., behavior parameters, specific LLM settings)."
    )
    trigger_event: Optional[TriggerEventType] = Field(
        None,
        description="The type of event that triggered the current processing turn (e.g., 'user_message', 'follow_up_timeout').",
    )

    remaining_steps: RemainingSteps = Field(
        RemainingSteps(),
        description="Remaining Steps",
    )

    # --- Conversation History & Current Input ---
    messages: Annotated[List[BaseMessage], add_messages] = Field(
        default_factory=list,
        description="The history of messages in the conversation (Human, AI, System, Tool). The latest user input is the last HumanMessage.",
    )
    current_user_input_text: Optional[str] = None
    current_turn_number: int = Field(
        default=0,
        description="The current turn number in the conversation, incremented with each agent-user exchange.",
    )

    found_appointments: Optional[List[Dict]] = Field(
        default=None,
        description="A list of Google Calendar event dictionaries found by the `find_customer_appointments` tool during the current conversation turn. This is used as a short-term memory to allow follow-up actions like cancelling or updating one of the found appointments. It should be cleared or replaced in each new turn.",
    )

    # --- Sales Process ---
    current_sales_stage: SalesStageLiteral = Field(
        default="initial_contact",
        description="The current stage of the sales conversation, guiding agent behavior and objectives.",
    )
    shopping_cart: List[ShoppingCartItem] = Field(
        default_factory=list,
        description="List of items the customer has added to their shopping cart.",
    )

    # --- Follow-up & Engagement Tracking ---
    pending_follow_up_trigger: Optional[PendingFollowUpTrigger] = Field(
        None,
        description="Details of a scheduled follow-up action (e.g., {'type': 'cart_abandonment', 'due_timestamp': 1678886400, 'context': '...'})",
    )
    follow_up_attempt_count: Optional[int] = Field(
        default=0,
        description="Number of follow-up attempts made for the current pending follow-up or in the current sequence.",
    )

    last_user_interaction_timestamp: Optional[float] = Field(
        None,
        description="Timestamp (epoch) of the last message received from the user.",
    )
    last_agent_message_timestamp: Optional[float] = Field(
        None, description="Timestamp (epoch) of the last message sent by the agent."
    )

    # --- Operational & Debugging ---
    last_processing_error: Optional[str] = Field(
        None,
        description="Stores the error message from the last failed node execution in the graph.",
    )
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Important for Langchain types like BaseMessage
        validate_assignment=True,  # Re-validates fields upon assignment
        from_attributes=True,  # Useful if creating from ORM models or other attribute-based objects
    )
