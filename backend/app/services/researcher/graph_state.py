# backend/app/services/researcher/graph_state.py

from typing import TypedDict, List, Set, Dict, Optional, Any, Literal  # Added Literal
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl  # Added BaseModel, Field, HttpUrl

# Import the schema that represents our target output
try:
    from app.api.schemas.company_profile import CompanyProfileSchema

    SCHEMA_AVAILABLE = True
except ImportError:
    from pydantic import BaseModel as PydanticBaseModel  # Alias to avoid conflict

    class CompanyProfileSchema(PydanticBaseModel):
        pass

    SCHEMA_AVAILABLE = False


class ResearchState(TypedDict):
    # ... (definição existente do ResearchState) ...
    account_id: UUID
    initial_url: str
    urls_to_scrape: List[str]
    search_queries: List[str]
    scraped_data: Dict[str, str]
    search_results: Dict[str, List[Any]]
    combined_context: Optional[str]
    profile_draft: Optional[CompanyProfileSchema]
    missing_info_summary: Optional[str]
    visited_urls: Set[str]
    max_iterations: int
    iteration_count: int
    error_message: Optional[str]
    next_action: Optional[str]  # This will be set by the planner


# --- Schema for Planner Output ---


class PlannerDecisionSchema(BaseModel):
    """
    Defines the structured output expected from the planning LLM call.
    """

    next_action: Literal["scrape", "search", "finish"] = Field(
        ...,
        description="The best next action to take: 'scrape' specific URLs, perform 'search' queries, or 'finish' the research.",
    )
    reasoning: Optional[str] = Field(
        None, description="A brief explanation of why this action was chosen."
    )
    urls_to_scrape: Optional[List[HttpUrl]] = Field(
        default_factory=list,
        description="List of specific internal URLs to scrape next. Only provide if next_action is 'scrape'.",
    )
    search_queries: Optional[List[str]] = Field(
        default_factory=list,
        description="List of specific search queries to execute. Only provide if next_action is 'search'.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "next_action": "scrape",
                    "reasoning": "Missing contact phone and address. The /contact page might contain this.",
                    "urls_to_scrape": [
                        "https://example.com/contact",
                        "https://example.com/about-us/location",
                    ],
                    "search_queries": [],
                },
                {
                    "next_action": "search",
                    "reasoning": "Opening hours not found on website. Searching externally.",
                    "urls_to_scrape": [],
                    "search_queries": [
                        "Example Inc opening hours",
                        "telefone Example Inc",
                    ],
                },
                {
                    "next_action": "finish",
                    "reasoning": "All key profile fields seem populated based on available information.",
                    "urls_to_scrape": [],
                    "search_queries": [],
                },
            ]
        }
    }
