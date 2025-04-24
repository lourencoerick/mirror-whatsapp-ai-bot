import asyncio
from typing import Dict, Any, List, Optional, Set, Type
from loguru import logger
from uuid import UUID
from pydantic import BaseModel

# Import state and schemas
from .graph_state import ResearchState, CompanyProfileSchema, PlannerDecisionSchema, SCHEMA_AVAILABLE
# Import web loader
try:
    from .web_loader_simple import fetch_and_extract_text
    SIMPLE_LOADER_AVAILABLE = True
except ImportError: SIMPLE_LOADER_AVAILABLE = False; async def fetch_and_extract_text(*args, **kwargs): return None
# Import search client
try:
    from app.services.search.client import perform_tavily_search, SearchResult
    SEARCH_AVAILABLE = True
except ImportError: SEARCH_AVAILABLE = False; class SearchResult(dict): pass; async def perform_tavily_search(*args, **kwargs): return []
# Import extractor
try:
    from .extractor import extract_profile_from_text
    EXTRACTOR_AVAILABLE = True
except ImportError: EXTRACTOR_AVAILABLE = False; async def extract_profile_from_text(*args, **kwargs): return None
# Import LLM base
try:
    from langchain_core.language_models import BaseChatModel
    LANGCHAIN_AVAILABLE = True
except ImportError: LANGCHAIN_AVAILABLE = False; class BaseChatModel: pass
# Import trustcall
try:
    from trustcall import create_extractor
    TRUSTCALL_AVAILABLE = True
except ImportError: TRUSTCALL_AVAILABLE = False; async def create_extractor(*args, **kwargs): raise ImportError("trustcall not installed")
# Import Repository functions and DB Model/Session
try:
    from app.services.repository.company_profile import (
        get_profile_by_account_id, create_profile, update_profile,
    )
    from app.models.company_profile import CompanyProfile as CompanyProfileModel
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker # Import sessionmaker
    REPO_AVAILABLE = True
except ImportError:
    logger.error("Repository or DB components not found.")
    REPO_AVAILABLE = False
    async def get_profile_by_account_id(*args, **kwargs): return None
    async def create_profile(*args, **kwargs): return None
    async def update_profile(*args, **kwargs): return None
    class CompanyProfileModel: pass
    AsyncSession = None # type: ignore
    async_sessionmaker = None # type: ignore

# --- Node: start_research ---
# (Keep the existing start_research function)
async def start_research(state: ResearchState) -> Dict[str, Any]:
    """Initializes the research process state."""
    account_id = state.get("account_id")
    initial_url = state.get("initial_url")
    logger.info(f"--- Starting Research Graph ---")
    logger.info(f"Account ID: {account_id}")
    logger.info(f"Initial URL: {initial_url}")
    if not account_id or not initial_url:
        error_msg = "Missing account_id or initial_url in initial state."
        logger.error(error_msg)
        return {"error_message": error_msg, "next_action": "error"}
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
    }
    logger.debug("Initialized research state.")
    return updates


# --- Node: scrape_website ---
# (Keep the existing scrape_website function)
async def scrape_website(state: ResearchState) -> Dict[str, Any]:
    """Fetches content from URLs specified in the state."""
    if not SIMPLE_LOADER_AVAILABLE:
        logger.error("Simple web loader is not available. Cannot scrape.")
        return {
            "error_message": "Web loader component unavailable.",
            "next_action": "error",
        }

    urls_to_fetch = state.get("urls_to_scrape", [])
    visited_urls = state.get("visited_urls", set())
    scraped_data = state.get("scraped_data", {})

    if not urls_to_fetch:
        logger.info("No URLs provided in 'urls_to_scrape'. Skipping scraping.")
        return {"urls_to_scrape": []}

    new_urls_to_fetch = [url for url in urls_to_fetch if url not in visited_urls]
    if not new_urls_to_fetch:
        logger.info("All URLs in 'urls_to_scrape' have already been visited.")
        return {"urls_to_scrape": []}

    logger.info(f"Fetching {len(new_urls_to_fetch)} new URLs...")
    tasks = [fetch_and_extract_text(url=url) for url in new_urls_to_fetch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    newly_visited = set()
    errors_encountered = False
    for i, result in enumerate(results):
        url = new_urls_to_fetch[i]
        newly_visited.add(url)
        if isinstance(result, Exception):
            logger.error(f"Error scraping URL {url}: {result}")
            errors_encountered = True
        elif result:
            logger.success(f"Successfully scraped URL: {url}")
            scraped_data[url] = result
        else:
            logger.warning(f"No content returned for URL: {url}")

    updates = {
        "scraped_data": scraped_data,
        "visited_urls": visited_urls.union(newly_visited),
        "urls_to_scrape": [],
        "error_message": state.get("error_message"),
    }
    logger.info(
        f"Finished scraping. Visited: {len(newly_visited)} new URLs. Total scraped pages: {len(scraped_data)}."
    )
    return updates


# --- Node: perform_search ---


async def perform_search(state: ResearchState) -> Dict[str, Any]:
    """
    Executes search queries specified in the state using the search service.

    Updates search_results in the state. Clears search_queries.

    Args:
        state: The current graph state.

    Returns:
        A dictionary containing the updates to the state.
    """
    if not SEARCH_AVAILABLE:
        logger.error("Search service is not available. Cannot perform search.")
        return {
            "error_message": "Search component unavailable.",
            "next_action": "error",
        }

    queries = state.get("search_queries", [])
    # Keep existing search results, add new ones
    search_results_agg = state.get("search_results", {})

    if not queries:
        logger.info("No search queries provided. Skipping search.")
        # Return empty update, but clear the list for next planning step
        return {"search_queries": []}

    logger.info(f"Starting search for {len(queries)} queries: {queries}")

    # --- Execute searches (can be concurrent) ---
    # Option 1: Concurrent execution
    search_tasks = [
        perform_tavily_search(query=q, max_results=3) for q in queries
    ]  # Limit results per query
    results_list = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Option 2: Sequential execution (simpler if concurrency isn't critical)
    # results_list = []
    # for q in queries:
    #     try:
    #         results_list.append(await perform_tavily_search(query=q, max_results=3))
    #     except Exception as e:
    #         results_list.append(e) # Append exception to handle below

    errors_encountered = False
    for i, result in enumerate(results_list):
        query = queries[i]
        if isinstance(result, Exception):
            logger.error(f"Error performing search for query '{query}': {result}")
            search_results_agg[query] = []  # Store empty list on error
            errors_encountered = True
        elif isinstance(result, list):
            logger.success(
                f"Search successful for query '{query}'. Found {len(result)} results."
            )
            # Store results keyed by the query
            search_results_agg[query] = result
        else:
            logger.warning(
                f"Unexpected result type for search query '{query}': {type(result)}"
            )
            search_results_agg[query] = []
            errors_encountered = True

    # Prepare state updates
    updates = {
        "search_results": search_results_agg,  # Updated dict with new results
        "search_queries": [],  # Clear the list for the next planning cycle
        "error_message": state.get("error_message"),  # Preserve existing error message
    }

    if errors_encountered and not updates["error_message"]:
        # Optionally set a general search error
        # updates["error_message"] = "Errors occurred during search engine queries."
        pass

    logger.info(f"Finished searching. Processed {len(queries)} queries.")

    return updates



# --- Node: update_profile ---

async def update_profile(state: ResearchState) -> Dict[str, Any]:
    """
    Combines scraped and search data, then uses the LLM extractor
    to update the profile_draft.

    Args:
        state: The current graph state, containing scraped_data, search_results,
               and potentially an existing profile_draft. Requires 'llm' instance
               in the graph's context/config.

    Returns:
        A dictionary containing the updates to the state.
    """
    if not EXTRACTOR_AVAILABLE or not SCHEMA_AVAILABLE:
        logger.error("Extractor function or CompanyProfileSchema unavailable.")
        return {"error_message": "Extractor unavailable.", "next_action": "error"}

    # Retrieve necessary components from state
    scraped_data: Dict[str, str] = state.get("scraped_data", {})
    search_results: Dict[str, List[Any]] = state.get("search_results", {})
    current_profile_draft: Optional[CompanyProfileSchema] = state.get("profile_draft")
    # --- IMPORTANT: Get LLM instance from graph context/config ---
    # LangGraph doesn't automatically pass the graph's configured objects (like llm)
    # directly into the state dict passed to nodes. We need to access it
    # when invoking the graph or make it available via config.
    # For now, we assume it's accessible via a mechanism outside the state dict.
    # We'll need to adjust the graph invocation later.
    # Placeholder: llm_instance = get_llm_from_somewhere()
    # Let's assume for now the graph runner provides it somehow, maybe via config
    # This is a placeholder and needs proper implementation during graph setup/invocation
    llm_instance: Optional[BaseChatModel] = state.get("llm_instance_placeholder") # Placeholder!

    if not llm_instance:
         logger.error("LLM instance not found in state/config for update_profile node.")
         return {"error_message": "LLM unavailable for extraction.", "next_action": "error"}


    # --- Combine Context ---
    combined_parts = []
    if scraped_data:
        combined_parts.append("--- Website Content ---")
        for url, content in scraped_data.items():
            combined_parts.append(f"\n[Source: {url}]\n{content[:10000]}") # Limit content per page
        combined_parts.append("--- End Website Content ---")

    if search_results:
        combined_parts.append("\n\n--- Search Results ---")
        for query, results in search_results.items():
            combined_parts.append(f"\n[Query: {query}]")
            for res in results:
                # Assuming res is a dict-like SearchResult
                title = res.get('title', 'N/A')
                url = res.get('url', 'N/A')
                content = res.get('content', 'N/A') # Snippet
                combined_parts.append(f"- Title: {title}\n  URL: {url}\n  Snippet: {content}\n")
        combined_parts.append("--- End Search Results ---")

    if not combined_parts:
        logger.info("No new scraped data or search results to process. Skipping profile update.")
        # Clear the inputs even if skipping extraction
        return {"scraped_data": {}, "search_results": {}, "combined_context": None}

    combined_context = "\n".join(combined_parts)
    logger.info(f"Combined context generated. Length: {len(combined_context)}. Updating profile draft...")
    logger.debug(f"Combined context sample: {combined_context[:500]}...")

    # --- Call Extractor ---
    try:
        # Use the existing extractor function
        newly_extracted_profile: Optional[CompanyProfileSchema] = await extract_profile_from_text(
            website_text=combined_context, # Pass combined context here
            llm=llm_instance,
            target_schema=CompanyProfileSchema
        )
    except Exception as e:
        logger.exception(f"Error calling extract_profile_from_text: {e}")
        return {
            "error_message": f"Extractor failed: {e}",
            "next_action": "error",
            "scraped_data": {}, # Clear inputs even on error
            "search_results": {},
            "combined_context": combined_context, # Keep context for debugging
        }

    # --- Update Profile Draft ---
    updated_profile_draft = current_profile_draft # Start with the current draft
    if newly_extracted_profile:
        logger.success("Extractor returned a new profile schema.")
        # --- Simple Overwrite Strategy ---
        # Replace the old draft entirely with the newly extracted one.
        # TODO: Consider a smarter merge strategy later if needed,
        # e.g., only updating fields that have non-None values in the new extraction.
        updated_profile_draft = newly_extracted_profile
        # --- End Simple Overwrite ---
    else:
        logger.warning("Extractor did not return a valid profile schema from the combined context.")
        # Keep the existing draft if extraction failed

    # --- Prepare State Updates ---
    updates = {
        "profile_draft": updated_profile_draft,
        "scraped_data": {}, # Clear processed data
        "search_results": {}, # Clear processed data
        "combined_context": combined_context, # Store context used for this update
        "error_message": state.get("error_message") # Preserve existing error
    }

    return updates


# --- Node: analyze_completeness ---


async def analyze_completeness(state: ResearchState) -> Dict[str, Any]:
    """
    Analyzes the current profile_draft to identify missing information.

    Uses a simple programmatic check for None or empty values.

    Args:
        state: The current graph state.

    Returns:
        A dictionary containing the 'missing_info_summary' update.
    """
    logger.info("Analyzing profile draft for completeness...")
    profile_draft: Optional[CompanyProfileSchema] = state.get("profile_draft")
    missing_info_summary = "Profile draft is not yet available."  # Default message

    if not SCHEMA_AVAILABLE:
        logger.error("CompanyProfileSchema not available for completeness check.")
        return {"missing_info_summary": "Error: Schema definition unavailable."}

    if profile_draft and isinstance(profile_draft, CompanyProfileSchema):
        missing_fields = []
        try:
            # Use model_dump to get dictionary representation for checking
            profile_dict = profile_draft.model_dump(
                exclude_unset=False
            )  # Include all fields

            # Iterate through the fields defined in the schema
            for field_name, field_info in CompanyProfileSchema.model_fields.items():
                value = profile_dict.get(field_name)
                is_missing = False

                # Check for None or empty values based on type
                # Consider field required status? For now, check all.
                field_type = field_info.annotation
                is_optional = (
                    getattr(field_type, "__origin__", None) is Optional
                    or str(field_type).startswith("Optional[")
                    or type(None) in getattr(field_type, "__args__", [])
                )  # Handle Union[T, None]

                if value is None:
                    # Allow None for optional fields unless we decide otherwise
                    if not is_optional:
                        is_missing = True
                elif isinstance(value, (list, str, dict)) and not value:
                    # Empty list, string, or dict might be considered missing
                    # We might want to refine this based on field importance
                    is_missing = True
                # Add more specific checks if needed (e.g., check length, format)

                if is_missing:
                    missing_fields.append(field_name)

            if not missing_fields:
                missing_info_summary = (
                    "Profile analysis suggests all key fields are present."
                )
                logger.success(missing_info_summary)
            else:
                missing_info_summary = (
                    f"Missing or empty fields identified: {', '.join(missing_fields)}."
                )
                logger.warning(missing_info_summary)

        except Exception as e:
            logger.exception(f"Error analyzing profile draft completeness: {e}")
            missing_info_summary = f"Error during analysis: {e}"
    elif profile_draft is not None:
        logger.warning(
            f"profile_draft exists but is not a CompanyProfileSchema instance: {type(profile_draft)}"
        )
        missing_info_summary = "Profile draft is in an unexpected format."
    else:
        logger.info("Profile draft is currently empty.")
        # Summary already set to default message

    return {"missing_info_summary": missing_info_summary}


# --- Node: plan_next_step ---


async def plan_next_step(state: ResearchState) -> Dict[str, Any]:
    """
    Decides the next action (scrape, search, finish) based on the current state.

    Uses an LLM call with structured output (PlannerDecisionSchema).

    Args:
        state: The current graph state. Requires 'llm' instance in context/config.

    Returns:
        A dictionary containing the updates to the state, including 'next_action',
        'urls_to_scrape' or 'search_queries', and incremented 'iteration_count'.
    """
    if not TRUSTCALL_AVAILABLE or not LANGCHAIN_AVAILABLE:
        logger.error("Trustcall or LangChain unavailable. Cannot plan next step.")
        return {
            "error_message": "Planning components unavailable.",
            "next_action": "error",
        }

    # --- Get State and Check Conditions ---
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 5)  # Default to 5 if not set
    error_message = state.get("error_message")
    missing_info = state.get("missing_info_summary", "Analysis not available.")
    profile_draft = state.get("profile_draft")
    initial_url = state.get("initial_url", "N/A")

    # Increment iteration count
    current_iteration = iteration_count + 1
    logger.info(
        f"--- Planning Step: Iteration {current_iteration}/{max_iterations} ---"
    )

    # Check termination conditions
    if error_message:
        logger.warning(
            f"Error detected in previous step: {error_message}. Finishing research."
        )
        return {
            "next_action": "finish",
            "iteration_count": current_iteration,
        }  # Go straight to finish on error
    if current_iteration > max_iterations:
        logger.warning(
            f"Max iterations ({max_iterations}) reached. Finishing research."
        )
        return {"next_action": "finish", "iteration_count": current_iteration}
    if "all key fields are present" in missing_info:
        logger.success("Analysis indicates profile is complete. Finishing research.")
        return {"next_action": "finish", "iteration_count": current_iteration}

    # --- Prepare for LLM Planner Call ---
    # Placeholder for getting LLM instance - adjust based on graph setup
    llm_instance: Optional[BaseChatModel] = state.get("llm_instance_placeholder")
    if not llm_instance:
        logger.error("LLM instance not found for planning node.")
        return {
            "error_message": "LLM unavailable for planning.",
            "next_action": "error",
            "iteration_count": current_iteration,
        }

    # Prepare profile summary for prompt (avoid sending huge objects)
    profile_summary = "Profile draft is currently empty."
    if profile_draft and isinstance(profile_draft, CompanyProfileSchema):
        # Create a concise summary, maybe just key fields or dump with limited depth
        try:
            profile_summary_dict = profile_draft.model_dump(exclude_unset=True)
            # Simple summary for now, could be more elaborate
            profile_summary = f"Current Profile Draft Summary:\n{profile_summary_dict}"
        except Exception:
            profile_summary = "Could not serialize current profile draft."

    # Build the prompt for the planner LLM
    prompt = f"""
You are an automated research planner. Your goal is to decide the next step to gather information needed to complete a company profile.

Target Website: {initial_url}

Current Profile Status:
{profile_summary}

Analysis of Missing Information:
{missing_info}

Based on the missing information, decide the *single best next action* to take. Your options are:
1.  'scrape': If you believe specific pages on the *target website* likely contain the missing info (e.g., a '/contact' page for phone number, '/about' for description, '/products' for offerings). Provide the *full URLs* to scrape.
2.  'search': If the information is unlikely to be found on the known website pages or requires external verification (e.g., specific operating hours not listed, reviews, news). Provide specific, targeted search queries.
3.  'finish': If the profile seems reasonably complete with the available information, or if further scraping/searching is unlikely to yield useful results for the *specific missing fields*.

Use the 'PlannerDecisionSchema' to structure your response. Provide *only* the JSON object.
Choose 'scrape' OR 'search', not both. If choosing 'scrape', provide URLs. If choosing 'search', provide queries. If choosing 'finish', leave URLs and queries empty.
"""

    logger.debug("Sending planning request to LLM...")

    # --- Call LLM using Trustcall ---
    try:
        planner_agent = create_extractor(
            llm=llm_instance,
            tools=[PlannerDecisionSchema],
            tool_choice=PlannerDecisionSchema.__name__,
        )
        result: Dict[str, Any] = await planner_agent.ainvoke(prompt)

        responses = result.get("responses")
        if isinstance(responses, list) and len(responses) > 0:
            decision = responses[0]
            if isinstance(decision, PlannerDecisionSchema):
                logger.info(
                    f"Planner LLM decided next action: '{decision.next_action}'. Reasoning: {decision.reasoning or 'N/A'}"
                )

                # Prepare state updates based on decision
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
                    "error_message": None,  # Clear previous non-fatal errors if planning succeeds
                }
                return updates
            else:
                logger.error(f"Planner LLM returned unexpected type: {type(decision)}")
                error_msg = "Planner LLM output failed validation."
        else:
            logger.error(
                f"Planner LLM call failed. Unexpected result structure: {result}"
            )
            error_msg = "Planner LLM call failed."

    except Exception as e:
        logger.exception(f"Error during planner LLM call: {e}")
        error_msg = f"Planner LLM error: {e}"

    # If LLM call failed or returned invalid data
    return {
        "error_message": error_msg,
        "next_action": "error",
        "iteration_count": current_iteration,
    }


# --- Node: finish_research ---


async def finish_research(state: ResearchState) -> Dict[str, Any]:
    """
    Final node: Saves the completed profile_draft to the database.

    Args:
        state: The final graph state. Requires 'db_session_factory' in config.

    Returns:
        An empty dictionary (no further state updates needed).
    """
    logger.info("--- Finishing Research Graph ---")
    profile_draft: Optional[CompanyProfileSchema] = state.get("profile_draft")
    account_id: Optional[UUID] = state.get("account_id")
    error_message = state.get("error_message")
    final_iteration = state.get("iteration_count", "N/A")

    if error_message:
        logger.error(
            f"Research finished due to error after {final_iteration} iterations: {error_message}"
        )
        # Decide if we still save the potentially incomplete draft or not
        # For now, let's attempt to save even if there was an error during planning/execution
        # but log it clearly.

    if not account_id:
        logger.critical(
            "Cannot save profile: account_id is missing in the final state."
        )
        return {}  # Cannot proceed

    if not profile_draft or not isinstance(profile_draft, CompanyProfileSchema):
        logger.warning(
            f"No valid profile draft available to save for account {account_id} after {final_iteration} iterations."
        )
        # Potentially save a status indicating failure? For now, just log.
        return {}  # Nothing to save

    # --- Get DB Session Factory from Config ---
    # This assumes the factory is passed in the 'configurable' part of the invoke call
    # Example: graph.ainvoke(..., config={"configurable": {"db_session_factory": my_factory}})
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = state.get(
        "db_session_factory"
    )  # Needs correct injection!

    if not db_session_factory or not REPO_AVAILABLE:
        logger.error(
            "Database session factory or repository functions unavailable. Cannot save profile."
        )
        # Log the profile draft data that couldn't be saved for debugging
        try:
            logger.error(
                f"Profile draft data not saved: {profile_draft.model_dump_json(indent=2)}"
            )
        except Exception:
            logger.error("Could not serialize profile draft for logging.")
        return {}

    # --- Save to Database ---
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
                        f"Updating existing profile (ID: {existing_profile.id}) with final draft."
                    )
                    update_data = profile_draft.model_dump(
                        exclude_unset=False, exclude={"id"}
                    )  # Save all fields
                    saved_profile = await update_profile(
                        db=db, db_profile=existing_profile, profile_in=update_data
                    )
                else:
                    logger.info(
                        f"Creating new profile for account {account_id} with final draft."
                    )
                    saved_profile = await create_profile(
                        db=db, profile_in=profile_draft, account_id=account_id
                    )

                if saved_profile:
                    profile_id = getattr(saved_profile, "id", None)
                    await db.commit()  # Commit the transaction
                    saved_successfully = True
                    logger.success(
                        f"Successfully saved final profile to DB. Profile ID: {profile_id}"
                    )
                else:
                    logger.error(
                        "Repository create/update returned None. Rolling back."
                    )
                    await db.rollback()

            except Exception as db_exc:
                logger.exception(
                    f"Database error during final save for account {account_id}: {db_exc}. Rolling back."
                )
                await db.rollback()

    except Exception as session_exc:
        logger.exception(
            f"Error obtaining/managing DB session during final save: {session_exc}"
        )

    if not saved_successfully:
        logger.error(f"Failed to save final profile draft for account {account_id}.")
        # Log the data again on failure
        try:
            logger.error(
                f"Profile draft data not saved: {profile_draft.model_dump_json(indent=2)}"
            )
        except Exception:
            logger.error("Could not serialize profile draft for logging.")

    # This node typically doesn't update the state further, it's terminal.
    return {}
