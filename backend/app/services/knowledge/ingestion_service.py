# backend/app/services/knowledge/ingestion_service.py
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union, Literal
from uuid import UUID
from urllib.parse import urlparse, urlunparse
from itertools import groupby

import html2text

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from .custom_web_loader import CustomWebLoader


# --- LangChain Imports ---
# Attempt to import necessary LangChain components
try:
    from langchain_community.document_loaders import (
        PyPDFLoader,
        TextLoader,
        UnstructuredFileLoader,  # Keep if used, remove if not
        RecursiveUrlLoader,
    )
    from langchain_core.documents import Document
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_experimental.text_splitter import SemanticChunker

    LANGCHAIN_LOADERS_AVAILABLE = True
except ImportError as e:
    logger.warning(
        f"LangChain loaders/splitters not fully available: {e}. Ingestion limited."
    )
    LANGCHAIN_LOADERS_AVAILABLE = False

    # Define dummy classes/functions if imports fail, allowing service to load
    # but potentially fail at runtime if these features are used.
    class Document:
        def __init__(self, page_content: str, metadata: Optional[Dict] = None):
            self.page_content = page_content
            self.metadata = metadata or {}

    class PyPDFLoader:
        def __init__(self, path: str):
            pass

        async def alazy_load(self) -> List[Document]:  # Match async signature if needed
            return []  # Return empty list

    class WebBaseLoader:
        def __init__(self, path: List[str]):
            pass

        async def alazy_load(self) -> List[Document]:  # Match async signature
            return []

    class TextLoader:
        def __init__(self, path: str, encoding: str):
            pass

        async def alazy_load(self) -> List[Document]:  # Match async signature
            return []

    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size: int, chunk_overlap: int):
            pass

        def split_documents(self, docs: List[Document]) -> List[Document]:
            return docs  # Pass through if splitter unavailable


# --- Project Imports ---

# Embedding Client
try:
    from app.core.embedding_utils import get_embeddings_batch, langchain_embbedings

    EMBEDDING_AVAILABLE = True
except ImportError:
    logger.error(
        "Embedding utils (get_embeddings_batch) not found. Cannot generate embeddings."
    )
    EMBEDDING_AVAILABLE = False

    # Dummy function
    async def get_embeddings_batch(*args, **kwargs) -> Optional[List[List[float]]]:
        return None


# Knowledge Chunk Repository
try:
    # Assuming 'add_chunks' is the primary function needed from this repo
    from app.services.repository.knowledge_chunk import add_chunks

    REPO_AVAILABLE = True
except ImportError:
    logger.error(
        "Knowledge chunk repository (add_chunks) not found. Cannot save chunks."
    )
    REPO_AVAILABLE = False

    # Dummy function
    async def add_chunks(*args, **kwargs) -> int:
        return 0


# Knowledge Document Repository/Model
try:
    from app.models.knowledge_document import DocumentStatus, KnowledgeDocument
    from app.services.repository import knowledge_document as knowledge_document_repo

    DOCUMENT_REPO_AVAILABLE = True
except ImportError:
    logger.warning("KnowledgeDocument model/repo not found. Status tracking disabled.")
    DOCUMENT_REPO_AVAILABLE = False

    # Dummy classes/variables
    class KnowledgeDocument:
        pass

    class DocumentStatus:
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    knowledge_document_repo = None  # type: ignore

try:
    from app.services.cloud_storage import download_gcs_file

    STORAGE_AVAILABLE = True
except ImportError:
    logger.error("Cloud storage utilities not found.")
    STORAGE_AVAILABLE = False

    async def download_gcs_file(*args, **kwargs) -> Optional[str]:
        return None  # Dummy


# --- Configuration ---
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
EMBEDDING_BATCH_SIZE = 32  # Batch size for embedding generation
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


class KnowledgeIngestionService:
    """
    Service responsible for processing source data (files, URLs, text),
    chunking it, generating embeddings, and saving the results to the
    knowledge base repository. Tracks document status if applicable.
    """

    def __init__(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        """
        Initializes the ingestion service.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            chunk_size: Target size for text chunks during splitting.
            chunk_overlap: Overlap between consecutive chunks.

        Raises:
            RuntimeError: If essential dependencies (loaders, embeddings, repo)
                          are not available.
        """
        # Check for essential components availability
        essentials_available = all(
            [LANGCHAIN_LOADERS_AVAILABLE, EMBEDDING_AVAILABLE, REPO_AVAILABLE]
        )
        if not essentials_available:
            missing = [
                name
                for name, available in [
                    ("LangChain Loaders/Splitters", LANGCHAIN_LOADERS_AVAILABLE),
                    ("Embedding Function", EMBEDDING_AVAILABLE),
                    ("Chunk Repository", REPO_AVAILABLE),
                ]
                if not available
            ]
            raise RuntimeError(
                f"KnowledgeIngestionService cannot initialize. Missing components: {', '.join(missing)}"
            )

        self.db_session_factory = db_session_factory
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self.semantic_text_splitter = SemanticChunker(
            langchain_embbedings, breakpoint_threshold_type="gradient"
        )

        logger.info(
            f"KnowledgeIngestionService initialized (Chunk Size: {chunk_size}, Overlap: {chunk_overlap})."
        )

    async def _load_documents(
        self,
        source_type: str,
        source_uri: str,
        recursive: bool = False,
    ) -> List[Document]:
        """
        Loads documents from the specified source using appropriate LangChain loaders.

        Prioritizes asynchronous loading methods (`alazy_load`) where available.

        Args:
            source_type: The type of the source ('file', 'url', 'text').
            source_uri: The path, URL, or raw text content of the source.

        Returns:
            A list of LangChain Document objects, or an empty list if loading fails.
        """
        logger.info(f"Loading documents from {source_type}: {source_uri}")
        documents: List[Document] = []
        loader: Any = None  # To store the loader instance for logging

        try:
            if source_type == "file":
                if source_uri.startswith("gs://"):
                    if not STORAGE_AVAILABLE:
                        raise RuntimeError(
                            "GCS storage component is required but unavailable."
                        )
                    logger.debug(f"Source is a GCS URI, attempting download...")
                    # Baixar para um arquivo temporário
                    local_file_path = await download_gcs_file(source_uri)
                    if not local_file_path:
                        raise ValueError(
                            f"Failed to download file from GCS: {source_uri}"
                        )
                    is_temp_file = True  # Marcar para exclusão posterior
                    logger.info(
                        f"File downloaded from GCS to temporary path: {local_file_path}"
                    )
                    file_path_for_loader = local_file_path  # Usar o path local
                else:
                    # Assumir que é um path local (talvez para testes ou outros cenários)
                    logger.warning(
                        f"Source type is 'file' but URI doesn't start with gs://. Assuming local path: {source_uri}"
                    )
                    file_path_for_loader = source_uri

                # Determine loader based on file extension
                if file_path_for_loader.lower().endswith(".pdf"):
                    loader = PyPDFLoader(file_path_for_loader)
                    logger.debug("Using PyPDFLoader...")
                elif file_path_for_loader.lower().endswith(".txt"):
                    loader = TextLoader(file_path_for_loader, encoding="utf-8")
                    logger.debug("Using TextLoader...")
                # Add other file types here if needed (e.g., UnstructuredFileLoader)
                elif file_path_for_loader.lower().endswith((".docx", ".pptx")):
                    loader = UnstructuredFileLoader(
                        file_path_for_loader, mode="elements"
                    )  # Example
                    logger.debug("Using UnstructuredFileLoader...")
                else:
                    logger.warning(
                        f"Unsupported file type for direct loading: {file_path_for_loader}"
                    )
                    return []  # Return empty if type not supported

                # Use asynchronous loading if available
                if hasattr(loader, "alazy_load"):
                    logger.debug("Attempting asynchronous loading (alazy_load)...")
                    documents = [doc async for doc in loader.alazy_load()]
                elif hasattr(loader, "load"):
                    logger.debug("Using synchronous loading (load)...")
                    # Run synchronous load in a thread pool to avoid blocking async event loop
                    documents = await asyncio.to_thread(loader.load)
                else:
                    logger.error(
                        f"Loader for {file_path_for_loader} has no load or alazy_load method."
                    )
                    return []

            elif source_type == "url":
                logger.debug("Using WebBaseLoader...")
                # WebBaseLoader expects a list of URLs

                if not recursive:
                    loader = CustomWebLoader(source_uri)
                else:
                    parsed_url = urlparse(source_uri)
                    base_url = urlunparse(
                        (
                            parsed_url.scheme,
                            parsed_url.netloc,
                            "/",  # We want the path to be just the root
                            "",  # No parameters
                            "",  # No query string
                            "",  # No fragment
                        )
                    )

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
                    h2t.include_doc_title = (
                        False  # Don't use <title> tag as H1 for the whole doc
                    )

                    loader = RecursiveUrlLoader(
                        url=source_uri,
                        max_depth=2,
                        prevent_outside=False,
                        base_url=base_url,
                        extractor=h2t.handle,
                        check_response_status=True,
                        continue_on_failure=True,
                        link_regex=r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"',
                    )

                if hasattr(loader, "alazy_load"):
                    logger.debug("Attempting asynchronous loading (alazy_load)...")
                    documents = [doc async for doc in loader.alazy_load()]
                elif hasattr(loader, "load"):
                    logger.debug("Using synchronous loading (load)...")
                    documents = await asyncio.to_thread(loader.load)
                else:
                    logger.error("WebBaseLoader has no load or alazy_load method.")
                    return []

            elif source_type == "text":
                # Create a single document directly from the text content
                documents = [
                    Document(
                        page_content=source_uri, metadata={"source": "manual_text"}
                    )
                ]
                logger.debug("Created document directly from text input.")

            else:
                # Handle unknown source types
                logger.error(f"Unknown source_type for loading: {source_type}")
                return []

            logger.info(f"Loaded {len(documents)} LangChain documents from source.")
            return documents

        except FileNotFoundError:
            logger.error(f"File not found during loading: {source_uri}")
            return []
        except ImportError as ie:
            # Catch errors if a specific loader's dependency is missing
            logger.error(f"Import error during loading (dependency missing?): {ie}")
            return []
        except Exception as e:
            # Catch-all for other loading errors
            loader_name = loader.__class__.__name__ if loader else "N/A"
            logger.exception(
                f"Failed to load documents using {loader_name} from "
                f"{source_type} '{source_uri}': {e}"
            )
            return []

    async def _generate_embeddings_in_batches(
        self, texts: List[str]
    ) -> List[List[float]]:
        """
        Generates embeddings for a list of text strings in batches.

        Args:
            texts: A list of strings to embed.

        Returns:
            A list of embeddings (each embedding is a list of floats).

        Raises:
            ValueError: If embedding generation fails for any batch or if the
                        number of embeddings does not match the number of texts.
        """
        all_embeddings: List[List[float]] = []
        if not texts:
            logger.info("No texts provided for embedding generation.")
            return all_embeddings

        logger.info(
            f"Generating embeddings for {len(texts)} texts in batches of {EMBEDDING_BATCH_SIZE}..."
        )
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch_texts = texts[i : i + EMBEDDING_BATCH_SIZE]
            batch_num = i // EMBEDDING_BATCH_SIZE + 1
            logger.debug(
                f"Processing embedding batch {batch_num} ({len(batch_texts)} texts)..."
            )

            # Call the actual embedding function
            batch_embeddings_result = await get_embeddings_batch(batch_texts)

            # Check if the result is valid
            if batch_embeddings_result is None:
                error_msg = f"Failed to generate embeddings for batch {batch_num} (starting index {i})."
                logger.error(error_msg)
                raise ValueError(error_msg)  # Fail fast if a batch fails

            # Process the batch result (handle potential None values defensively, convert numpy arrays)
            processed_batch: List[List[float]] = []
            if len(batch_embeddings_result) != len(batch_texts):
                error_msg = (
                    f"Embedding result count ({len(batch_embeddings_result)}) "
                    f"does not match text count ({len(batch_texts)}) for batch {batch_num}."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            for idx, emb in enumerate(batch_embeddings_result):
                if emb is not None:
                    # Convert numpy array to list if necessary
                    processed_embedding = (
                        emb.tolist() if hasattr(emb, "tolist") else emb
                    )
                    # Basic validation of embedding structure (optional)
                    if not isinstance(processed_embedding, list) or not all(
                        isinstance(f, float) for f in processed_embedding
                    ):
                        logger.warning(
                            f"Unexpected embedding format at index {i+idx} in batch {batch_num}. Type: {type(processed_embedding)}"
                        )
                        # Decide whether to raise error or skip
                        # raise ValueError(f"Invalid embedding format received at index {i+idx}.")
                    processed_batch.append(processed_embedding)
                else:
                    # This case should ideally be prevented by get_embeddings_batch raising an error
                    error_msg = f"Unexpected None embedding received at index {i+idx} in batch {batch_num}."
                    logger.error(error_msg)
                    raise ValueError(error_msg)

            all_embeddings.extend(processed_batch)
            logger.debug(f"Finished processing embedding batch {batch_num}.")

        # Final check: ensure the total number of embeddings matches the input texts
        if len(all_embeddings) != len(texts):
            error_msg = (
                f"Final embedding count ({len(all_embeddings)}) does not match "
                f"initial text count ({len(texts)})."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Successfully generated {len(all_embeddings)} embeddings.")
        return all_embeddings

    async def ingest_source(
        self,
        account_id: UUID,
        source_type: str,
        source_uri: str,
        source_identifier: str,
        recursive: bool,
        document_id: Optional[UUID] = None,
        text_splitter_type: Optional[Literal["semantic", "recursive"]] = "recursive",
    ) -> bool:
        """
        Processes a single source: loads, splits, embeds, and saves chunks.
        Manages document status updates via the repository if document_id is provided.

        Args:
            account_id: The UUID of the account owning the data.
            source_type: Type of the source ('file', 'url', 'text').
            source_uri: Path, URL, or text content.
            source_identifier: A user-friendly name or identifier for the source (e.g., filename, URL).
            document_id: Optional UUID of the associated KnowledgeDocument for status tracking.

        Returns:
            True if ingestion completed successfully (chunks saved), False otherwise.
        """
        logger.info(
            f"Starting ingestion: Account={account_id}, Source='{source_identifier}' "
            f"({source_type}), DocID={document_id}"
        )
        # Initialize status tracking variables
        final_status = (
            DocumentStatus.FAILED
        )  # Default to failed unless explicitly successful
        error_message: Optional[str] = (
            "Ingestion process did not complete successfully."
        )
        processed_chunk_count = 0
        ingestion_successful = False

        try:
            # --- Update Status to PROCESSING ---
            if document_id:
                logger.debug(f"Updating document {document_id} status to PROCESSING.")
                async with self.db_session_factory() as db:
                    await knowledge_document_repo.update_document_status(
                        db, document_id=document_id, status=DocumentStatus.PROCESSING
                    )
                    await db.commit()

            # --- Step 1: Load ALL Documents from the source ---
            all_loaded_docs = await self._load_documents(
                source_type, source_uri, recursive
            )
            if not all_loaded_docs:
                error_message = "Failed to load documents or the source is empty."
                logger.warning(f"No documents loaded from source: {source_identifier}")
                return False

            loaded_documents_for_db = [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in all_loaded_docs
            ]

            # --- Group documents by their source metadata ---
            # This is crucial for websites or sources that yield multiple files.
            # We group by the 'source' key in the metadata, which LangChain loaders populate.
            get_source_key = lambda doc: doc.metadata.get("source", "default_source")

            # Sort documents by source to ensure groupby works correctly
            all_loaded_docs.sort(key=get_source_key)

            grouped_docs = groupby(all_loaded_docs, key=get_source_key)

            all_chunks_to_save: List[Dict[str, Any]] = []

            # --- Process each group of documents (e.g., each webpage) separately ---
            for source_key, doc_group_iter in grouped_docs:
                doc_group = list(doc_group_iter)
                logger.info(
                    f"Processing document group with source: '{source_key}' ({len(doc_group)} parts)."
                )

                # --- Step 2: Split into Chunks (for this group only) ---
                splitter = (
                    self.semantic_text_splitter
                    if text_splitter_type == "semantic"
                    else self.text_splitter
                )
                chunks = splitter.split_documents(doc_group)

                if not chunks:
                    logger.warning(
                        f"Splitting resulted in zero chunks for source '{source_key}'. Skipping."
                    )
                    continue

                # --- Step 3: Generate Embeddings (for this group's chunks) ---
                chunk_texts = [chunk.page_content for chunk in chunks]
                embeddings = await self._generate_embeddings_in_batches(chunk_texts)

                # --- Step 4: Prepare Chunk Data (with correct, resetting index) ---
                for i, chunk_doc in enumerate(chunks):
                    metadata = chunk_doc.metadata.copy() if chunk_doc.metadata else {}
                    # Use the specific source of this group, not the overall identifier
                    metadata["original_source"] = source_key
                    if "page" in metadata:
                        metadata["page_number"] = metadata.pop("page")

                    all_chunks_to_save.append(
                        {
                            "chunk_text": chunk_doc.page_content,
                            "embedding": embeddings[i],
                            "chunk_index": i,  # Index resets for each new group
                            "source_type": source_type,
                            # We use the more specific source_key for the identifier
                            "source_identifier": source_key,
                            "metadata_": metadata,
                            "document_id": document_id,
                        }
                    )

            total_processed_chunk_count = len(all_chunks_to_save)
            logger.info(
                f"Total chunks prepared from all groups: {total_processed_chunk_count}"
            )

            if not all_chunks_to_save:
                logger.warning(
                    "Processing all groups resulted in zero chunks. Marking as complete."
                )
                final_status = DocumentStatus.COMPLETED
                error_message = None
                ingestion_successful = True
            else:
                # --- Step 5: Save All Prepared Chunks to Database in one go ---
                logger.debug(
                    f"Saving {total_processed_chunk_count} total chunks to the repository..."
                )
                async with self.db_session_factory() as db:
                    added_count = await add_chunks(
                        db, account_id=account_id, chunks_data=all_chunks_to_save
                    )
                    if added_count != total_processed_chunk_count:
                        error_message = f"DB save mismatch: Expected {total_processed_chunk_count}, saved {added_count}."
                        logger.error(error_message)
                        final_status = DocumentStatus.FAILED
                        ingestion_successful = False
                    else:
                        await db.commit()
                        logger.success(
                            f"Successfully ingested and saved {added_count} chunks."
                        )
                        final_status = DocumentStatus.COMPLETED
                        error_message = None
                        ingestion_successful = True

        except ValueError as ve:
            logger.error(f"Ingestion failed due to ValueError: {ve}")
            error_message = f"Processing error: {str(ve)[:500]}"
            final_status = DocumentStatus.FAILED
            ingestion_successful = False
        except Exception as e:
            logger.exception(
                f"Unexpected error during ingestion for source {source_identifier}: {e}"
            )
            error_message = f"Unexpected error: {str(e)[:500]}"
            final_status = DocumentStatus.FAILED
            ingestion_successful = False

        finally:
            if DOCUMENT_REPO_AVAILABLE and document_id:
                logger.debug(
                    f"Updating final document status for {document_id} to {final_status}."
                )
                try:
                    async with self.db_session_factory() as db:

                        await knowledge_document_repo.update_document_status(
                            db,
                            document_id=document_id,
                            status=final_status,
                            error_message=error_message,
                        )

                        await knowledge_document_repo.update_extracted_content(
                            db,
                            document_id=document_id,
                            extracted_content=loaded_documents_for_db,
                        )

                        if (
                            final_status == DocumentStatus.COMPLETED
                            and ingestion_successful
                        ):
                            await knowledge_document_repo.update_document_chunk_count(
                                db,
                                document_id=document_id,
                                count=total_processed_chunk_count,
                            )

                        await db.commit()
                        logger.info(
                            f"Final document status and content updated for {document_id}."
                        )
                except Exception as db_final_err:
                    logger.error(
                        f"CRITICAL: Failed to update final document status/content for {document_id}. Error: {db_final_err}"
                    )

            return ingestion_successful
