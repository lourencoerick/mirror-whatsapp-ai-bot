# backend/app/services/search/client.py

import os
from typing import List, Dict, Optional
from loguru import logger
import asyncio

# Ensure tavily-python is installed: pip install tavily-python
try:
    from tavily import TavilyClient

    TAVILY_AVAILABLE = True
except ImportError:
    logger.warning(
        "TavilyClient not found. Search functionality will be disabled. pip install tavily-python"
    )
    TAVILY_AVAILABLE = False

    class TavilyClient:  # Dummy
        def __init__(self, api_key: str):
            pass

        def search(self, query: str, **kwargs) -> Dict:
            return {"results": []}


# Load API key from environment variables
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class SearchResult(Dict):
    """Simple structure for search results (can be expanded)."""

    title: Optional[str]
    url: Optional[str]
    content: Optional[str]
    score: Optional[float]
    raw_content: Optional[str]


class SearchService:
    """
    Provides functionality to search using Tavily API.
    """

    def __init__(self, api_key: Optional[str] = TAVILY_API_KEY):
        """
        Initializes the SearchService.

        Args:
            api_key: The Tavily API key. Reads from TAVILY_API_KEY env var if not provided.

        Raises:
            ValueError: If Tavily library is not available or API key is missing.
        """
        if not TAVILY_AVAILABLE:
            raise ValueError("TavilyClient library is not installed.")
        if not api_key:
            raise ValueError(
                "Tavily API key is missing. Set TAVILY_API_KEY environment variable."
            )

        self.client = TavilyClient(api_key=api_key)
        logger.info("Tavily SearchService initialized.")

    async def search(
        self,
        query: str,
        search_depth: str = "basic",  # Or "advanced"
        max_results: int = 5,
        include_raw_content: bool = False,  # Raw content can be large
        include_domains: List[str] = [],
    ) -> List[SearchResult]:
        """
        Performs a search using the Tavily API.

        Args:
            query: The search query string.
            search_depth: Tavily search depth ('basic' or 'advanced').
            max_results: Maximum number of results to return.
            include_raw_content: Whether to include raw page content in results.

        Returns:
            A list of SearchResult dictionaries. Returns empty list on error.
        """
        logger.info(
            f"Performing Tavily search for query: '{query}' (depth: {search_depth}, max_results: {max_results})"
        )
        try:
            # Tavily client runs synchronously, use to_thread
            search_result_dict = await asyncio.to_thread(
                self.client.search,
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_raw_content=include_raw_content,
                include_domains=include_domains,
                # include_answer=False, # Optionally exclude Tavily's generated answer
            )
            # Extract results in a consistent format
            results = search_result_dict.get("results", [])
            formatted_results: List[SearchResult] = [
                SearchResult(
                    title=r.get("title"),
                    url=r.get("url"),
                    content=r.get("content"),  # This is the snippet/summary
                    score=r.get("score"),
                    raw_content=r.get(
                        "raw_content"
                    ),  # Only present if include_raw_content=True
                )
                for r in results
            ]
            logger.info(
                f"Tavily search returned {len(formatted_results)} results for query: '{query}'"
            )
            return formatted_results

        except Exception as e:
            logger.exception(f"Error during Tavily search for query '{query}': {e}")
            return []


# --- Optional: Simple async function wrapper ---
# This can be useful if you don't want to manage the SearchService instance everywhere
async def perform_tavily_search(query: str, **kwargs) -> List[SearchResult]:
    """Convenience function to perform a Tavily search."""
    if not TAVILY_API_KEY:
        logger.error("Tavily API key not configured.")
        return []
    try:
        service = SearchService(api_key=TAVILY_API_KEY)
        return await service.search(query, **kwargs)
    except ValueError as e:  # Catch init errors
        logger.error(f"Failed to initialize SearchService: {e}")
        return []
