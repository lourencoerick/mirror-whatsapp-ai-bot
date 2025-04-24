# backend/app/services/researcher/web_loader_simple.py

import asyncio
from typing import Optional, Dict, Tuple

from loguru import logger
import sys

# --- Dependencies ---
# pip install requests beautifulsoup4 lxml
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
DEFAULT_SINGLE_PAGE_TIMEOUT = 20  # Timeout for fetching one page
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Connection": "keep-alive",
}


# --- Helper Functions ---


def _validate_url(url: str) -> bool:
    """Checks if the URL is non-empty and has a valid scheme."""
    if not url or not url.startswith(("http://", "https://")):
        logger.warning(f"Invalid or missing URL provided: {url}")
        return False
    return True


def _clean_extracted_text(text: str) -> str:
    """Removes excessive blank lines from extracted text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def _extract_text_simple(html_content: str) -> str:
    """Extracts main text content from HTML using BeautifulSoup."""
    if not BEAUTIFULSOUP_AVAILABLE:
        return ""
    try:
        soup = BeautifulSoup(html_content, "lxml")  # Use lxml parser
        # Remove common irrelevant tags
        for script_or_style in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form"]
        ):
            script_or_style.decompose()
        # Get remaining text, separated by newlines, stripping extra whitespace
        text = soup.get_text(separator="\n", strip=True)
        return text
    except Exception as e:
        logger.error(f"Error during BeautifulSoup parsing: {e}")
        return ""  # Return empty string on parsing error


def _fetch_page_content_sync(
    url: str, headers: Dict[str, str], timeout: int
) -> Optional[str]:
    """Synchronous function to fetch page content (for use with to_thread)."""
    try:
        response = requests.get(
            url, headers=headers, timeout=timeout, allow_redirects=True
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            logger.debug(f"Skipping non-HTML content at {url} (type: {content_type})")
            return None
        # Use response.content and decode explicitly for better encoding handling
        # Try UTF-8 first, then let requests guess if needed
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning(
                f"UTF-8 decoding failed for {url}, using apparent encoding: {response.apparent_encoding}"
            )
            return response.text  # Fallback to requests' detected encoding
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url} after {timeout}s")
        return None
    except requests.exceptions.RequestException as e:
        # Log specific HTTP errors if possible
        status_code = getattr(e.response, "status_code", "N/A")
        logger.warning(f"Failed to fetch {url} (Status: {status_code}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None


# --- Core Function ---


async def fetch_and_extract_text(
    url: str,
    request_timeout: int = DEFAULT_SINGLE_PAGE_TIMEOUT,
    request_headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Fetches content from a single URL, extracts, and cleans the text content.

    Uses synchronous requests in a thread for robustness.

    Args:
        url: The URL of the web page to load.
        request_timeout: Timeout in seconds for the fetch operation.
        request_headers: Headers to use for the HTTP request.

    Returns:
        A string containing the extracted and cleaned text content, or None on failure.
    """
    if not BEAUTIFULSOUP_AVAILABLE:
        logger.error("Dependencies (requests, beautifulsoup4) not available.")
        return None
    if not _validate_url(url):
        return None

    headers = (
        request_headers if request_headers is not None else DEFAULT_REQUEST_HEADERS
    )

    logger.info(f"Attempting to fetch and extract text from URL: {url}")

    try:
        # Fetch HTML content in thread
        html_content = await asyncio.wait_for(
            asyncio.to_thread(_fetch_page_content_sync, url, headers, request_timeout),
            timeout=float(request_timeout + 5),  # Add buffer to wait_for timeout
        )

        if not html_content:
            # Fetch function already logged the reason (timeout, error, non-html)
            return None

        # Extract text using BeautifulSoup
        extracted_text = _extract_text_simple(html_content)
        if not extracted_text.strip():
            logger.warning(f"No significant text extracted from {url} after parsing.")
            return None

        # Clean the extracted text (remove extra blank lines)
        clean_text = _clean_extracted_text(extracted_text)

        logger.success(
            f"Successfully fetched and extracted text from {url}. Length: {len(clean_text)}"
        )
        return clean_text

    except asyncio.TimeoutError:
        # This timeout is for the asyncio.wait_for call itself
        logger.error(f"Overall operation timeout fetching/processing {url}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error during fetch/extract for {url}: {e}")
        return None


# --- Example Usage (for quick testing) ---
async def main_test():
    """Runs a quick test of the fetch_and_extract_text function."""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    test_urls = [
        "https://www.google.com",
        "https://httpbin.org/html",
        "https://httpbin.org/delay/5",  # Test timeout
        "https://httpbin.org/status/404",  # Test HTTP error
        "https://nonexistent-domain-for-testing-12345.xyz",  # Test DNS error
        "https://www.google.com/images/branding/googlelogo/1x/googlelogo_light_color_272x92dp.png",  # Test non-html
    ]

    for test_url in test_urls:
        print(f"\n--- Testing Simple Fetch for URL: {test_url} ---")
        extracted_text = await fetch_and_extract_text(
            url=test_url, request_timeout=10  # Use shorter timeout for testing
        )

        if extracted_text:
            logger.success(f"Successfully processed URL: {test_url}")
            print(f"Extracted Text (first 500 chars):")
            print(extracted_text[:500] + "...")
        else:
            logger.warning(f"Failed to extract text for URL: {test_url}")
        print("--- End Test ---")


if __name__ == "__main__":
    if not BEAUTIFULSOUP_AVAILABLE:
        logger.error("Cannot run test: Missing 'requests' or 'beautifulsoup4'.")
    elif not hasattr(asyncio, "to_thread"):
        logger.error("asyncio.to_thread is required (Python 3.9+).")
    else:
        try:
            import loguru, requests, lxml  # Check lxml for parser

            asyncio.run(main_test())
        except ImportError as e:
            print(f"ERROR: Missing required library: {e}.")
        except Exception as main_exc:
            logger.exception(
                f"An error occurred during the main test execution: {main_exc}"
            )
