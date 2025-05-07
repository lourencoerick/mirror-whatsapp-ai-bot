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


class ReactionToPresentation(BaseModel):
    """Analysis of user's reaction if agent just presented a solution."""

    reaction_type: Optional[
        Literal[
            "positive_interest",  # Ex: "Gostei!", "Parece bom", "Quero saber mais"
            "specific_question",  # Fez pergunta sobre a solução apresentada
            "new_objection_to_solution",  # Levantou objeção à solução apresentada
            "neutral_or_vague",  # Ex: "Ok", "Entendi", "Vou pensar"
            "off_topic_or_unrelated",
            "not_applicable",  # Se o agente não acabou de apresentar uma solução
        ]
    ] = Field(
        "not_applicable", description="User's reaction type to a solution presentation."
    )
    details: Optional[str] = Field(
        None, description="Specific text of question or objection if applicable."
    )


class ObjectionAfterRebuttalStatus(BaseModel):
    """Analysis of an objection's status after the agent attempted a rebuttal."""

    # Qual objeção estava sendo tratada (texto da objeção original)
    original_objection_text_handled: Optional[str] = Field(None)

    status: Optional[
        Literal[
            "appears_resolved",  # Ex: "Ah, entendi agora!", "Faz sentido", cliente segue para compra
            "still_persists",  # Cliente reitera a mesma objeção ou dúvida
            "new_objection_raised",  # Cliente levanta uma objeção DIFERENTE
            "unclear_still_evaluating",  # Cliente ainda está pensando, não deu sinal claro
            "changed_topic",  # Cliente mudou de assunto, ignorando o rebuttal
            "not_applicable",  # Se o agente não acabou de fazer um rebuttal
        ]
    ] = Field(
        "not_applicable", description="Status of the objection after agent's rebuttal."
    )
    new_objection_text: Optional[str] = Field(
        None, description="Text of the new objection, if raised."
    )


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
        "PositiveFeedbackToProposal",
        "NegativeFeedbackToProposal",
        "RequestForNextStepInPurchase",
    ] = Field(..., description="The primary, overall intent of the user's message.")

    initially_extracted_questions: List[InitiallyExtractedQuestion] = Field(
        default_factory=list,
        description="Questions extracted, pending detailed repetition analysis.",
    )

    reaction_to_solution_presentation: Optional[ReactionToPresentation] = Field(
        default_factory=ReactionToPresentation,  # Default para not_applicable
        description="Analysis of user's reaction if agent just presented a solution.",
    )
    objection_status_after_rebuttal: Optional[ObjectionAfterRebuttalStatus] = Field(
        default_factory=ObjectionAfterRebuttalStatus,  # Default para not_applicable
        description="Analysis of objection status if agent just made a rebuttal.",
    )
    # The following fields are assumed to be extractable by the first LLM call directly
    extracted_objections: List[ExtractedObjection] = Field(default_factory=list)
    extracted_needs_or_pains: List[ExtractedNeedOrPain] = Field(default_factory=list)
    analysis_of_response_to_agent_action: PendingAgentActionResponseAnalysis
    is_primarily_vague_statement: bool = Field(False)
    is_primarily_off_topic: bool = Field(False)

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
        "PositiveFeedbackToProposal",
        "NegativeFeedbackToProposal",
        "RequestForNextStepInPurchase",
    ] = Field(..., description="The primary, overall intent of the user's message.")

    reaction_to_solution_presentation: Optional[ReactionToPresentation]
    objection_status_after_rebuttal: Optional[ObjectionAfterRebuttalStatus]

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
