# backend/app/services/researcher/graph_nodes.py

import asyncio
from typing import Dict, Any, List, Optional, Set, Type
from loguru import logger
from uuid import UUID
from pydantic import BaseModel


# Import state and schemas
from .graph_state import (
    ResearchState,
    # CompanyProfileSchema,
    PlannerDecisionSchema,
    SCHEMA_AVAILABLE,
)


# Import web loader
try:
    from .web_loader_simple import fetch_and_extract_text

    SIMPLE_LOADER_AVAILABLE = True
except ImportError:
    SIMPLE_LOADER_AVAILABLE = False
    logger.error("Simple web loader 'fetch_and_extract_text' not found.")

    async def fetch_and_extract_text(*args, **kwargs) -> Optional[str]:
        return None  # Dummy


# Import search client
try:
    from app.services.search.client import perform_tavily_search, SearchResult

    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.error("Search service 'perform_tavily_search' not found.")

    class SearchResult(dict):
        pass

    async def perform_tavily_search(*args, **kwargs) -> List[SearchResult]:
        return []  # Dummy


# Import extractor
try:
    from .extractor import extract_profile_from_text

    EXTRACTOR_AVAILABLE = True
except ImportError:
    EXTRACTOR_AVAILABLE = False
    logger.error("Extractor function 'extract_profile_from_text' not found.")

    async def extract_profile_from_text(
        *args, **kwargs
    ) -> Optional[CompanyProfileSchema]:
        return None  # Dummy


# Import LLM base
try:
    from langchain_core.language_models import BaseChatModel

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

    class BaseChatModel:
        pass


# Import trustcall
try:
    from trustcall import create_extractor

    TRUSTCALL_AVAILABLE = True
except ImportError:
    TRUSTCALL_AVAILABLE = False
    logger.error("trustcall library not found.")

    async def create_extractor(*args, **kwargs):
        raise ImportError("trustcall not installed")


# Import Repository functions and DB Model/Session
try:
    from app.services.repository.company_profile import (
        get_profile_by_account_id,
        create_profile,
        update_profile,
    )
    from app.api.schemas.company_profile import CompanyProfileSchema
    from app.models.company_profile import CompanyProfile as CompanyProfileModel
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    REPO_AVAILABLE = True
except ImportError:
    REPO_AVAILABLE = False
    logger.error("Repository or DB components not found.")

    async def get_profile_by_account_id(*args, **kwargs):
        return None

    async def create_profile(*args, **kwargs):
        return None

    async def update_profile(*args, **kwargs):
        return None

    class CompanyProfileModel:
        pass

    AsyncSession = None  # type: ignore
    async_sessionmaker = None  # type: ignore


# ==============================================================================
# Graph Nodes
# ==============================================================================


# --- Node: start_research ---
async def start_research(state: ResearchState) -> Dict[str, Any]:
    """Initializes the research process state."""
    account_id = state.get("account_id")
    initial_url = state.get("initial_url")

    logger.info("--- Starting Research Graph ---")
    logger.info(f"Account ID: {account_id}")
    logger.info(f"Initial URL: {initial_url}")

    if not account_id or not initial_url:
        error_msg = "Missing account_id or initial_url in initial state."
        logger.error(error_msg)
        return {"error_message": error_msg, "next_action": "error"}

    # Initialize state fields
    updates = {
        "urls_to_scrape": [initial_url],
        "search_queries": [],
        "scraped_data": {},
        "search_results": {},
        "combined_context": None,
        "profile_draft": None,
        "missing_info_summary": None,
        "visited_urls": set(),
        "iteration_count": 0,
        "error_message": None,
        "next_action": None,
        # max_iterations should be passed in the initial state if needed
    }
    logger.debug("Initialized research state.")
    return updates


# --- Node: scrape_website ---
async def scrape_website(state: ResearchState) -> Dict[str, Any]:
    """Fetches content from URLs specified in the state."""
    if not SIMPLE_LOADER_AVAILABLE:
        logger.error("Simple web loader unavailable.")
        return {"error_message": "Web loader unavailable.", "next_action": "error"}

    urls_to_fetch = state.get("urls_to_scrape", [])
    visited_urls = state.get("visited_urls", set())
    scraped_data = state.get("scraped_data", {})

    if not urls_to_fetch:
        logger.info("No URLs provided in 'urls_to_scrape'. Skipping scraping.")
        return {"urls_to_scrape": []}  # Clear the list

    new_urls_to_fetch = [url for url in urls_to_fetch if url not in visited_urls]
    if not new_urls_to_fetch:
        logger.info("All URLs in 'urls_to_scrape' have already been visited.")
        return {"urls_to_scrape": []}  # Clear the list

    logger.info(f"Fetching {len(new_urls_to_fetch)} new URLs...")
    tasks = [fetch_and_extract_text(url=url) for url in new_urls_to_fetch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    newly_visited = set()
    for i, result in enumerate(results):
        url = new_urls_to_fetch[i]
        newly_visited.add(url)
        if isinstance(result, Exception):
            logger.error(f"Error scraping URL {url}: {result}")
        elif result:
            scraped_data[url] = result
            logger.success(f"Scraped {url}")
        else:
            logger.warning(f"No content for {url}")

    updates = {
        "scraped_data": scraped_data,
        "visited_urls": visited_urls.union(newly_visited),
        "urls_to_scrape": [],  # Clear processed list
        "error_message": state.get("error_message"),  # Preserve previous error
    }
    logger.info(
        f"Finished scraping. Visited: {len(newly_visited)}. "
        f"Total scraped: {len(scraped_data)}."
    )
    return updates


# --- Node: perform_search ---
async def perform_search(state: ResearchState) -> Dict[str, Any]:
    """Executes search queries specified in the state."""
    if not SEARCH_AVAILABLE:
        logger.error("Search service unavailable.")
        return {"error_message": "Search unavailable.", "next_action": "error"}

    queries = state.get("search_queries", [])
    search_results_agg = state.get("search_results", {})

    if not queries:
        logger.info("No search queries provided. Skipping search.")
        return {"search_queries": []}  # Clear the list

    logger.info(f"Starting search for {len(queries)} queries: {queries}")
    search_tasks = [perform_tavily_search(query=q, max_results=3) for q in queries]
    results_list = await asyncio.gather(*search_tasks, return_exceptions=True)

    for i, result in enumerate(results_list):
        query = queries[i]
        if isinstance(result, Exception):
            logger.error(f"Error searching '{query}': {result}")
            search_results_agg[query] = []
        elif isinstance(result, list):
            logger.success(f"Search OK for '{query}'. Found {len(result)}")
            search_results_agg[query] = result
        else:
            logger.warning(
                f"Unexpected search result type for '{query}': {type(result)}"
            )
            search_results_agg[query] = []

    updates = {
        "search_results": search_results_agg,
        "search_queries": [],  # Clear processed list
        "error_message": state.get("error_message"),  # Preserve previous error
    }
    logger.info(f"Finished searching. Processed {len(queries)} queries.")
    return updates


# --- Node: update_profile ---
async def update_company_profile(state: ResearchState, config: dict) -> Dict[str, Any]:
    """
    Combines context and uses LLM extractor to update profile_draft.
    Requires 'llm_instance' in the config.
    """
    if not EXTRACTOR_AVAILABLE or not SCHEMA_AVAILABLE:
        logger.error("Extractor or Schema unavailable.")
        return {"error_message": "Extractor unavailable.", "next_action": "error"}

    scraped_data = state.get("scraped_data", {})
    search_results = state.get("search_results", {})
    current_profile_draft = state.get("profile_draft")

    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_instance"
    )
    if not llm_instance:
        logger.error("LLM instance not found in config for update_profile node.")
        return {
            "error_message": "LLM unavailable for extraction.",
            "next_action": "error",
        }

    # --- Combine Context ---
    combined_parts = []
    if scraped_data:
        combined_parts.append("--- Website Content ---")
        for url, content in scraped_data.items():
            # Limit content per page shown in context
            combined_parts.append(f"\n[Source: {url}]\n{content[:10000]}")
        combined_parts.append("--- End Website Content ---")

    if search_results:
        combined_parts.append("\n\n--- Search Results ---")
        for query, results in search_results.items():
            combined_parts.append(f"\n[Query: {query}]")
            result_snippets = [
                f"- Title: {res.get('title', 'N/A')}\n  URL: {res.get('url', 'N/A')}\n  Snippet: {res.get('content', 'N/A')}\n"
                for res in results  # Assuming results is a list of dicts
            ]
            combined_parts.append("\n".join(result_snippets))
        combined_parts.append("--- End Search Results ---")

    if not combined_parts:
        logger.info("No new data to process. Skipping profile update.")
        return {"scraped_data": {}, "search_results": {}, "combined_context": None}

    combined_context = "\n".join(combined_parts)
    logger.info(
        f"Combined context generated. Length: {len(combined_context)}. "
        f"Updating profile draft..."
    )

    # --- Call Extractor ---
    try:
        newly_extracted_profile = await extract_profile_from_text(
            website_text=combined_context,
            llm=llm_instance,
            target_schema=CompanyProfileSchema,
        )
    except Exception as e:
        logger.exception(f"Error calling extract_profile_from_text: {e}")
        return {
            "error_message": f"Extractor failed: {e}",
            "next_action": "error",
            "scraped_data": {},  # Clear inputs even on error
            "search_results": {},
            "combined_context": combined_context,  # Keep context for debugging
        }

    # --- Update Profile Draft ---
    updated_profile_draft = current_profile_draft
    if newly_extracted_profile:
        logger.success("Extractor returned new profile schema.")
        # Simple overwrite strategy
        updated_profile_draft = newly_extracted_profile
    else:
        logger.warning("Extractor did not return valid profile schema.")
        # Keep existing draft if extraction failed

    updates = {
        "profile_draft": updated_profile_draft,
        "scraped_data": {},  # Clear processed data
        "search_results": {},  # Clear processed data
        "combined_context": combined_context,  # Store context used
        "error_message": state.get("error_message"),  # Preserve previous error
    }
    return updates


# --- Node: analyze_completeness ---
async def analyze_completeness(state: ResearchState) -> Dict[str, Any]:
    """Analyzes the current profile_draft to identify missing information."""
    logger.info("Analyzing profile draft for completeness...")
    profile_draft = state.get("profile_draft")
    missing_info_summary = "Profile draft is not yet available."

    if not SCHEMA_AVAILABLE:
        logger.error("Schema unavailable for completeness check.")
        return {"missing_info_summary": "Error: Schema definition unavailable."}

    if profile_draft and isinstance(profile_draft, CompanyProfileSchema):
        missing_fields = []
        try:
            profile_dict = profile_draft.model_dump(exclude_unset=False)
            for field_name, field_info in CompanyProfileSchema.model_fields.items():
                value = profile_dict.get(field_name)
                is_missing = False
                field_type = field_info.annotation
                is_optional = (
                    getattr(field_type, "__origin__", None) is Optional
                    or str(field_type).startswith("Optional[")
                    or type(None) in getattr(field_type, "__args__", [])
                )

                if value is None and not is_optional:
                    is_missing = True
                elif isinstance(value, (list, str, dict)) and not value:
                    is_missing = True  # Consider empty sequences/strings as missing

                if is_missing:
                    missing_fields.append(field_name)

            if not missing_fields:
                missing_info_summary = (
                    "Profile analysis suggests all key fields are present."
                )
            else:
                missing_info_summary = (
                    f"Missing or empty fields identified: {', '.join(missing_fields)}."
                )
            logger.info(f"Completeness analysis result: {missing_info_summary}")

        except Exception as e:
            logger.exception(f"Error analyzing profile draft: {e}")
            missing_info_summary = f"Error during analysis: {e}"
    elif profile_draft is not None:
        logger.warning(
            f"profile_draft is not a CompanyProfileSchema: {type(profile_draft)}"
        )
        missing_info_summary = "Profile draft in unexpected format."
    else:
        logger.info("Profile draft is empty.")

    return {"missing_info_summary": missing_info_summary}


# --- Node: plan_next_step ---
async def plan_next_step(state: ResearchState, config: dict) -> Dict[str, Any]:
    """Decides the next action. Requires 'llm_instance' in config."""
    if not TRUSTCALL_AVAILABLE or not LANGCHAIN_AVAILABLE:
        logger.error("Planning components unavailable.")
        return {
            "error_message": "Planning components unavailable.",
            "next_action": "error",
        }

    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 5)
    error_message = state.get("error_message")
    missing_info = state.get("missing_info_summary", "Analysis not available.")
    profile_draft = state.get("profile_draft")
    initial_url = state.get("initial_url", "N/A")
    current_iteration = iteration_count + 1

    logger.info(
        f"--- Planning Step: Iteration {current_iteration}/{max_iterations} ---"
    )

    # Check termination conditions
    if error_message:
        logger.warning(f"Error detected: {error_message}. Finishing.")
        return {"next_action": "finish", "iteration_count": current_iteration}
    if current_iteration > max_iterations:
        logger.warning(f"Max iterations reached. Finishing.")
        return {"next_action": "finish", "iteration_count": current_iteration}
    if "all key fields are present" in missing_info:
        logger.success("Profile complete. Finishing.")
        return {"next_action": "finish", "iteration_count": current_iteration}

    # Get LLM
    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_instance"
    )
    if not llm_instance:
        logger.error("LLM instance not found in config for planning node.")
        return {
            "error_message": "LLM unavailable for planning.",
            "next_action": "error",
            "iteration_count": current_iteration,
        }

    # Prepare profile summary
    profile_summary = "Profile draft is currently empty."
    if profile_draft and isinstance(profile_draft, CompanyProfileSchema):
        try:
            profile_summary = f"Current Profile Draft Summary:\n{profile_draft.model_dump(exclude_unset=True)}"
        except Exception:
            profile_summary = "Could not serialize profile draft."

    # Build prompt
    prompt = f"""
You are an automated research planner. Your goal is to decide the next step to gather information needed to complete a company profile.

Target Website: {initial_url}

Current Profile Status:
{profile_summary}

Analysis of Missing Information (may be incomplete):
{missing_info}

**CRITICAL GOAL:** Regardless of the 'Missing Information' analysis, you MUST prioritize actions that help find, verify, or add detail about the company's specific **products, services, and pricing/plans** (offerings). Ensure these are well-represented before considering the profile complete. Understand the company context, before making a decision. Always use at least one time, the search for product, this will help you to have more information. 

Based on the current profile status AND the critical goal above, decide the *single best next action* to take. Your options are:
1.  'scrape': If you believe specific pages on the *target website* likely contain the missing info OR details about products/services/plans (e.g., '/products', '/services', '/pricing', '/contact', '/about'). Provide the *full URLs* to scrape.
2.  'search': If the information (especially product/service details or pricing) is unlikely to be found on the known website pages or requires external verification. Provide specific, targeted search queries (e.g., "[Company Name] product list", "[Company Name] service pricing").
3.  'finish': Choose this *only if* the profile seems reasonably complete, you have specifically attempted to find details about products/services/plans (via scrape or search in previous steps), and further actions are unlikely to yield significant improvements to the offerings information or other critical fields.

Use the 'PlannerDecisionSchema' to structure your response. Provide *only* the JSON object.
Choose 'scrape' OR 'search', not both. If choosing 'scrape', provide URLs. If choosing 'search', provide queries. If choosing 'finish', leave URLs and queries empty.
"""
    logger.debug("Sending planning request to LLM...")

    # Call LLM
    try:
        planner_agent = create_extractor(
            llm=llm_instance,
            tools=[PlannerDecisionSchema],
            tool_choice=PlannerDecisionSchema.__name__,
        )
        result = await planner_agent.ainvoke(prompt)
        responses = result.get("responses")

        if isinstance(responses, list) and len(responses) > 0:
            decision = responses[0]
            if isinstance(decision, PlannerDecisionSchema):
                logger.info(
                    f"Planner decided: '{decision.next_action}'. "
                    f"Reasoning: {decision.reasoning or 'N/A'}"
                )
                updates = {
                    "next_action": decision.next_action,
                    "iteration_count": current_iteration,
                    "urls_to_scrape": (
                        [str(url) for url in decision.urls_to_scrape]
                        if decision.urls_to_scrape
                        else []
                    ),
                    "search_queries": (
                        decision.search_queries if decision.search_queries else []
                    ),
                    "error_message": None,  # Clear error on successful planning
                }
                return updates
            else:
                error_msg = "Planner LLM output failed validation."
                logger.error(f"{error_msg} Type: {type(decision)}")
        else:
            error_msg = "Planner LLM call failed."
            logger.error(f"{error_msg} Result: {result}")

    except Exception as e:
        logger.exception(f"Error during planner LLM call: {e}")
        error_msg = f"Planner LLM error: {e}"

    # Handle failure
    return {
        "error_message": error_msg,
        "next_action": "error",
        "iteration_count": current_iteration,
    }


# --- Node: finish_research ---
async def finish_research(state: ResearchState, config: dict) -> Dict[str, Any]:
    """Final node: Saves the completed profile_draft to the database."""
    logger.info("--- Finishing Research Graph ---")
    profile_draft = state.get("profile_draft")
    account_id = state.get("account_id")
    error_message = state.get("error_message")
    final_iteration = state.get("iteration_count", "N/A")

    if error_message:
        logger.error(
            f"Research finished due to error after {final_iteration} iterations: {error_message}"
        )

    if not account_id:
        logger.critical("Cannot save profile: account_id missing.")
        return {}

    if not profile_draft or not isinstance(profile_draft, CompanyProfileSchema):
        logger.warning(f"No valid profile draft to save for account {account_id}.")
        return {}

    # Get DB Session Factory from config
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = config.get(
        "configurable", {}
    ).get("db_session_factory")
    if not db_session_factory or not REPO_AVAILABLE:
        logger.error(
            "DB session factory or repository unavailable. Cannot save profile."
        )
        try:
            logger.error(
                f"Profile draft data not saved: {profile_draft.model_dump_json(indent=2)}"
            )
        except Exception:
            logger.error("Could not serialize profile draft for logging.")
        return {}

    try:
        # Use mode='json' to serialize HttpUrl etc. to strings
        # Exclude 'id' as it's not directly set/updated this way
        profile_data_dict = profile_draft.model_dump(
            mode="json", exclude={"id"}, exclude_unset=False
        )
        logger.debug(f"Profile data prepared for DB save: {profile_data_dict}")
    except Exception as dump_err:
        logger.exception(f"Failed to serialize profile draft for DB: {dump_err}")
        return {}

    # Save to Database
    logger.info(f"Attempting to save final profile draft for account {account_id}...")
    saved_successfully = False
    profile_id = None
    try:
        async with db_session_factory() as db:
            try:
                existing_profile = await get_profile_by_account_id(
                    db=db, account_id=account_id
                )
                saved_profile: Optional[CompanyProfileModel] = None

                if existing_profile:
                    logger.info(
                        f"Updating existing profile (ID: {existing_profile.id})."
                    )
                    saved_profile = await update_profile(
                        db=db, db_profile=existing_profile, profile_in=profile_data_dict
                    )
                else:
                    logger.info(f"Creating new profile for account {account_id}.")
                    saved_profile = await create_profile(
                        db=db, profile_in=profile_draft, account_id=account_id
                    )

                if saved_profile:
                    profile_id = getattr(saved_profile, "id", None)
                    await db.commit()
                    saved_successfully = True
                    logger.success(f"Saved final profile to DB. ID: {profile_id}")
                else:
                    logger.error("Repo create/update returned None. Rolling back.")
                    await db.rollback()
            except Exception as db_exc:
                logger.exception(f"DB error during final save: {db_exc}. Rolling back.")
                await db.rollback()
    except Exception as session_exc:
        logger.exception(f"Error managing DB session during final save: {session_exc}")

    if not saved_successfully:
        logger.error(f"Failed to save final profile draft for account {account_id}.")

    return {}  # Terminal node
