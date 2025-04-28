# backend/app/services/knowledge/ingestion_service.py

import asyncio
from typing import List, Optional, Dict, Any, Union, Tuple # Added Tuple
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# --- LangChain Imports ---
try:
    from langchain_core.documents import Document
    from langchain_community.document_loaders import (
        TextLoader, PyPDFLoader, WebBaseLoader, UnstructuredFileLoader
    )
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_LOADERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LangChain loaders/splitters not fully available: {e}. Ingestion limited.")
    LANGCHAIN_LOADERS_AVAILABLE = False
    # Dummies
    class Document:
        def __init__(self, page_content: str, metadata: Optional[Dict] = None):
            self.page_content = page_content; self.metadata = metadata or {}
    class PyPDFLoader: def __init__(self, path: str): pass; def load(self) -> List[Document]: return []
    class WebBaseLoader: def __init__(self, path: List[str]): pass; def load(self) -> List[Document]: return []
    class TextLoader: def __init__(self, path: str, encoding: str): pass; def load(self) -> List[Document]: return []
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size: int, chunk_overlap: int): pass
        def split_documents(self, docs: List[Document]) -> List[Document]: return docs

# --- Project Imports ---
# Embedding Client
try:
    from app.core.embedding_utils import get_embeddings_batch
    EMBEDDING_AVAILABLE = True
except ImportError:
    logger.error("Embedding utils not found. Cannot generate embeddings.")
    EMBEDDING_AVAILABLE = False
    async def get_embeddings_batch(*args, **kwargs) -> Optional[List[List[float]]]: return None

# Knowledge Repo
try:
    from app.services.repository.knowledge_chunk as knowledge_repo import add_chunks
    REPO_AVAILABLE = True
except ImportError:
    logger.error("Knowledge repository not found. Cannot save chunks.")
    REPO_AVAILABLE = False
    async def add_chunks(*args, **kwargs) -> int: return 0

# Document Repo/Model
try:
    from app.models.knowledge_document import KnowledgeDocument, DocumentStatus
    # Importar o módulo do repositório
    from app.services.repository import knowledge_document as knowledge_document_repo
    DOCUMENT_REPO_AVAILABLE = True
except ImportError:
    logger.warning("KnowledgeDocument model/repo not found. Status tracking disabled.")
    DOCUMENT_REPO_AVAILABLE = False
    class KnowledgeDocument: pass
    class DocumentStatus: PENDING="pending"; PROCESSING="processing"; COMPLETED="completed"; FAILED="failed"
    knowledge_document_repo = None # type: ignore


# --- Configuration ---
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
EMBEDDING_BATCH_SIZE = 32


class KnowledgeIngestionService:
    """
    Service responsible for processing source data (files, URLs, text),
    chunking, embedding, and saving it to the knowledge base.
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
            chunk_size: Target size for text chunks.
            chunk_overlap: Overlap between consecutive chunks.
        """
        if not all([LANGCHAIN_LOADERS_AVAILABLE, EMBEDDING_AVAILABLE, REPO_AVAILABLE]):
            # Log specific missing components if possible
            missing = [
                name for name, available in [
                    ("Loaders", LANGCHAIN_LOADERS_AVAILABLE),
                    ("Embeddings", EMBEDDING_AVAILABLE),
                    ("Repo", REPO_AVAILABLE)
                ] if not available
            ]
            raise RuntimeError(f"IngestionService cannot initialize. Missing: {', '.join(missing)}")

        self.db_session_factory = db_session_factory
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        logger.info(
            f"KnowledgeIngestionService initialized "
            f"(Chunk Size: {chunk_size}, Overlap: {chunk_overlap})."
        )

    async def _load_documents(
        self, source_type: str, source_uri: str
    ) -> List[Document]:
        """
        Loads documents from the specified source using appropriate loaders,
        preferring asynchronous methods like 'alazy_load' where available.
        """
        logger.info(f"Loading documents from {source_type}: {source_uri}")
        documents: List[Document] = []
        loader: Any = None

        try:
            if source_type == "file":
                file_path = source_uri
                if file_path.lower().endswith(".pdf"):
                    loader = PyPDFLoader(file_path)
                    logger.debug("Using PyPDFLoader (async)...")
                elif file_path.lower().endswith(".txt"):
                     loader = TextLoader(file_path, encoding='utf-8')
                     logger.debug("Using TextLoader (async)...")
                
                documents = [doc async for doc in loader.alazy_load()]
            elif source_type == "url":
                logger.debug("Using WebBaseLoader (async via alazy_load)...")
                loader = WebBaseLoader([source_uri]) # Passar lista
                documents = [doc async for doc in loader.alazy_load()]
            elif source_type == "text":
                documents = [Document(page_content=source_uri, metadata={"source": "manual_text"})]

            else:
                logger.error(f"Unknown source_type for loading: {source_type}")
                return []

            logger.info(f"Loaded {len(documents)} LangChain documents from source.")
            return documents

        except FileNotFoundError:
             logger.error(f"File not found during loading: {source_uri}")
             return []
        except ImportError as ie:
             logger.error(f"Import error during loading (dependency missing?): {ie}")
             return []
        except Exception as e:
            loader_name = loader.__class__.__name__ if loader else "N/A"
            logger.exception(f"Failed to load documents using {loader_name} from {source_type} '{source_uri}': {e}")
            return []

    async def _generate_embeddings_in_batches(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a list of texts in batches.
        Raises ValueError on failure.
        """
        all_embeddings: List[List[float]] = []
        if not texts:
            return all_embeddings

        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch_texts = texts[i : i + EMBEDDING_BATCH_SIZE]
            logger.debug(f"Generating embeddings for batch {i//EMBEDDING_BATCH_SIZE + 1} ({len(batch_texts)} texts)...")
            batch_embeddings_result = await get_embeddings_batch(batch_texts)

            if batch_embeddings_result is None:
                error_msg = f"Failed to generate embeddings for batch starting at index {i}."
                logger.error(error_msg)
                raise ValueError(error_msg) # Fail fast

            # Convert ndarray to list[float] if needed, handle potential None in list (though shouldn't happen now)
            processed_batch = []
            for emb in batch_embeddings_result:
                if emb is not None:
                     processed_batch.append(emb.tolist() if hasattr(emb, 'tolist') else emb)
                else:
                     # This case should ideally not happen if get_embeddings_batch raises error on failure
                     logger.error(f"Unexpected None embedding in batch result at index {i + len(processed_batch)}")
                     raise ValueError("Unexpected None embedding received.")
            all_embeddings.extend(processed_batch)


        if len(all_embeddings) != len(texts):
             error_msg = f"Mismatch between texts ({len(texts)}) and generated embeddings ({len(all_embeddings)})."
             logger.error(error_msg)
             raise ValueError(error_msg)

        return all_embeddings

    async def ingest_source(
        self,
        account_id: UUID,
        source_type: str,
        source_uri: str,
        source_identifier: str,
        document_id: Optional[UUID] = None
    ) -> bool:
        """
        Processes a single source, generates chunks and embeddings, and saves them.
        Manages document status updates if document_id is provided.

        Returns:
            True if ingestion completed successfully, False otherwise.
        """
        logger.info(
            f"Starting ingestion process for account {account_id}, "
            f"source: {source_identifier} ({source_type}), DocID: {document_id}"
        )
        final_status = DocumentStatus.FAILED # Default to failed
        error_msg: Optional[str] = "Unknown ingestion error."
        valid_chunk_count = 0
        processed_ok = False

        try:
            # --- Update Status to PROCESSING ---
            if DOCUMENT_REPO_AVAILABLE and document_id:
                async with self.db_session_factory() as db:
                    await knowledge_document_repo.update_document_status(
                        db, document_id=document_id, status=DocumentStatus.PROCESSING
                    )
                    await db.commit()

            # 1. Load Documents
            documents = await self._load_documents(source_type, source_uri)
            if not documents:
                # Loading failed or produced no documents
                if source_type == 'file' and not source_uri.lower().endswith((".pdf", ".txt")): # Example check
                     error_msg = "Unsupported file type."
                else:
                     error_msg = "Failed to load documents or source is empty."
                raise ValueError(error_msg) # Go to finally block

            # 2. Split into Chunks
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"Split into {len(chunks)} chunks.")
            if not chunks:
                logger.warning("Splitting resulted in zero chunks.")
                final_status = DocumentStatus.COMPLETED
                error_msg = "Source resulted in zero processable chunks."
                valid_chunk_count = 0
                processed_ok = True # Consider this a success case
                raise StopIteration("Zero chunks generated") # Go to finally

            # 3. Gerar Embeddings
            chunk_texts = [chunk.page_content for chunk in chunks]
            embeddings = await self._generate_embeddings_in_batches(chunk_texts)
            # Error handled by exception in helper

            # 4. Preparar Dados para Salvar
            chunks_to_save: List[Dict[str, Any]] = []
            for i, chunk_doc in enumerate(chunks):
                metadata = chunk_doc.metadata.copy() if chunk_doc.metadata else {}
                metadata["original_source"] = source_identifier
                if 'page' in chunk_doc.metadata: metadata['page_number'] = chunk_doc.metadata['page']

                chunks_to_save.append({
                    "chunk_text": chunk_doc.page_content,
                    "embedding": embeddings[i],
                    "source_type": source_type,
                    "source_identifier": source_identifier,
                    "metadata_": metadata,
                    "document_id": document_id
                })
            valid_chunk_count = len(chunks_to_save)

            # 5. Salvar Chunks no Banco
            async with self.db_session_factory() as db:
                added_count = await add_chunks(db, account_id=account_id, chunks_data=chunks_to_save)
                if added_count != valid_chunk_count:
                    raise RuntimeError(f"Failed to save all chunks ({added_count}/{valid_chunk_count}).")
                await db.commit() # Commit successful chunk saving
                logger.success(f"Successfully ingested and saved {added_count} chunks.")
                final_status = DocumentStatus.COMPLETED
                error_msg = None
                processed_ok = True

        except StopIteration as si: # Handle zero chunks case
             logger.info(str(si))
             # final_status, error_msg, valid_chunk_count set before raising
        except Exception as e:
            logger.exception(f"Ingestion failed for source {source_identifier}: {e}")
            # Use the exception message as the error message
            error_msg = f"Ingestion error: {str(e)[:500]}" # Limit error message length
            final_status = DocumentStatus.FAILED
            processed_ok = False

        finally:
            # 6. Atualizar Status Final do Documento (sempre tenta)
            if DOCUMENT_REPO_AVAILABLE and document_id:
                 try:
                     async with self.db_session_factory() as db:
                          await knowledge_document_repo.update_document_status(
                              db, document_id=document_id, status=final_status, error_message=error_msg
                          )
                          if final_status == DocumentStatus.COMPLETED:
                               await knowledge_document_repo.update_document_chunk_count(
                                   db, document_id=document_id, count=valid_chunk_count
                               )
                          await db.commit()
                          logger.info(f"Final document status updated to {final_status} for {document_id}")
                 except Exception as db_final_err:
                      # Log error but don't overwrite original failure status
                      logger.error(f"Failed to update final document status for {document_id}: {db_final_err}")

        return processed_ok