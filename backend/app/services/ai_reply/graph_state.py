# backend/app/services/ai_reply/graph_state.py

from typing import TypedDict, List, Optional, Dict, Any
from typing_extensions import Annotated
from uuid import UUID

# --- LangGraph Message Accumulation ---
try:
    from langgraph.graph.message import add_messages

    LANGGRAPH_AVAILABLE = True
except ImportError:
    add_messages = lambda x: x
    LANGGRAPH_AVAILABLE = False
    print(
        "WARNING: langgraph not found. Message accumulation ('add_messages') will not work correctly."
    )

# --- LangChain Core Message Type ---
try:
    from langchain_core.messages import BaseMessage

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    BaseMessage = Any

# --- Application Specific Schemas ---
try:
    from app.api.schemas.company_profile import CompanyProfileSchema
    from app.api.schemas.bot_agent import BotAgentRead

    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False
    print(
        "WARNING: CompanyProfileSchema or BotAgentRead not found. State typing incomplete."
    )
    from pydantic import BaseModel

    class CompanyProfileSchema(BaseModel):
        pass

    class BotAgentRead(BaseModel):
        pass


# --- Define Sales Stages & SPIN Types ---
SALES_STAGE_OPENING = "Opening"
SALES_STAGE_QUALIFICATION = "Qualification"
SALES_STAGE_INVESTIGATION = "Investigation"
SALES_STAGE_PRESENTATION = "Presentation"
SALES_STAGE_OBJECTION_HANDLING = "ObjectionHandling"
SALES_STAGE_CLOSING = "Closing"
SALES_STAGE_FOLLOW_UP = "FollowUp"
SALES_STAGE_UNKNOWN = "Unknown"
SPIN_TYPE_SITUATION = "Situation"
SPIN_TYPE_PROBLEM = "Problem"
SPIN_TYPE_IMPLICATION = "Implication"
SPIN_TYPE_NEED_PAYOFF = "NeedPayoff"


CERTAINTY_STATUS_OK = "OK"  # Indicates certainty threshold met
CERTAINTY_STATUS_STATEMENT_MADE = (
    "StatementMade"  # Indicates a statement was made, awaiting response
)


class ConversationState(TypedDict):
    """
    Represents the evolving state during the AI reply generation process,
    including conversation history, configuration, RAG context, sales stage,
    and identified customer information.
    """

    # === Core Identifiers & Configuration ===
    account_id: UUID
    conversation_id: UUID
    bot_agent_id: UUID
    company_profile: CompanyProfileSchema
    agent_config: BotAgentRead

    # === Conversation History & Input ===
    messages: Annotated[List[BaseMessage], add_messages]
    input_message: str

    # === RAG & Generation ===
    retrieved_context: Optional[str]
    generation: Optional[str]

    # === Sales Process State ===
    classification_details: Optional[Dict[str, Any]]
    current_sales_stage: Optional[str]
    customer_needs: Optional[List[str]]
    customer_pain_points: Optional[List[str]]

    # === SPIN Subgraph State ===
    spin_question_type: Optional[str]
    problem_mentioned: Optional[bool]
    problem_summary: Optional[str]
    need_expressed: Optional[bool]
    need_summary: Optional[str]
    last_spin_question_type: Optional[str]
    explicit_need_identified: bool
    # spin_history: Optional[List[Dict[str, str]]] # Optional history tracking

    # === Straight Line Subgraph State ===
    certainty_level: Optional[Dict[str, int]]
    certainty_focus: Optional[str]
    proposed_solution_details: Optional[Dict[str, Any]]
    certainty_status: Optional[str]

    # === Objection Handling State ===
    current_objection: Optional[str]
    objection_loop_count: int
    objection_resolution_status: Optional[str]

    # === Closing Subgraph State (Inicial) ===
    closing_attempt_count: int
    closing_status: Optional[str]

    # === Control & Metadata ===
    intent: Optional[str]
    is_simulation: bool
    loop_count: int

    # === Error Handling ===
    error: Optional[str]
