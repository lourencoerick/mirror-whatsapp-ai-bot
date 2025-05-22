# backend/app/services/ai_reply/new_agent/schemas/offer_selection.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Assuming OfferingInfo might be imported or defined elsewhere,
# for now, we'll use a simplified structure for what the LLM needs.
from app.api.schemas.company_profile import OfferingInfo  # Ideal


class SelectedOffer(BaseModel):
    """
    Represents a single offer selected by the LLM.
    """

    product_name: str = Field(
        ...,
        description="The exact name of the selected product/offering from the available list.",
    )
    # Details below would be populated by the node using the product_name to look up
    # in the company_profile.offering_overview for consistency, rather than relying on LLM to recreate them.
    # The LLM's job is primarily selection.
    product_details: Optional[OfferingInfo] = Field(
        None,
        description="Full details of the selected product from the company profile.",
    )
    reason_for_selection: str = Field(
        ...,
        description="Brief justification from the LLM on why this offer was chosen based on user context.",
    )
    confidence_score: Optional[float] = Field(
        None,
        description="LLM's confidence in this selection (0.0 to 1.0).",
        ge=0.0,
        le=1.0,
    )
    key_benefit_to_highlight: Optional[str] = Field(
        None,
        description="The primary benefit of this selected offer that should be highlighted to the user, based on the conversation.",
    )

    class Config:
        extra = "forbid"


class OfferSelectionOutput(BaseModel):
    """
    Structured output from the OfferSelector component.
    """

    selected_offer: Optional[SelectedOffer] = Field(
        None,
        description="The best available offer selected by the LLM. Null if no suitable offer found or below confidence.",
    )
    no_suitable_offer_found: bool = Field(
        False,
        description="True if the LLM explicitly determined no available offer matches the user's needs.",
    )
    alternative_suggestions_if_no_match: Optional[List[str]] = Field(
        default_factory=list,
        description="If no direct match, suggestions for related products or information to ask the user.",
    )
    clarifying_questions_to_ask: Optional[List[str]] = Field(
        default_factory=list,
        description="If user input is too vague, questions the agent could ask to narrow down options.",
    )
    overall_justification: str = Field(
        ...,
        description="Overall justification from the LLM for its decision (selected_offer, no_offer, or need_clarification).",
    )

    class Config:
        extra = "forbid"
