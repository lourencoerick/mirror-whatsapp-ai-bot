# backend/app/services/ai_reply/new_agent/schemas/input_analysis.py

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# This type would ideally be imported from a central state definition
# to ensure consistency. For this schema file, we define it to show intent.
# from ..state_definition import CustomerQuestionStatusType as CentralCustomerQuestionStatusType
SimplifiedCustomerQuestionStatusType = Literal[
    "answered_satisfactorily",
    "answered_with_fallback",
    "unknown_previous_status",  # Used if the original question isn't found or its answer status is unclear
]
"""Simplified status of how a previously asked (original) question was handled by the agent."""


# --- Schemas for the FINAL output of the InputProcessor component ---
# This is what the StateUpdater will ultimately receive.


class ExtractedQuestionAnalysis(BaseModel):
    """
    Detailed analysis of a single question extracted from the user's current message,
    INCLUDING its repetition status against previous questions.
    """

    question_text: str = Field(
        ..., description="The core, normalized text of the extracted question."
    )
    is_repetition: bool = Field(
        ...,
        description="True if this question is a semantic repetition of a previously asked one.",
    )
    status_of_original_answer: Optional[SimplifiedCustomerQuestionStatusType] = Field(
        None,
        description="If is_repetition is true, this indicates how the agent answered the original instance of this question.",
    )
    original_question_turn: Optional[int] = Field(
        None,
        description="If is_repetition is true, the turn number when the original question was first asked.",
    )
    original_question_core_text: Optional[str] = Field(
        None,
        description="If is_repetition is true, the core text of the original question it matches from the log.",
    )

    class Config:
        extra = "forbid"


class ExtractedObjection(BaseModel):
    """Details of an objection identified in the user's message."""

    objection_text: str = Field(
        ..., description="The core text expressing the objection."
    )

    class Config:
        extra = "forbid"


class ExtractedNeedOrPain(BaseModel):
    """Details of an identified customer need or pain point."""

    text: str = Field(
        ...,
        description="The text from the user's message describing the need or pain point.",
    )
    type: Literal["need", "pain_point"] = Field(
        ...,
        description="Classification of whether the statement represents a 'need' or a 'pain_point'.",
    )

    class Config:
        extra = "forbid"


class PendingAgentActionResponseAnalysis(BaseModel):
    """
    Analyzes how the user's current message relates to the agent's
    immediately preceding action or question.
    """

    user_response_to_agent_action: Literal[
        "answered_clearly",
        "partially_answered",
        "ignored_agent_action",
        "acknowledged_action",
        "not_applicable",
    ] = Field(
        ...,
        description="How the user's message responded to the agent's last specific action/question.",
    )

    class Config:
        extra = "forbid"


class UserInputAnalysisOutput(BaseModel):
    """
    FINAL comprehensive structured output from the InputProcessor component,
    after all analysis (including repetition checks) is complete.
    This object will be used by the StateUpdater.
    """

    overall_intent: Literal[
        "Greeting",
        "Farewell",
        "Questioning",
        "StatingInformationOrOpinion",
        "ExpressingObjection",
        "ExpressingNeedOrPain",
        "RespondingToAgent",
        "VagueOrUnclear",
        "OffTopic",
        "PositiveFeedback",
        "NegativeFeedback",
        "RequestingClarificationFromAgent",
    ] = Field(..., description="The primary, overall intent of the user's message.")

    extracted_questions: List[ExtractedQuestionAnalysis] = (
        Field(  # Uses the detailed analysis
            default_factory=list,
            description="All distinct questions identified, including their repetition analysis.",
        )
    )
    extracted_objections: List[ExtractedObjection] = Field(default_factory=list)
    extracted_needs_or_pains: List[ExtractedNeedOrPain] = Field(default_factory=list)
    analysis_of_response_to_agent_action: PendingAgentActionResponseAnalysis
    is_primarily_vague_statement: bool = Field(False)
    is_primarily_off_topic: bool = Field(False)

    class Config:
        extra = "forbid"


# --- Schemas for the INTERMEDIATE output of the first LLM call (extraction only) ---


class SingleRepetitionCheckOutput(BaseModel):
    """Output of LLM checking if a new question is a repetition of a single logged question."""

    is_semantic_repetition: bool = Field(
        ...,
        description="Is the new question a semantic repetition of the logged question?",
    )


class InitiallyExtractedQuestion(BaseModel):
    """
    Represents a question extracted from user input by the first LLM call,
    BEFORE detailed repetition analysis.
    """

    question_text: str = Field(
        ..., description="The core, normalized text of the extracted question."
    )
    # Any other attributes the first LLM might extract about the question itself,
    # for example, a preliminary topic, could be added here.
    # E.g., preliminary_topic: Optional[str] = None

    class Config:
        extra = "forbid"


class InitialUserInputAnalysis(BaseModel):
    """
    Structured output from the *first LLM call* in the InputProcessor.
    Focuses on extraction, defers detailed repetition analysis.
    """

    overall_intent: Literal[
        "Greeting",
        "Farewell",
        "Questioning",
        "StatingInformationOrOpinion",
        "ExpressingObjection",
        "ExpressingNeedOrPain",
        "RespondingToAgent",
        "VagueOrUnclear",
        "OffTopic",
        "PositiveFeedback",
        "NegativeFeedback",
        "RequestingClarificationFromAgent",
    ] = Field(..., description="The primary, overall intent of the user's message.")

    initially_extracted_questions: List[InitiallyExtractedQuestion] = Field(
        default_factory=list,
        description="Questions extracted, pending detailed repetition analysis.",
    )
    # The following fields are assumed to be extractable by the first LLM call directly
    extracted_objections: List[ExtractedObjection] = Field(default_factory=list)
    extracted_needs_or_pains: List[ExtractedNeedOrPain] = Field(default_factory=list)
    analysis_of_response_to_agent_action: PendingAgentActionResponseAnalysis
    is_primarily_vague_statement: bool = Field(False)
    is_primarily_off_topic: bool = Field(False)

    class Config:
        extra = "forbid"
