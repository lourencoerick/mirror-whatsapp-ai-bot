# backend/app/services/ai_reply/new_agent/state_definition.py

from typing import List, Optional, Dict, Any, Literal
from typing_extensions import Annotated, TypedDict
from uuid import UUID
import time  # Import time for default timestamp

# --- LangGraph Message Accumulation ---
try:
    from langgraph.graph.message import add_messages

    LANGGRAPH_AVAILABLE = True
except ImportError:
    add_messages = lambda x, y: (
        x + y
        if isinstance(x, list) and isinstance(y, list)
        else (y if x is None else x)
    )
    LANGGRAPH_AVAILABLE = False
    print("WARNING: langgraph.graph.message.add_messages not found.")

# --- LangChain Core Message Type ---
try:
    from langchain_core.messages import BaseMessage

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    BaseMessage = Any  # type: ignore
    print("WARNING: langchain_core.messages.BaseMessage not found.")

# --- Application Specific Schemas (using Any to avoid circular deps) ---
# Ideally, import these properly or use forward references if needed.
# from app.api.schemas.company_profile import CompanyProfileSchema
# from app.api.schemas.bot_agent import BotAgentRead
CompanyProfileSchema = Any
BotAgentRead = Any


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
    "IDLE",
]
"""Defines the possible high-level objectives of the sales agent."""

AgentActionType = Literal[
    "ASK_SPIN_QUESTION",
    "MAKE_CERTAINTY_STATEMENT",
    "PRESENT_SOLUTION_OFFER",
    "GENERATE_REBUTTAL",
    "ASK_CLARIFYING_QUESTION",
    "INITIATE_CLOSING",
    "CONFIRM_ORDER_DETAILS",
    "PROCESS_ORDER_CONFIRMATION",
    "HANDLE_CLOSING_CORRECTION",
    "GENERATE_GREETING",
    "GENERATE_FAREWELL",
    "ANSWER_DIRECT_QUESTION",
    "ACKNOWLEDGE_AND_TRANSITION",
    # "HANDLE_IMPASSE",
    "DECIDE_PROACTIVE_STEP",
]
"""Defines the specific low-level actions the agent can plan and execute."""

SpinQuestionType = Literal["Situation", "Problem", "Implication", "NeedPayoff"]
"""Types of questions used in the SPIN selling methodology."""

CertaintyFocusType = Literal["product", "agent", "company"]
"""Areas where customer certainty can be assessed."""

CustomerQuestionStatusType = Literal[
    "newly_asked",
    "answered_satisfactorily",
    "answered_with_fallback",
    "pending_agent_answer",
    "repetition_after_satisfactory_answer",
    "repetition_after_fallback",
    "ignored_by_agent",
]
"""Tracks the status of questions asked by the customer."""

ObjectionStatusType = Literal[
    "active",
    "addressing",
    "addressed_needs_check",
    "resolved",
    "ignored",
]
"""Tracks the status of objections raised by the customer."""

UserInterruptionType = Literal[
    "direct_question", "objection", "vague_statement", "off_topic_comment"
]
"""Classifies the type of user input that interrupts the agent's flow."""

ClosingProcessStatusType = Literal[
    "not_started",
    "attempt_made",
    "awaiting_confirmation",
    "confirmation_rejected",
    "needs_correction",
    "confirmed_success",
    "confirmed_failed_to_process",
]
"""Tracks the current stage of the sales closing process."""

TriggerEventType = Literal["user_message", "follow_up_timeout"]

# === Detailed Sub-TypedDicts for RichConversationState ===


class AgentActionDetails(TypedDict, total=False):
    """
    Specific parameters for an agent's planned action.

    Keys are optional and depend on the `action_type`.

    Attributes:
        spin_type: The type of SPIN question to ask.
        certainty_focus: The focus area for a certainty statement.
        objection_text_to_address: The specific objection text for rebuttal.
        question_to_answer_text: The user's question text to be answered.
        question_to_answer_status: The user's question status to be answered.
        proposed_product_name: The name of the product being proposed.
        product_name: Product name used in closing actions.
        price: Price used in closing actions.
        price_info: Additional price context (e.g., '/month').
        context: Contextual information for handling corrections or transitions.
        off_topic_text: Text of the off-topic comment being acknowledged.
        previous_goal_topic: Topic to transition back to after interruption.
        product_name_to_present: Product name for PRESENT_SOLUTION_OFFER.
        key_benefit_to_highlight: Benefit to focus on for PRESENT_SOLUTION_OFFER.
        reason: Reason for generating a farewell message.
    """

    spin_type: Optional[SpinQuestionType]
    certainty_focus: Optional[CertaintyFocusType]
    objection_text_to_address: Optional[str]
    question_to_answer_text: Optional[str]
    question_to_answer_status: Optional[str]
    proposed_product_name: Optional[str]
    # Closing related
    product_name: Optional[str]
    price: Optional[float]
    price_info: Optional[str]
    # Correction/Transition related
    context: Optional[str]
    off_topic_text: Optional[str]
    previous_goal_topic: Optional[str]
    # Presentation related
    product_name_to_present: Optional[str]
    key_benefit_to_highlight: Optional[str]
    # Farewell related
    reason: Optional[str]

    # Follow-up
    trigger_source: Optional[TriggerEventType]
    current_follow_up_attempts: Optional[int]


class PendingAgentAction(TypedDict):
    """
    Represents the action the agent just performed or was about to perform.

    Used to provide context for interpreting the user's next message and for
    tracking action history.

    Attributes:
        action_type: The type of the action performed.
        details: Specific parameters used for this action.
        action_generation_text: The actual text generated by the LLM for this action.
        attempts: Number of times this specific action was attempted/re-iterated (future use).
    """

    action_type: AgentActionType
    details: AgentActionDetails
    action_generation_text: Optional[str]
    attempts: int


class AgentGoal(TypedDict):
    """
    Defines the agent's current high-level objective for the conversation.

    Attributes:
        goal_type: The primary objective (e.g., INVESTIGATING_NEEDS).
        previous_goal_if_interrupted: Stores the previous goal if the current
            goal is temporary (e.g., handling an interruption). Recursive structure
            represented as Dict for simplicity.
        goal_details: A dictionary containing specific details relevant to the
            current goal (e.g., SPIN question counters, objection text).
    """

    goal_type: AgentGoalType
    previous_goal_if_interrupted: Optional[Dict[str, Any]]  # Recursive AgentGoal
    goal_details: Optional[Dict[str, Any]]


class IdentifiedNeedEntry(TypedDict):
    """Represents an identified customer need."""

    text: str
    status: Literal["active", "addressed_by_agent", "confirmed_by_user"]
    priority: Optional[int]  # 0-10, higher is more important
    source_turn: int  # Turn number when need was identified


class IdentifiedPainPointEntry(TypedDict):
    """Represents an identified customer pain point."""

    text: str
    status: Literal["active", "addressed_by_agent", "confirmed_by_user"]
    source_turn: int


class IdentifiedObjectionEntry(TypedDict):
    """Represents an identified customer objection."""

    text: str  # The core text of the objection
    status: ObjectionStatusType
    rebuttal_attempts: int  # How many times agent tried to rebut this
    source_turn: int
    related_to_proposal: Optional[bool]  # Was this about a specific proposal?


class CustomerCertaintyLevels(TypedDict):
    """Customer's perceived certainty levels (scale 0-10, optional)."""

    product: Optional[int]
    agent: Optional[int]
    company: Optional[int]
    last_assessed_turn: Optional[int]


class DynamicCustomerProfile(TypedDict):
    """
    Aggregates dynamically inferred data about the customer during the conversation.

    Attributes:
        identified_needs: List of identified customer needs.
        identified_pain_points: List of identified customer pain points.
        identified_objections: List of identified customer objections.
        certainty_levels: Estimated customer certainty levels.
        last_discerned_intent: The most recently identified user intent.
    """

    identified_needs: List[IdentifiedNeedEntry]
    identified_pain_points: List[IdentifiedPainPointEntry]
    identified_objections: List[IdentifiedObjectionEntry]
    certainty_levels: CustomerCertaintyLevels
    last_discerned_intent: Optional[str]


class CustomerQuestionEntry(TypedDict):
    """
    Tracks a specific question asked by the customer and how it was handled.

    Used for repetition detection and ensuring questions are addressed.

    Attributes:
        original_question_text: Full text from user message part containing the question.
        extracted_question_core: The essential part of the question (normalized).
        turn_asked: Turn number when this question was first identified.
        status: Current status of the question handling.
        agent_direct_response_summary: Summary of agent's response if directly answered.
        repetition_of_turn: If a repetition, points to the turn_asked of the first instance.
        similarity_vector: Optional embedding for similarity checks (future use).
    """

    original_question_text: str
    extracted_question_core: str
    turn_asked: int
    status: CustomerQuestionStatusType
    agent_direct_response_summary: Optional[str]
    repetition_of_turn: Optional[int]
    similarity_vector: Optional[List[float]]


class UserInterruption(TypedDict):
    """
    Represents a point where user input deviates from the agent's flow.

    Used by the Planner to prioritize handling these deviations.

    Attributes:
        type: The type of interruption (question, objection, etc.).
        text: The core text of the interruption.
        status: Whether the interruption is pending resolution or resolved.
        turn_detected: The turn number when the interruption was detected.
    """

    type: UserInterruptionType
    text: str
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
    The central state representation for an AI sales agent conversation.

    Manages all aspects of the dialogue, agent's strategy, customer understanding,
    and operational metadata required for the LangGraph execution flow.

    Attributes:
        account_id: Unique identifier for the account/client.
        conversation_id: Unique identifier for this specific conversation.
        bot_agent_id: Optional identifier for the specific bot agent configuration used.
        company_profile: Static information about the company (name, offerings, etc.).
        agent_config: Configuration specific to the bot agent instance.

        messages: The history of messages in the conversation (accumulated).
        current_user_input_text: The latest message received from the user for processing.
        current_turn_number: The current turn number in the conversation.

        current_agent_goal: The agent's current high-level objective.
        last_agent_action: The last action performed by the agent.
        user_interruptions_queue: List of pending user interruptions to be handled.
        next_agent_action_command: The specific action planned for the current turn.
        action_parameters: Parameters required for the planned action.

        customer_profile_dynamic: Dynamically inferred information about the customer.
        customer_question_log: Log of questions asked by the customer.
        current_turn_extracted_questions: Temporary list of questions extracted in the current turn (used by StateUpdater).

        active_proposal: Details of the solution currently proposed to the customer.
        closing_process_status: Current status of the sales closing process.
        last_objection_handled_turn: Turn number when the last objection was addressed (future use).

        retrieved_knowledge_for_next_action: Context retrieved from RAG for the planned action.
        last_agent_generation_text: Raw text output from the response generator LLM.
        final_agent_message_text: Formatted text ready to be sent to the user.
        conversation_summary_for_llm: Optional summary for providing long-term context to LLMs.
        last_interaction_timestamp: Timestamp of the last message processed.
        is_simulation: Flag indicating if the conversation is a simulation.

        user_input_analysis_result: Temporary storage for the output of the InputProcessor node.
        last_processing_error: Stores error message from the last failed node execution.
        disengagement_reason: Optional reason why the conversation ended prematurely.
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
    current_turn_extracted_questions: List[CustomerQuestionEntry]  # Temp field

    # --- Sales Process Specific State ---
    active_proposal: Optional[ProposedSolution]
    closing_process_status: Optional[ClosingProcessStatusType]
    last_objection_handled_turn: Optional[int]

    # --- Context for Generation & Operational Data ---
    retrieved_knowledge_for_next_action: Optional[str]  # RAG context
    last_agent_generation_text: Optional[str]  # Raw LLM output
    final_agent_message_text: Optional[str]  # Formatted output
    conversation_summary_for_llm: Optional[str]
    last_interaction_timestamp: float
    is_simulation: bool

    # --- Temporary fields for inter-node communication ---
    user_input_analysis_result: Optional[Dict[str, Any]]  # Output of InputProcessor

    # --- Follow-up ---
    follow_up_scheduled: Optional[bool]  # True se um follow-up está "armado"
    follow_up_attempt_count: Optional[
        int
    ]  # Quantos follow-ups por inatividade já foram tentados nesta sequência
    last_message_from_agent_timestamp: Optional[float]
    # temporary variable to indicate that the trigger was set!
    trigger_event: Optional[TriggerEventType]

    # --- Error Handling & System Status ---
    last_processing_error: Optional[str]
    disengagement_reason: Optional[str]

    # --- Default values for initialization ---
    # It's often better to handle defaults in the graph initialization
    # but providing some here can be helpful for type checking.
    # Example (adjust as needed):
    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)
    #     self.setdefault("current_turn_number", 0)
    #     self.setdefault("messages", [])
    #     # ... other defaults
