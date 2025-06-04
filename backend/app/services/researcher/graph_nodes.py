# backend/app/services/researcher/graph_nodes.py

import tldextract
import asyncio
from typing import Dict, Any, List, Optional, Set, Type
from loguru import logger
from uuid import UUID
from pydantic import BaseModel
from urllib.parse import urlparse

# Import state and schemas
from .graph_state import (
    ResearchState,
    LinkInfo,
    PlannerDecisionSchema,
    SCHEMA_AVAILABLE,
)


# Import web loader
try:
    from .web_loader_simple import fetch_and_extract_text_and_links

    SIMPLE_LOADER_AVAILABLE = True
except ImportError:
    SIMPLE_LOADER_AVAILABLE = False
    logger.error("Simple web loader 'fetch_and_extract_text_and_links' not found.")

    async def fetch_and_extract_text_and_links(*args, **kwargs) -> Optional[str]:
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
        "newly_found_links": [],
        "intial_url_found_links": [],
        "action_history": [],
        "search_attempted": False,
        # max_iterations should be passed in the initial state if needed
    }
    logger.debug("Initialized research state.")
    return updates


# --- Node: scrape_website ---
async def scrape_website(state: ResearchState) -> Dict[str, Any]:
    """
    Fetches content and links from URLs specified in the state.
    Updates scraped_data, visited_urls, and newly_found_links. Clears urls_to_scrape.
    """
    if not SIMPLE_LOADER_AVAILABLE:
        logger.error("Simple web loader unavailable.")
        return {"error_message": "Web loader unavailable.", "next_action": "error"}

    urls_to_fetch = state.get("urls_to_scrape", [])
    initial_url = state.get("initial_url")
    visited_urls = state.get("visited_urls", set())
    scraped_data = state.get("scraped_data", {})
    # Initialize list for newly found links in this cycle
    all_links_found_this_cycle: List[LinkInfo] = []

    found_links_key_to_update = "newly_found_links"
    if urls_to_fetch:
        if initial_url == urls_to_fetch[0]:
            found_links_key_to_update = "intial_url_found_links"

    if not urls_to_fetch:
        logger.info("No URLs provided in 'urls_to_scrape'. Skipping scraping.")
        # Clear list and return empty found links
        return {"urls_to_scrape": [], "newly_found_links": []}

    new_urls_to_fetch = [url for url in urls_to_fetch if url not in visited_urls]
    if not new_urls_to_fetch:
        logger.info("All URLs in 'urls_to_scrape' have already been visited.")
        # Clear list and return empty found links
        return {"urls_to_scrape": [], "newly_found_links": []}

    logger.info(f"Fetching {len(new_urls_to_fetch)} new URLs...")
    # Call the function that returns text AND links
    tasks = [fetch_and_extract_text_and_links(url=url) for url in new_urls_to_fetch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    newly_visited = set()
    successful_scrapes = 0
    failed_scrapes = 0
    for i, result in enumerate(results):
        url = new_urls_to_fetch[i]
        newly_visited.add(url)

        if isinstance(result, Exception):
            logger.error(f"Error scraping URL {url}: {result}")
            failed_scrapes += 1
        elif isinstance(result, tuple) and len(result) == 2:
            extracted_text, found_links = result
            has_text = False
            if extracted_text:
                scraped_data[url] = extracted_text
                logger.success(f"Scraped text from {url}")
                successful_scrapes += 1
                has_text = True
            else:
                logger.warning(f"No text content returned for URL: {url}")

            if found_links:
                all_links_found_this_cycle.extend(found_links)
                logger.debug(f"Found {len(found_links)} links on {url}")

            # Count as failure only if neither text nor links were found
            if not has_text and not found_links:
                failed_scrapes += 1
        else:
            logger.error(f"Unexpected result format from fetcher for {url}: {result}")
            failed_scrapes += 1

    action_summary = (
        f"Scrape attempt finished. URLs attempted: {len(new_urls_to_fetch)}. "
        f"Successful text: {successful_scrapes}. Failed/No Content: {failed_scrapes}. "
        f"Links found: {len(all_links_found_this_cycle)}."
    )
    logger.info(action_summary)

    # --- Deduplicate links found across all pages in this cycle ---
    unique_links_dict: Dict[str, LinkInfo] = {
        link.url: link for link in all_links_found_this_cycle
    }
    unique_new_links = list(unique_links_dict.values())
    logger.info(
        f"Found {len(unique_new_links)} unique internal links in this scraping cycle."
    )
    # --- End Deduplication ---

    updates = {
        "scraped_data": scraped_data,
        "visited_urls": newly_visited,
        "urls_to_scrape": [],  # Clear processed list
        found_links_key_to_update: unique_new_links,
        "error_message": state.get("error_message"),
        "action_history": [action_summary],
    }
    logger.info(
        f"Finished scraping. Visited: {len(newly_visited)}. "
        f"Total scraped pages with text: {len(scraped_data)}."
    )
    return updates


# --- Node: perform_search ---
async def perform_search(state: ResearchState) -> Dict[str, Any]:
    """
    Executes search queries specified in the state.
    Updates search_results, last_action_summary, and sets search_attempted flag.
    Clears search_queries.
    """
    search_attempted_flag = state.get("search_attempted", False)

    initial_url = state.get("initial_url", False)
    ext = tldextract.extract(initial_url)
    registrable = f"{ext.domain}.{ext.suffix}"
    include_domains = [registrable, f"*.{registrable}"]

    registrable = f"{ext.domain}.{ext.suffix}"
    if not SEARCH_AVAILABLE:
        summary = "Search failed: Service unavailable."
        logger.error(summary)
        # Preserve existing search_attempted state on error
        return {
            "error_message": "Search unavailable.",
            "next_action": "error",
            "action_history": [summary],
            "search_attempted": search_attempted_flag,
        }

    queries = state.get("search_queries", [])
    search_results_agg = state.get("search_results", {})

    if not queries:
        summary = "Skipped search: No queries provided."
        logger.info(summary)
        # Preserve existing search_attempted state when skipping
        return {
            "search_queries": [],
            "action_history": [summary],
            "search_attempted": search_attempted_flag,
        }

    logger.info(f"Starting search for {len(queries)} queries: {queries}")
    search_tasks = [
        perform_tavily_search(query=q, max_results=3, include_domains=include_domains)
        for q in queries
    ]
    results_list = await asyncio.gather(*search_tasks, return_exceptions=True)

    successful_searches = 0
    failed_searches = 0
    total_results = 0
    errors_encountered = False

    for i, result in enumerate(results_list):
        query = queries[i]
        if isinstance(result, Exception):
            logger.error(f"Error searching '{query}': {result}")
            search_results_agg[query] = []
            failed_searches += 1
            errors_encountered = True
        elif isinstance(result, list):
            logger.success(f"Search OK for '{query}'. Found {len(result)}")
            search_results_agg[query] = result
            successful_searches += 1
            total_results += len(result)
        else:
            logger.warning(
                f"Unexpected search result type for '{query}': {type(result)}"
            )
            search_results_agg[query] = []
            failed_searches += 1
            errors_encountered = True

    action_summary = (
        f"Search attempt finished. Queries: {len(queries)}. "
        f"Successful: {successful_searches}. Failed: {failed_searches}. "
        f"Total results found: {total_results}."
    )
    logger.info(action_summary)

    # --- Set search_attempted to True IF at least one search was tried ---
    # We set it even if there were errors, as an *attempt* was made.
    if queries:
        search_attempted_flag = True

    updates = {
        "search_results": search_results_agg,
        "search_queries": [],  # Clear processed list
        "error_message": state.get("error_message"),  # Preserve previous error
        "action_history": [action_summary],
        "search_attempted": search_attempted_flag,  # Return the updated flag
    }
    return updates


# --- Node: update_profile ---
async def update_company_profile(state: ResearchState, config: dict) -> Dict[str, Any]:
    """
    Combines context, uses LLM extractor to get new info, and then uses
    another LLM call to intelligently merge the new info with the existing
    profile_draft. Requires 'llm_instance' in the config.
    Clears scraped_data and search_results.
    """
    if not all([EXTRACTOR_AVAILABLE, SCHEMA_AVAILABLE, TRUSTCALL_AVAILABLE]):
        logger.error("Update components (Extractor, Schema, Trustcall) unavailable.")
        return {
            "error_message": "Update components unavailable.",
            "next_action": "error",
        }

    scraped_data = state.get("scraped_data", {})
    search_results = state.get("search_results", {})
    current_profile_draft = state.get("profile_draft")

    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_instance"
    )
    if not llm_instance:
        logger.error("LLM instance not found in config for update_profile node.")
        return {"error_message": "LLM unavailable for update.", "next_action": "error"}

    # --- Combine Context ---
    combined_parts = []
    has_search_results = bool(search_results)
    if scraped_data:
        combined_parts.append("--- Website Content ---")
        for url, content in scraped_data.items():
            combined_parts.append(
                f"\n[Source: {url}]\n{content[:10000]}"
            )  # Limit content
        combined_parts.append("--- End Website Content ---")

    if search_results:
        combined_parts.append("\n\n--- Search Results ---")
        for query, results in search_results.items():
            combined_parts.append(f"\n[Query: {query}]")
            result_snippets = [
                f"- Title: {res.get('title', 'N/A')}\n  URL: {res.get('url', 'N/A')}\n  Snippet: {res.get('content', 'N/A')}\n"
                for res in results
            ]
            combined_parts.append("\n".join(result_snippets))
        combined_parts.append("--- End Search Results ---")

    if not combined_parts:
        logger.info("No new data to process. Skipping profile update.")
        return {
            "scraped_data": {},
            "search_results": {},
            "combined_context": None,
            "profile_draft": current_profile_draft,  # Preserve draft
        }

    combined_context = "\n".join(combined_parts)
    logger.info(
        f"Combined context generated. Length: {len(combined_context)}. Extracting new info..."
    )

    # --- Call Initial Extractor ---
    try:

        newly_extracted_profile = await extract_profile_from_text(
            website_text=combined_context,
            llm=llm_instance,
            target_schema=CompanyProfileSchema,
        )
        logger.debug(f"New profile extracted: {newly_extracted_profile}")
    except Exception as e:
        logger.exception(f"Error calling extract_profile_from_text: {e}")
        return {
            "error_message": f"Extractor failed: {e}",
            "next_action": "error",
            "scraped_data": {},
            "search_results": {},
            "combined_context": combined_context,
            "profile_draft": current_profile_draft,
        }

    # --- Merge Logic ---
    updated_profile_draft = current_profile_draft

    if not newly_extracted_profile:
        logger.warning("Initial extractor returned no profile. Keeping existing draft.")
        updates = {
            "profile_draft": current_profile_draft,
            "scraped_data": {},
            "search_results": {},
            "combined_context": combined_context,
            "error_message": state.get("error_message"),
        }
    elif not current_profile_draft:

        logger.info("First successful extraction. Using as initial profile draft.")
        updated_profile_draft = newly_extracted_profile
        updates = {
            "profile_draft": updated_profile_draft,
            "scraped_data": {},
            "search_results": {},
            "combined_context": combined_context,
            "error_message": state.get("error_message"),
        }
    else:
        # --- Perform LLM Merge ---
        logger.info("Performing LLM merge of current draft and new extraction...")
        try:
            search_warning_for_merger = ""
            if search_results:
                search_warning_for_merger = (
                    "\n\n**Important Context:** The 'Newly Extracted Information' below was generated using a combination of website content "
                    "AND external search engine results. Search results might be less reliable or outdated. "
                    "When merging, prioritize information clearly stated on the company's website (likely reflected in the 'Existing Profile Draft' or the website portions of the new extraction) "
                    "over potentially conflicting information from search snippets, especially for critical details like pricing, specific features, or contact info. Use search results mainly to fill gaps."
                )

            logger.warning(f"Warning: {search_warning_for_merger}")
            current_draft_json = current_profile_draft.model_dump_json(indent=2)
            new_extraction_json = newly_extracted_profile.model_dump_json(
                indent=2, exclude_unset=True
            )

            merge_prompt = f"""
            You are an expert data integrator. Your task is to merge two versions of a company profile into a single, comprehensive, and accurate profile.

            **Existing Profile Draft:**
            ```json
            {current_draft_json}
            ```
            ---

            {search_warning_for_merger}
            Newly Extracted Information (from latest research):
            ```json
            {new_extraction_json}
            ```
            
            Instructions:
                1. Combine the information intelligently into a single, final profile, considering the source context described above if applicable.
                2. Prioritize values that are most accurate, complete, and likely up-to-date, considering the source context described above if applicable.
                3. If 'Newly Extracted' provides better/more detail for a field empty in 'Existing', use the new value, , considering the source context described above if applicable.
                4. If 'Newly Extracted' is missing a value present in 'Existing', keep the existing value.
                5. For lists (like 'offering_overview', etc.): Combine items uniquely. For 'offering_overview', merge items with the same name intelligently (combine features, prefer longer descriptions, prefer existing price/link if new one is missing or less specific), considering the source context described above if applicable.
                6. Ensure the final output strictly adheres to the CompanyProfileSchema format.
            """
            merge_agent = create_extractor(
                llm=llm_instance,
                tools=[CompanyProfileSchema],
                tool_choice=CompanyProfileSchema.__name__,
            )
            merge_result = await merge_agent.ainvoke(merge_prompt)
            merge_responses = merge_result.get("responses")
            if isinstance(merge_responses, list) and len(merge_responses) > 0:
                merged_profile = merge_responses[0]
                if isinstance(merged_profile, CompanyProfileSchema):
                    logger.success("LLM merge successful.")
                    updated_profile_draft = merged_profile
                else:
                    logger.error(
                        f"LLM merge returned unexpected type: {type(merged_profile)}. Keeping previous draft."
                    )
            else:
                logger.error(
                    f"LLM merge call failed or returned no response. Keeping previous draft. Result: {merge_result}"
                )

        except Exception as merge_err:
            logger.exception(
                f"Error during LLM merge process: {merge_err}. Keeping previous draft."
            )

        # Prepare updates after merge attempt
        updates = {
            "profile_draft": updated_profile_draft,
            "scraped_data": {},
            "search_results": {},
            "combined_context": combined_context,
            "error_message": state.get("error_message"),
        }
        # --- End LLM Merge ---

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
    """
    Decides the next action. Requires 'llm_instance' in config.
    Clears last_action_summary and newly_found_links after planning.
    """
    if not TRUSTCALL_AVAILABLE or not LANGCHAIN_AVAILABLE:
        logger.error("Planning components unavailable.")
        return {
            "error_message": "Planning components unavailable.",
            "next_action": "error",
        }

    # --- Get State ---
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 7)
    error_message = state.get("error_message")
    missing_info = state.get("missing_info_summary", "Analysis not available.")
    profile_draft = state.get("profile_draft")
    initial_url = state.get("initial_url", "N/A")
    action_history = state.get("action_history", [])
    visited_urls = state.get("visited_urls", set())
    search_attempted = state.get("search_attempted", True)
    newly_found_links_all = state.get("newly_found_links", [])
    intial_url_found_links_all = state.get("intial_url_found_links", [])
    current_iteration = iteration_count + 1

    logger.info(
        f"--- Planning Step: Iteration {current_iteration}/{max_iterations} ---"
    )
    logger.info(f"Last taken actions: {action_history}")

    # --- Check Termination Conditions ---
    updates_if_finishing = {
        "iteration_count": current_iteration,
        "newly_found_links": [],
    }
    if error_message:
        logger.warning(f"Error detected: {error_message}. Finishing.")
        return {**updates_if_finishing, "next_action": "finish"}
    if current_iteration > max_iterations:
        logger.warning("Max iterations reached. Finishing.")
        return {**updates_if_finishing, "next_action": "finish"}
    # Keep this check, but LLM prompt prioritizes offerings
    # if "all key fields are present" in missing_info:
    #     logger.success("Analysis suggests profile complete. Finishing.")
    #     return {**updates_if_finishing, "next_action": "finish"}

    # --- Logic to Force Search (Example: after iteration 2 if not searched) ---
    force_search = False
    if current_iteration > 8 and not search_attempted:
        profile_has_basics = bool(
            profile_draft
            and profile_draft.company_name
            and profile_draft.business_description
        )
        if profile_has_basics:
            force_search = True
            logger.info(
                f"Forcing 'search' action (Iteration {current_iteration}, Search Attempted: {search_attempted}, Basics Found: {profile_has_basics})."
            )

    if force_search:
        company_name = (
            profile_draft.company_name if profile_draft else profile_draft.website
        )
        forced_queries = [
            f"{company_name} produtos e serviços",
            f"{company_name} planos e preço",
            f"{company_name} contato para informações",
        ]
        # Return only fields to be overwritten
        return {
            "next_action": "search",
            "search_queries": forced_queries,
            "iteration_count": current_iteration,
            "urls_to_scrape": [],
            "error_message": None,
        }
    # --- Get LLM ---
    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_instance"
    )
    if not llm_instance:
        logger.error("LLM instance not found in config for planning node.")
        return {
            **updates_if_finishing,
            "error_message": "LLM unavailable for planning.",
            "next_action": "error",
        }

    # --- Prepare Prompt ---
    profile_summary = "Profile draft is currently empty."
    if profile_draft and isinstance(profile_draft, CompanyProfileSchema):
        try:
            profile_summary = (
                f"Current Profile Draft Summary:\n"
                f"{profile_draft.model_dump(exclude_unset=True, exclude={'combined_context', 'scraped_data', 'search_results'})}"
            )
        except Exception:
            profile_summary = "Could not serialize profile draft."

    links_summary = "No new links found in the last scraping cycle."

    unvisited_candidate_links = [
        link for link in newly_found_links_all if link.url not in visited_urls
    ]

    intial_url_found_links = [
        link for link in intial_url_found_links_all if link.url not in visited_urls
    ]
    logger.debug(
        f"Found {len(unvisited_candidate_links)} unvisited candidate links out of {len(newly_found_links_all)} total."
    )

    initial_url_links_summary = "No links found in the target website."
    if intial_url_found_links:
        links_list_str = "\n".join(
            [
                f"- URL: {link.url} (Anchor Text: '{link.anchor_text or 'N/A'}')"
                for link in intial_url_found_links[:30]
            ]
        )
        initial_url_links_summary = f"Potential URLs found in the first target URL (limit 30):\n{links_list_str}"
        if len(intial_url_found_links) > 30:
            initial_url_links_summary += "\n..."
    logger.debug(f"{initial_url_links_summary}")
    if unvisited_candidate_links:
        links_list_str = "\n".join(
            [
                f"- URL: {link.url} (Anchor Text: '{link.anchor_text or 'N/A'}')"
                for link in unvisited_candidate_links[:20]
            ]
        )
        links_summary = f"Potential URLs found in the last scraping cycle (limit 20):\n{links_list_str}"
        if len(unvisited_candidate_links) > 20:
            links_summary += "\n..."

    history_log = "No actions taken yet."
    if action_history:
        history_to_show = action_history[-5:]  # Show last 5 actions
        history_log = "History of Recent Actions Attempted:\n" + "\n".join(
            history_to_show
        )

    prompt = f"""
You are an automated research planner AI. Your objective is to strategically decide the next step to build a **complete and accurate** company profile using information from a website and external search.

**Overall Goal:** Create a high-quality company profile suitable for an AI sales assistant.

**Key Priorities:**
1.  **Offerings (Primary):** Ensure the profile accurately lists and details the company's specific **products, services, and pricing/plans**. This is the most critical information.
2.  **Contact/FAQ (Secondary):** Find reliable contact methods (email, phone) and FAQ information if missing.

**Decision Factors:** Base your decision on the following context, prioritizing the goals above. Analyze the action history to avoid repeating failed attempts. Consider the likely business type (e.g., online service vs. physical store - an online service might not have 'delivery options').

**Context Provided:**
*   Target Website: {initial_url}
*   {initial_url_links_summary}
*   Current Profile Status Summary:
{profile_summary}
*   Analysis of Missing Information: {missing_info}
*   {history_log}
*   {links_summary}

Before decide to 'finish', make sure that in the 'History of Recent Actions Attempted', there are at least two Sucessful Scrape Actions. And if it makes sense, explore a bit more the links found on the target url.

**Instructions:** Choose the *single best next action* from the options below.

**Action Options:**

1.  **'scrape'**:
    *   **Choose if:** Specific *unvisited candidate URLs* or common paths (like `/contact`, `/about`, `/products`, `/services`, `/pricing`, `/faq`) seem highly likely to contain the missing information, **especially offering details, contact info, or FAQs**.
    *   **Check History:** Do NOT suggest URLs that recently failed (check history) unless there's a strong reason.
    *   **Output:** Provide the *full URLs* to scrape in the `urls_to_scrape` field.

2.  **'search'**:
    *   **Choose if:**
        *   Website scraping seems unlikely to yield the missing info (especially detailed offerings/pricing).
        *   Previous scraping attempts for specific info failed (check history).
        *   External validation or data is needed (e.g., operating hours, specific contacts, reviews).
    *   **Check History:** Do NOT repeat failed search queries for the same missing information.
    *   **Output:** Provide specific, targeted search queries in the `search_queries` field (e.g., "[Company Name] product list", "[Company Name] service pricing", "[Company Name] contact phone number").

3.  **'finish'**:
    *   **Choose ONLY if:**
        *   The profile seems reasonably complete, **especially regarding offerings and contact info**.
        *   The action history shows that targeted scraping AND/OR searching for the key missing information have already been attempted.
        *   Further actions seem unlikely to yield significant improvements based on the available context and history.
    *   **Output:** Leave `urls_to_scrape` and `search_queries` empty.

**Output Format:**
Use the 'PlannerDecisionSchema'. Respond *only* with the valid JSON object.
"""
    logger.debug("Sending planning request to LLM...")

    # --- Call LLM ---

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
                    "error_message": None,
                    "newly_found_links": [],
                }

                if (
                    decision.next_action == "finish"
                    and "Missing or empty fields identified" in missing_info
                ):
                    logger.warning(
                        f"Planner decided finish, but analysis shows missing: {missing_info}"
                    )
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
        "newly_found_links": [],
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
