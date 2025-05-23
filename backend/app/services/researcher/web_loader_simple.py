import asyncio
from typing import Optional, Dict, Tuple, List
from urllib.parse import urljoin, urlparse
import html2text
from loguru import logger
import sys
import httpx

# Import LinkInfo schema from graph_state or define it here
try:
    from .graph_state import LinkInfo
except ImportError:
    from pydantic import BaseModel, Field  # Fallback definition

    class LinkInfo(BaseModel):
        url: str = Field(...)
        anchor_text: Optional[str] = Field(None)


# --- Dependencies ---
try:
    import httpx
    from bs4 import BeautifulSoup

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    logger.error("Required libraries 'httpx' or 'beautifulsoup4' not found.")
    BEAUTIFULSOUP_AVAILABLE = False

    class BeautifulSoup:
        pass


# --- Configuration Defaults ---
DEFAULT_SINGLE_PAGE_TIMEOUT = 20
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
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

        h2t = html2text.HTML2Text()
        h2t.body_width = 0  # No automatic line wrapping
        h2t.ignore_images = True  # Usually good for RAG
        h2t.ignore_links = False  # Keep links by default, can be changed
        h2t.ignore_emphasis = False  # Keep bold/italic
        h2t.unicode_snob = True
        h2t.mark_code = True
        h2t.header_style = 1  # Use #, ## for headers (ATX style)
        h2t.use_automatic_links = True
        h2t.skip_internal_links = True
        h2t.include_doc_title = False  # Don't use <title> tag as H1 for the whole doc
        # override the text using html2text
        text = h2t.handle(html_content)
    except Exception as e:
        logger.error(f"Error during BeautifulSoup parsing or link extraction: {e}")
        # Return whatever was extracted so far, or empty if error was early
        return text, links

    return text, links


async def _fetch_page_content_async(
    url: str, headers: Dict[str, str], timeout: int
) -> Optional[str]:
    try:
        logger.info(f"Fetching HTML from URL: {url}")
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url} after {timeout}s")
        return None
    except httpx.RequestError as e:
        logger.error(f"HTTP request failed for URL {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {e}")
        return None

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


# --- Core Function  ---


async def fetch_and_extract_text_and_links(
    url: str,
    request_timeout: int = DEFAULT_SINGLE_PAGE_TIMEOUT,
    request_headers: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], List[LinkInfo]]:
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

    default_headers = DEFAULT_REQUEST_HEADERS.copy()

    headers = request_headers if request_headers is not None else default_headers
    logger.info(f"Attempting to fetch/extract text & links from URL: {url}")

    html_content: Optional[str] = None
    extracted_text: Optional[str] = None
    links: List[LinkInfo] = []

    try:

        html_content = await _fetch_page_content_async(url, headers, request_timeout)

        if html_content:

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

                extracted_text = None
        else:

            logger.warning(
                f"Fetch failed or returned no HTML for {url}. No text or links extracted."
            )
            return None, []

    except asyncio.TimeoutError:
        logger.error(f"Overall operation timeout fetching/processing {url}")
        return None, []
    except Exception as e:
        logger.exception(f"Unexpected error during fetch/extract for {url}: {e}")
        return None, []

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
            print("Extracted Text (first 500 chars):")
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
            import loguru, httpx, lxml

            asyncio.run(main_test())
        except ImportError as e:
            print(f"ERROR: Missing required library: {e}.")
        except Exception as main_exc:
            logger.exception(f"An error occurred: {main_exc}")
