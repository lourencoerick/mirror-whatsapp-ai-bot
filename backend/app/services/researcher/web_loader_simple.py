# backend/app/services/researcher/web_loader_simple.py

import asyncio
from typing import Optional, Dict, Tuple, List  # Added List
from urllib.parse import urljoin, urlparse  # Added urljoin, urlparse

from loguru import logger
import sys

# Import LinkInfo schema from graph_state or define it here
try:
    # Assuming graph_state is in the same directory or accessible path
    from .graph_state import LinkInfo
except ImportError:
    from pydantic import BaseModel, Field  # Fallback definition

    class LinkInfo(BaseModel):
        url: str = Field(...)
        anchor_text: Optional[str] = Field(None)


# --- Dependencies ---
try:
    import requests
    from bs4 import BeautifulSoup

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    logger.error("Required libraries 'requests' or 'beautifulsoup4' not found.")
    BEAUTIFULSOUP_AVAILABLE = False

    class BeautifulSoup:
        pass

    class requests:
        pass


# --- Configuration Defaults ---
DEFAULT_SINGLE_PAGE_TIMEOUT = 20
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# --- Helper Functions ---


def _validate_url(url: str) -> bool:
    # ... (remains the same) ...
    if not url or not url.startswith(("http://", "https://")):
        logger.warning(f"Invalid or missing URL provided: {url}")
        return False
    return True


def _clean_extracted_text(text: str) -> str:
    # ... (remains the same) ...
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


# --- Added Link Helpers (from llm_guided loader) ---
def _get_base_domain(netloc: str) -> str:
    parts = netloc.split(".")
    if len(parts) <= 2:
        return netloc
    return ".".join(parts[-2:])


def _is_internal_link_allow_subdomains(base_netloc: str, link_url: str) -> bool:
    try:
        link_netloc = urlparse(link_url).netloc
        if not link_netloc:
            return True
        base_domain = _get_base_domain(base_netloc)
        link_domain = _get_base_domain(link_netloc)
        return base_domain == link_domain
    except Exception:
        return False


def _clean_link(base_url: str, link: str) -> Optional[str]:
    try:
        absolute_link = urljoin(base_url, link.strip())
        parsed_link = urlparse(absolute_link)
        if (
            parsed_link.scheme not in ["http", "https"]
            or parsed_link.fragment
            or parsed_link.scheme in ["javascript", "tel", "mailto"]
        ):
            return None
        clean_url = parsed_link._replace(fragment="").geturl()
        return clean_url
    except Exception:
        return None


# --- End Added Link Helpers ---


def _extract_text_and_links_simple(
    html_content: str, base_url: str
) -> Tuple[str, List[LinkInfo]]:
    """Extracts main text content and internal links from HTML."""
    if not BEAUTIFULSOUP_AVAILABLE:
        return "", []
    text = ""
    links = []
    try:
        soup = BeautifulSoup(html_content, "lxml")
        for script_or_style in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form"]
        ):
            script_or_style.decompose()
        text = soup.get_text(separator="\n", strip=True)

        # Extract internal links (allowing subdomains)
        base_netloc = urlparse(base_url).netloc
        processed_urls = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            cleaned_link = _clean_link(base_url, href)

            # Use the subdomain-allowing check
            # is_whatsapp = any(
            #     domain in cleaned_link for domain in ["wa.me", "api.whatsapp.com"]
            # )

            if (
                cleaned_link
                and cleaned_link not in processed_urls
                and _is_internal_link_allow_subdomains(base_netloc, cleaned_link)
            ):
                anchor_text = a_tag.get_text(strip=True)
                links.append(LinkInfo(url=cleaned_link, anchor_text=anchor_text))
                processed_urls.add(cleaned_link)

    except Exception as e:
        logger.error(f"Error during BeautifulSoup parsing or link extraction: {e}")
        # Return whatever was extracted so far, or empty if error was early
        return text, links

    return text, links


def _fetch_page_content_sync(
    url: str, headers: Dict[str, str], timeout: int
) -> Optional[str]:
    try:
        response = requests.get(
            url, headers=headers, timeout=timeout, allow_redirects=True
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            logger.debug(f"Skipping non-HTML content at {url} (type: {content_type})")
            return None
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning(
                f"UTF-8 decode failed for {url}, using apparent: {response.apparent_encoding}"
            )
            return response.text
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url} after {timeout}s")
        return None
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, "status_code", "N/A")
        logger.warning(f"Failed fetch {url} (Status: {status_code}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None


# --- Core Function (MODIFIED) ---


async def fetch_and_extract_text_and_links(  # Renamed function
    url: str,
    request_timeout: int = DEFAULT_SINGLE_PAGE_TIMEOUT,
    request_headers: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], List[LinkInfo]]:  # Modified return type
    """
    Fetches content from a single URL, extracts cleaned text and internal links.

    Args:
        url: The URL of the web page to load.
        request_timeout: Timeout in seconds for the fetch operation.
        request_headers: Headers to use for the HTTP request.

    Returns:
        A tuple containing:
            - str: The extracted and cleaned text content, or None on failure.
            - List[LinkInfo]: A list of found internal links.
    """
    if not BEAUTIFULSOUP_AVAILABLE:
        logger.error("Dependencies (requests, beautifulsoup4) not available.")
        return None, []
    if not _validate_url(url):
        return None, []

    headers = (
        request_headers if request_headers is not None else DEFAULT_REQUEST_HEADERS
    )
    logger.info(f"Attempting to fetch/extract text & links from URL: {url}")

    html_content: Optional[str] = None
    extracted_text: Optional[str] = None
    links: List[LinkInfo] = []

    try:
        # Fetch HTML content in thread
        html_content = await asyncio.wait_for(
            asyncio.to_thread(_fetch_page_content_sync, url, headers, request_timeout),
            timeout=float(request_timeout + 5),  # Add buffer
        )

        if html_content:
            # Extract text and links using BeautifulSoup
            raw_text, links = _extract_text_and_links_simple(html_content, url)

            if raw_text.strip():
                extracted_text = _clean_extracted_text(raw_text)
                logger.success(
                    f"Successfully fetched/extracted text ({len(extracted_text)} chars) and {len(links)} links from {url}."
                )
            else:
                logger.warning(
                    f"No significant text extracted from {url}, but found {len(links)} links."
                )
                # Return None for text, but still return found links
                extracted_text = None
        else:
            # Fetch function already logged the reason
            logger.warning(
                f"Fetch failed or returned no HTML for {url}. No text or links extracted."
            )
            return None, []  # Return None and empty list

    except asyncio.TimeoutError:
        logger.error(f"Overall operation timeout fetching/processing {url}")
        return None, []
    except Exception as e:
        logger.exception(f"Unexpected error during fetch/extract for {url}: {e}")
        return None, []

    # Return the extracted text (or None) and the list of links
    return extracted_text, links


async def main_test():
    """Runs a quick test of the fetch_and_extract_text_and_links function."""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    test_urls = [
        "https://www.google.com",
        "https://httpbin.org/html",
        "https://httpbin.org/links/10/0",
    ]

    for test_url in test_urls:
        print(f"\n--- Testing Simple Fetch for URL: {test_url} ---")

        extracted_text, found_links = await fetch_and_extract_text_and_links(
            url=test_url, request_timeout=10
        )

        if extracted_text is not None:
            logger.success(f"Successfully processed URL: {test_url}")
            print(f"Extracted Text (first 500 chars):")
            print(extracted_text[:500] + "...")
        else:
            logger.warning(f"Failed to extract text for URL: {test_url}")

        print(f"Found {len(found_links)} internal links:")
        for i, link_info in enumerate(found_links[:5]):
            print(f"  {i+1}. URL: {link_info.url} (Anchor: '{link_info.anchor_text}')")
        if len(found_links) > 5:
            print("  ...")

        print("--- End Test ---")


if __name__ == "__main__":
    if not BEAUTIFULSOUP_AVAILABLE:
        logger.error("Cannot run test: Missing 'requests' or 'beautifulsoup4'.")
    elif not hasattr(asyncio, "to_thread"):
        logger.error("asyncio.to_thread is required (Python 3.9+).")
    else:
        try:
            import loguru, requests, lxml

            asyncio.run(main_test())
        except ImportError as e:
            print(f"ERROR: Missing required library: {e}.")
        except Exception as main_exc:
            logger.exception(f"An error occurred: {main_exc}")
