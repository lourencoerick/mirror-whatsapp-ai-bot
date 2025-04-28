# backend/app/services/ai_reply/graph_state.py

from typing import TypedDict, List, Optional, Dict, Any
from typing_extensions import Annotated
from uuid import UUID


try:
    from langgraph.graph.message import add_messages

    LANGGRAPH_AVAILABLE = True
except ImportError:
    add_messages = None
    LANGGRAPH_AVAILABLE = False
    print("WARNING: langgraph not found. Message accumulation will not work correctly.")


try:
    from langchain_core.messages import BaseMessage

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    BaseMessage = Any


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


class ConversationState(TypedDict):
    """
    Represents the state during the processing of an AI reply for a conversation.
    """

    # --- Identifiers ---
    account_id: UUID
    conversation_id: UUID
    bot_agent_id: UUID

    # --- Loaded Configuration ---
    company_profile: CompanyProfileSchema
    agent_config: BotAgentRead

    # --- Conversation Flow ---
    messages: Annotated[List[Any], add_messages]
    input_message: str
    retrieved_context: Optional[str]
    generation: Optional[str]

    # --- Error Handling ---
    error: Optional[str]
