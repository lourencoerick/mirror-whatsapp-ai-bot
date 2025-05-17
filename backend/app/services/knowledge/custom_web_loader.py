# app/services/knowledge_loaders.py

import httpx
from loguru import logger  # Usando loguru como no seu exemplo
from typing import List, AsyncIterator, Optional

from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from bs4 import BeautifulSoup
import html2text  # Biblioteca para converter HTML para Markdown


class CustomWebLoader(BaseLoader):
    """
    Loads web page content, cleans it, and converts it to Markdown using html2text.

    This loader fetches HTML from a URL, optionally cleans it using BeautifulSoup
    to remove scripts, styles, etc., and then converts the (cleaned) HTML
    to Markdown format using the html2text library.
    It inherits from Langchain's BaseLoader.
    """

    def __init__(
        self,
        url: str,
        user_agent: Optional[str] = None,
        perform_html_cleaning: bool = True,
    ):
        """
        Initializes the CustomWebLoader.

        Args:
            url: The URL of the web page to load.
            user_agent: Optional User-Agent string for HTTP requests.
            perform_html_cleaning: If True, attempts to remove script, style,
                                   and svg tags before html2text conversion.
        Raises:
            ValueError: If the URL is not a valid HTTP/HTTPS URL.
        """
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(
                "Invalid URL. Must be a string starting with http:// or https://"
            )
        self.url = url
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        self.perform_html_cleaning = perform_html_cleaning

        # Configure html2text converter instance
        self.h2t = html2text.HTML2Text()
        self.h2t.body_width = 0  # No automatic line wrapping
        self.h2t.ignore_images = True  # Usually good for RAG
        self.h2t.ignore_links = False  # Keep links by default, can be changed
        self.h2t.ignore_emphasis = False  # Keep bold/italic
        self.h2t.unicode_snob = True
        self.h2t.mark_code = True
        self.h2t.header_style = 1  # Use #, ## for headers (ATX style)
        self.h2t.use_automatic_links = True
        self.h2t.skip_internal_links = True
        self.h2t.include_doc_title = (
            False  # Don't use <title> tag as H1 for the whole doc
        )

    def _clean_html(self, html_content: str) -> str:
        """
        Removes script, style, and svg tags from HTML content.
        """
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, "lxml")
            for tag_type in [
                "script",
                "style",
                "svg",
                "footer",
                "nav",
                "header",
                "aside",
            ]:  # Tags comuns de boilerplate/não-conteúdo
                for tag in soup.find_all(tag_type):
                    tag.decompose()  # Remove a tag e seu conteúdo
            cleaned_html = str(soup)
            logger.debug(
                f"HTML cleaned. Original length: {len(html_content)}, Cleaned length: {len(cleaned_html)}"
            )
            return cleaned_html
        except Exception as e:
            logger.error(f"Error during HTML cleaning for {self.url}: {e}")
            return html_content  # Retorna o original em caso de falha

    async def _fetch_and_convert_to_markdown(self) -> Optional[str]:
        """
        Fetches HTML from the URL, optionally cleans it, and converts it to Markdown.

        Returns:
            The Markdown content as a string, or None if fetching or conversion fails.
        """
        html_content: Optional[str] = None
        try:
            logger.info(f"Fetching HTML from URL: {self.url}")
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                html_content = response.text

            if not html_content:
                logger.warning(f"No HTML content fetched from URL: {self.url}")
                return None

            logger.success(
                f"Successfully fetched HTML from {self.url} (length: {len(html_content)})"
            )

            # Etapa de Limpeza Opcional
            if self.perform_html_cleaning:
                logger.info(f"Performing HTML cleaning for {self.url}...")
                html_to_convert = self._clean_html(html_content)
            else:
                html_to_convert = html_content

            if not html_to_convert:
                logger.warning(
                    f"HTML content is empty after cleaning for {self.url}. Cannot convert."
                )
                return None

            # Converter o HTML (limpo ou original) para Markdown
            logger.info(
                f"Converting HTML to Markdown for {self.url} using html2text..."
            )
            markdown_content = self.h2t.handle(html_to_convert)

            if not markdown_content:
                logger.warning(
                    f"html2text produced no Markdown content for URL: {self.url}"
                )
                return None

            logger.success(
                f"Successfully converted HTML to Markdown for {self.url} (Markdown length: {len(markdown_content)})"
            )
            # logger.debug(f"Markdown Output for {self.url}:\n{markdown_content[:1000]}...") # Log preview

            return markdown_content.strip()

        except httpx.TimeoutException:
            logger.error(f"Timeout occurred while fetching URL: {self.url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed for URL {self.url}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while processing URL {self.url}: {e}"
            )
            return None

    async def aload(self) -> List[Document]:
        """
        Asynchronously loads the web page content, converts to Markdown,
        and returns it as a single Document.
        """
        markdown_content = await self._fetch_and_convert_to_markdown()
        if markdown_content:
            metadata = {
                "source": self.url,
                "loader": "CustomWebLoader",
                "format": "markdown",  # Indicando que o conteúdo é Markdown
            }
            return [Document(page_content=markdown_content, metadata=metadata)]
        logger.warning(
            f"No document generated for URL: {self.url} as no Markdown content was produced."
        )
        return []

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        Asynchronously and lazily loads the web page content as Markdown.
        Yields a single Document object.
        """
        markdown_content = await self._fetch_and_convert_to_markdown()
        if markdown_content:
            metadata = {
                "source": self.url,
                "loader": "CustomWebLoader",
                "format": "markdown",
            }
            yield Document(page_content=markdown_content, metadata=metadata)
        else:
            logger.warning(f"No document to yield for URL: {self.url} (lazy load).")
