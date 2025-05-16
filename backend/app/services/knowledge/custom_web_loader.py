# app/services/knowledge_loaders.py

import trafilatura
import httpx
from loguru import logger
from typing import List, AsyncIterator, Optional

from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document


class CustomWebLoader(BaseLoader):
    """
    Loads web page content using Trafilatura and converts it into a Langchain Document.

    This loader fetches the content from a URL, extracts the main textual content
    using Trafilatura, and returns it as a single Document.
    It inherits from Langchain's BaseLoader.
    """

    def __init__(self, url: str):
        """
        Initializes the CustomWebLoader.

        Args:
            url: The URL of the web page to load.

        Raises:
            ValueError: If the URL is not a valid HTTP/HTTPS URL.
        """
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(
                "Invalid URL. Must be a string starting with http:// or https://"
            )
        self.url = url

    async def _fetch_and_extract_content(self) -> Optional[str]:
        """
        Fetches HTML from the URL and extracts the main text content using Trafilatura.

        Returns:
            The extracted text content, or None if extraction fails or an error occurs.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(self.url)
                response.raise_for_status()  # Raise an exception for bad status codes
                html_content = response.text

            if not html_content:
                logger.warning(f"No HTML content fetched from URL: {self.url}")
                return None

            # Extract main content using Trafilatura
            # output_format='text' ensures plain text output.
            extracted_text = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=False,  # Consider making this configurable if tables are needed
                output_format="txt",
            )

            if not extracted_text:
                logger.warning(
                    f"Trafilatura could not extract main content from URL: {self.url}"
                )
                return None

            return (
                extracted_text.strip()
            )  # Ensure leading/trailing whitespace is removed

        except httpx.TimeoutException:
            logger.error(f"Timeout occurred while fetching URL: {self.url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed for URL {self.url}: {e}")
            return None
        except Exception as e:
            # Catch any other unexpected errors during extraction.
            logger.error(
                f"An unexpected error occurred while processing URL {self.url}: {e}"
            )
            return None

    async def aload(self) -> List[Document]:
        """
        Asynchronously loads the web page content into a list containing a single Document.

        The Document's page_content will be the extracted text, and its metadata
        will include the source URL and a type identifier.

        Returns:
            A list containing one Document with the page content, or an empty list if
            content extraction fails or no content is found.
        """
        extracted_text = await self._fetch_and_extract_content()
        if extracted_text:
            metadata = {"source": self.url, "loader": "CustomWebLoader"}
            return [Document(page_content=extracted_text, metadata=metadata)]
        return []

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        Asynchronously and lazily loads the web page content.

        Yields a single Document object containing the extracted text from the URL.
        If content extraction fails or no content is found, the iterator will be empty.
        """
        extracted_text = await self._fetch_and_extract_content()
        if extracted_text:
            metadata = {"source": self.url, "loader": "CustomWebLoader"}
            yield Document(page_content=extracted_text, metadata=metadata)


class CustomTextLoader(BaseLoader):
    """
    Loads text from a string into a Langchain Document.

    This loader takes a string of text and wraps it in a single Document.
    It inherits from Langchain's BaseLoader.
    """

    def __init__(self, text_content: str, source_name: str = "text_input"):
        """
        Initializes the CustomTextLoader.

        Args:
            text_content: The string content to load.
            source_name: An identifier for the source of this text (e.g., "manual_entry_123").
        """
        if not isinstance(text_content, str):
            raise ValueError("text_content must be a string.")
        self.text_content = text_content
        self.source_name = source_name

    async def aload(self) -> List[Document]:
        """
        Asynchronously "loads" the text content into a list containing a single Document.

        Returns:
            A list containing one Document with the text content.
            Returns an empty list if the text_content is empty or only whitespace.
        """
        cleaned_text = self.text_content.strip()
        if not cleaned_text:
            logger.info(
                f"Empty text content provided for source: {self.source_name}. "
                "No document will be created."
            )
            return []

        metadata = {"source": self.source_name, "loader": "CustomTextLoader"}
        return [Document(page_content=cleaned_text, metadata=metadata)]

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        Asynchronously and lazily "loads" the text content.

        Yields a single Document object containing the text.
        If text_content is empty or only whitespace, the iterator will be empty.
        """
        cleaned_text = self.text_content.strip()
        if cleaned_text:
            metadata = {"source": self.source_name, "loader": "CustomTextLoader"}
            yield Document(page_content=cleaned_text, metadata=metadata)
        else:
            logger.info(
                f"Empty text content provided for source: {self.source_name} "
                "in alazy_load. Iterator will be empty."
            )
