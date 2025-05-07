# backend/app/services/ai_reply/new_agent/state_definition.py

from typing import TypedDict, List, Optional, Dict, Any, Literal
from typing_extensions import Annotated  # For LangGraph message accumulation
from uuid import UUID

# --- LangGraph Message Accumulation ---
# This is often used in the state if messages are appended directly within graph operations.
try:
    from langgraph.graph.message import add_messages

    LANGGRAPH_AVAILABLE = True
except ImportError:
    add_messages = lambda x, y: (
        x + y
        if isinstance(x, list) and isinstance(y, list)
        else (y if x is None else x)
    )  # Simplified fallback
    LANGGRAPH_AVAILABLE = False
    print(
        "WARNING: langgraph.graph.message.add_messages not found. "
        "Message accumulation might behave as simple list concatenation."
    )

# --- LangChain Core Message Type ---
try:
    from langchain_core.messages import BaseMessage

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    BaseMessage = Any  # type: ignore
    print(
        "WARNING: langchain_core.messages.BaseMessage not found. "
        "Message history typing will be 'Any'."
    )

# --- Application Specific Schemas (using Any to avoid circular deps in this core file) ---
# In a real setup, you'd ensure these are resolvable or use forward references if needed.
CompanyProfileSchema = (
    Any  # Placeholder for app.api.schemas.company_profile.CompanyProfileSchema
)
BotAgentRead = Any  # Placeholder for app.api.schemas.bot_agent.BotAgentRead


# === Enums and Literals for State Fields ===

AgentGoalType = Literal[
    "GREETING",
    "INVESTIGATING_NEEDS",
    "BUILDING_CERTAINTY",
    "PRESENTING_SOLUTION",
    "HANDLING_OBJECTION",
    "CLARIFYING_USER_INPUT",
    "ATTEMPTING_CLOSE",
    "PROCESSING_ORDER",
    "ENDING_CONVERSATION",
    "IDLE",  # New: Represents a state waiting for user input without a proactive agent goal
]

AgentActionType = Literal[
    "ASK_SPIN_QUESTION",
    "MAKE_CERTAINTY_STATEMENT",
    "PRESENT_SOLUTION_OFFER",
    "GENERATE_REBUTTAL",
    "ASK_CLARIFYING_QUESTION",  # Agent asks to clarify user's vague statement
    "INITIATE_CLOSING",
    "CONFIRM_ORDER_DETAILS",
    "PROCESS_ORDER_CONFIRMATION",  # Agent confirms order is (theoretically) processed
    "HANDLE_CLOSING_CORRECTION",
    "GENERATE_GREETING",
    "GENERATE_FAREWELL",
    "ANSWER_DIRECT_QUESTION",  # Agent answers a direct question from user
    "ACKNOWLEDGE_AND_TRANSITION",  # General acknowledgement and moving on
    "HANDLE_IMPASSE",  # When stuck on an unanswerable question
]

SpinQuestionType = Literal["Situation", "Problem", "Implication", "NeedPayoff"]
CertaintyFocusType = Literal["product", "agent", "company"]

CustomerQuestionStatusType = Literal[
    "newly_asked",  # Freshly asked by the user in the current turn
    "answered_satisfactorily",  # Agent provided a good answer previously
    "answered_with_fallback",  # Agent couldn't answer (used fallback) previously
    "pending_agent_answer",  # User asked, agent hasn't responded yet in this turn's plan
    "repetition_after_satisfactory_answer",
    "repetition_after_fallback",
    "ignored_by_agent",  # Agent decided to ignore after multiple fallbacks (impasse)
]

ObjectionStatusType = Literal[
    "active",  # Newly raised or re-raised
    "addressing",  # Agent is currently formulating a rebuttal
    "addressed_needs_check",  # Agent offered a rebuttal, waiting for user reaction
    "resolved",  # User indicates objection is no longer a blocker
    "ignored",  # Agent decided to move on after failed rebuttals
]

UserInterruptionType = Literal[
    "direct_question", "objection", "vague_statement", "off_topic_comment"
]


# === Detailed Sub-TypedDicts for RichConversationState ===


class AgentActionDetails(TypedDict, total=False):
    """
    Specific parameters for an agent's action.
    Keys are optional and depend on the action_type.
    """

    spin_type: Optional[SpinQuestionType]
    certainty_focus: Optional[CertaintyFocusType]
    objection_text_to_address: Optional[str]
    question_to_answer_text: Optional[str]  # User's question text
    proposed_product_name: Optional[str]
    # ... other details as needed for different actions


class PendingAgentAction(TypedDict):
    """
    Represents the action the agent just performed or was about to perform,
    which the user's latest message might be a response to.
    """

    action_type: AgentActionType
    details: AgentActionDetails
    action_generation_text: Optional[str]  # The actual text generated for this action
    attempts: int  # Number of times this specific action was attempted/re-iterated


class AgentGoal(TypedDict):
    """Defines the agent's current high-level objective for the conversation."""

    goal_type: AgentGoalType
    # Stores the previous goal if the current goal is a temporary interruption (e.g., handling a direct question)
    previous_goal_if_interrupted: Optional[
        Dict[str, Any]
    ]  # Recursive AgentGoal, use Dict for simplicity here
    goal_details: Optional[
        Dict[str, Any]
    ]  # E.g., specific product to present, objection to handle


class IdentifiedNeedEntry(TypedDict):
    """An identified customer need."""

    text: str
    status: Literal["active", "addressed_by_agent", "confirmed_by_user"]
    priority: Optional[int]  # 0-10, higher is more important
    source_turn: int  # Turn number when need was identified


class IdentifiedPainPointEntry(TypedDict):
    """An identified customer pain point."""

    text: str
    status: Literal["active", "addressed_by_agent", "confirmed_by_user"]
    source_turn: int


class IdentifiedObjectionEntry(TypedDict):
    """An identified customer objection."""

    text: str  # The core of the objection
    status: ObjectionStatusType
    rebuttal_attempts: int
    source_turn: int
    related_to_proposal: Optional[bool]  # Was this objection about a specific proposal?


class CustomerCertaintyLevels(TypedDict):
    """Customer's perceived certainty levels (scale 0-10)."""

    product: Optional[int]
    agent: Optional[int]
    company: Optional[int]
    last_assessed_turn: Optional[int]


class DynamicCustomerProfile(TypedDict):
    """Aggregates inferred data about the customer."""

    identified_needs: List[IdentifiedNeedEntry]
    identified_pain_points: List[IdentifiedPainPointEntry]
    identified_objections: List[IdentifiedObjectionEntry]
    certainty_levels: CustomerCertaintyLevels
    last_discerned_intent: Optional[str]
    # communication_style_preference: Optional[str] # E.g., "direct", "formal", "friendly" (advanced)
    # key_information_provided: Dict[str, Any] # E.g., {"email": "test@example.com"}


class CustomerQuestionEntry(TypedDict):
    """
    Tracks a specific question asked by the customer and how it was handled.
    Used for repetition detection and ensuring questions are addressed.
    """

    original_question_text: (
        str  # Full text from user message part containing the question
    )
    extracted_question_core: str  # The essential part of the question
    turn_asked: int  # Turn number when this question was first identified
    status: CustomerQuestionStatusType
    # Summary of how the agent responded IF this question was the primary focus of a response
    agent_direct_response_summary: Optional[str]
    # If this is a repetition, points to the turn_asked of the first instance
    repetition_of_turn: Optional[int]
    # Embedding or hash for similarity checks
    similarity_vector: Optional[List[float]]  # Or a string hash


class UserInterruption(TypedDict):
    """
    Represents a point where the user's input deviates from the agent's
    current pending action or goal, requiring a temporary shift in focus.
    """

    type: UserInterruptionType
    text: str  # The core text of the interruption (e.g., the question, the objection)
    status: Literal["pending_resolution", "resolved", "acknowledged"]
    turn_detected: int


class ProposedSolution(TypedDict):
    """Details of a solution/offer proposed to the customer."""

    product_name: str
    quantity: Optional[int]
    price: Optional[float]
    price_info: Optional[str]  # E.g., "per month", "one-time"
    key_benefits_highlighted: List[str]
    turn_proposed: int
    status: Literal["proposed", "accepted", "rejected", "needs_correction"]


# === Main Conversation State Definition ===


class RichConversationState(TypedDict):
    """
    The central, rich state representation for an AI sales agent conversation.
    Manages all aspects of the dialogue, agent's strategy, customer understanding,
    and operational metadata.
    """

    # --- Core Identifiers & Configuration ---
    account_id: UUID
    conversation_id: UUID
    bot_agent_id: Optional[UUID]
    company_profile: CompanyProfileSchema
    agent_config: BotAgentRead

    # --- Conversation History & Current Input ---
    messages: Annotated[List[BaseMessage], add_messages]
    current_user_input_text: str
    current_turn_number: int

    # --- Agent's Internal State & Strategy ---
    current_agent_goal: AgentGoal
    last_agent_action: Optional[PendingAgentAction]
    user_interruptions_queue: List[UserInterruption]
    next_agent_action_command: Optional[AgentActionType]
    action_parameters: AgentActionDetails

    # --- Dynamically Inferred Customer Profile ---
    customer_profile_dynamic: DynamicCustomerProfile

    # --- Customer Question Tracking ---
    customer_question_log: List[CustomerQuestionEntry]
    current_turn_extracted_questions: List[CustomerQuestionEntry]

    # --- Sales Process Specific State ---
    active_proposal: Optional[ProposedSolution]
    closing_process_status: Optional[
        Literal[
            "not_started",
            "attempt_made",
            "awaiting_confirmation",
            "confirmation_rejected",
            "needs_correction",
            "confirmed_success",
            "confirmed_failed_to_process",
        ]
    ]
    last_objection_handled_turn: Optional[int]

    # --- Context for Generation & Operational Data ---
    retrieved_knowledge_for_next_action: Optional[str]
    last_agent_generation_text: Optional[str]
    conversation_summary_for_llm: Optional[str]
    last_interaction_timestamp: float
    is_simulation: bool

    # --- Resultado da Análise do Input (NOVO CAMPO) ---
    # Este campo armazenará temporariamente o resultado do process_user_input_node
    # para ser usado pelo state_updater_node.
    user_input_analysis_result: Optional[Dict[str, Any]]

    # --- Error Handling & System Status ---
    last_processing_error: Optional[str]
    disengagement_reason: Optional[str]
