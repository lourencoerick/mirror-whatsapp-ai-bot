import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query

# Arq imports
from arq.connections import ArqRedis, Job
from arq.jobs import JobStatus, ResultNotFound
from redis.exceptions import (
    ConnectionError as ArqConnectionError,
    TimeoutError as EnqueueTimeout,
)


from app.core.arq_manager import get_arq_pool
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.services.cloud_storage import (
    save_knowledge_file_gcs,
)
from app.database import get_db, AsyncSessionLocal


try:
    from app.services.repository import knowledge_document as knowledge_document_repo
    from app.models.knowledge_document import DocumentStatus, KnowledgeDocument

    DOCUMENT_REPO_AVAILABLE = True
except ImportError:
    DOCUMENT_REPO_AVAILABLE = False
    knowledge_document_repo = None  # type: ignore

    class DocumentStatus:
        PENDING = "pending"  # Dummy

    class KnowledgeDocument:
        pass  # Dummy


from app.api.schemas.knowledge_document import (
    KnowledgeDocumentCreate,
    AddTextRequest,
    AddUrlRequest,
    IngestResponse,
    JobStatusResponse,
    JobStatusEnum,
    KnowledgeDocumentRead,
    PaginatedKnowledgeDocumentRead,
)

from app.core.wake_workers import wake_worker
from app.config import get_settings, Settings

settings: Settings = get_settings()


KNOWLEDGE_TASK_NAME = "process_knowledge_source"
BATCH_ARQ_QUEUE_NAME = settings.BATCH_ARQ_QUEUE_NAME

router = APIRouter()


# --- Endpoint: Upload File ---
@router.post(
    "/knowledge/upload-file",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Knowledge File",
    description="Uploads a file (PDF, TXT, DOCX) to the knowledge base for processing.",
)
async def upload_knowledge_file(
    file: UploadFile = File(..., description="The knowledge file to upload."),
    auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    db: AsyncSession = Depends(get_db),
):
    """
    Handles file upload, saves it to GCS, creates a KnowledgeDocument record,
    and enqueues the ingestion task.
    """
    account_id: UUID = auth_context.account.id
    original_filename = file.filename or "unknown_file"
    logger.info(
        f"Received file upload request: '{original_filename}' for account {account_id}"
    )

    if not DOCUMENT_REPO_AVAILABLE or not knowledge_document_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document repository unavailable.",
        )
    if not arq_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue unavailable.",
        )

    document_record: Optional[KnowledgeDocument] = None
    try:
        document_in = KnowledgeDocumentCreate(
            source_type="file",
            source_uri=f"pending_upload/{original_filename}",
            original_filename=original_filename,
        )

        document_record = await knowledge_document_repo.create_document(
            db=db,
            account_id=account_id,
            document_in=document_in,
            initial_status=DocumentStatus.PENDING,
        )
        await db.commit()
        await db.refresh(document_record)
        logger.info(
            f"Created KnowledgeDocument record (ID: {document_record.id}) with PENDING status."
        )
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"Failed to create KnowledgeDocument record for file '{original_filename}': {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register document before upload.",
        ) from e

    if not document_record or not document_record.id:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document ID after creation.",
        )

    document_id = document_record.id

    gcs_uri: Optional[str] = None
    try:
        gcs_uri = await save_knowledge_file_gcs(
            file=file,
            account_id=account_id,
            document_id=document_id,
        )

        document_record.source_uri = gcs_uri
        db.add(document_record)
        await db.commit()
        logger.info(f"Updated document {document_id} source_uri to {gcs_uri}")

    except HTTPException as e:

        logger.error(
            f"GCS upload failed for document {document_id}. Marking as FAILED."
        )
        try:
            document_record.status = DocumentStatus.FAILED
            document_record.error_message = f"GCS Upload Failed: {e.detail}"
            db.add(document_record)
            await db.commit()
        except Exception as db_err:
            logger.error(
                f"Failed to update document {document_id} status to FAILED after upload error: {db_err}"
            )
            await db.rollback()
        raise e
    except Exception as e:

        logger.exception(
            f"Unexpected error during GCS upload for document {document_id}. Marking as FAILED."
        )
        try:
            document_record.status = DocumentStatus.FAILED
            document_record.error_message = f"Unexpected Upload Error: {str(e)[:200]}"
            db.add(document_record)
            await db.commit()
        except Exception as db_err:
            logger.error(
                f"Failed to update document {document_id} status to FAILED after unexpected upload error: {db_err}"
            )
            await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed unexpectedly.",
        ) from e

    job: Optional[Job] = None
    try:
        await wake_worker(settings.BATCH_WORKER_INTERNAL_URL)
        job = await arq_pool.enqueue_job(
            KNOWLEDGE_TASK_NAME,
            account_id=account_id,
            source_type="file",
            source_uri=gcs_uri,
            source_identifier=original_filename,
            document_id=document_id,
            _queue_name=BATCH_ARQ_QUEUE_NAME,
        )
        if not job:
            raise RuntimeError("arq_pool.enqueue_job returned None.")

        logger.info(
            f"Enqueued knowledge ingestion job '{job.job_id}' for document {document_id}."
        )
        return IngestResponse(
            document_id=document_id,
            job_id=job.job_id,
            message=f"File '{original_filename}' uploaded and ingestion task queued.",
        )

    except (ArqConnectionError, EnqueueTimeout, RuntimeError, Exception) as q_err:
        logger.exception(
            f"Failed to enqueue ingestion task for document {document_id}: {q_err}"
        )

        try:
            async with AsyncSessionLocal() as db_fail:
                await knowledge_document_repo.update_document_status(
                    db_fail,
                    document_id=document_id,
                    status=DocumentStatus.FAILED,
                    error_message=f"Failed to queue task: {q_err}",
                )
                await db_fail.commit()
        except Exception as db_err:
            logger.error(
                f"Failed to update document {document_id} status to FAILED after queue error: {db_err}"
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue ingestion task after upload.",
        ) from db_err


@router.post(
    "/knowledge/add-url",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add Knowledge URL",
    description="Adds a URL to the knowledge base for scraping and ingestion.",
)
async def add_knowledge_url(
    request: AddUrlRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a KnowledgeDocument record for a URL and enqueues the ingestion task.
    """
    account_id: UUID = auth_context.account.id
    url_to_ingest = str(request.url)
    recursive_crawl = request.recursive
    source_identifier = url_to_ingest

    logger.info(
        f"Received URL ingestion request: '{url_to_ingest}' (recursive: {recursive_crawl}) for account {account_id}"
    )

    if not DOCUMENT_REPO_AVAILABLE or not knowledge_document_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document repository unavailable.",
        )
    if not arq_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue unavailable.",
        )

    document_record: Optional[KnowledgeDocument] = None
    try:
        document_in = KnowledgeDocumentCreate(
            source_type="url",
            source_uri=url_to_ingest,
            original_filename=None,
        )
        document_record = await knowledge_document_repo.create_document(
            db=db,
            account_id=account_id,
            document_in=document_in,
            initial_status=DocumentStatus.PENDING,
        )
        await db.commit()
        await db.refresh(document_record)
        logger.info(
            f"Created KnowledgeDocument record (ID: {document_record.id}) for URL."
        )
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"Failed to create KnowledgeDocument record for URL '{url_to_ingest}': {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register URL document.",
        ) from e

    if not document_record or not document_record.id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document ID after creation.",
        )

    document_id = document_record.id

    job: Optional[Job] = None
    try:
        await wake_worker(settings.BATCH_WORKER_INTERNAL_URL)
        job = await arq_pool.enqueue_job(
            KNOWLEDGE_TASK_NAME,
            account_id=account_id,
            source_type="url",
            source_uri=url_to_ingest,
            source_identifier=source_identifier,
            document_id=document_id,
            recursive=recursive_crawl,
            _queue_name=BATCH_ARQ_QUEUE_NAME,
        )
        if not job:
            raise RuntimeError("arq_pool.enqueue_job returned None.")

        logger.info(
            f"Enqueued knowledge ingestion job '{job.job_id}' for document {document_id} (URL: {url_to_ingest}, recursive: {recursive_crawl})."
        )
        return IngestResponse(
            document_id=document_id,
            job_id=job.job_id,
            message=f"URL '{url_to_ingest}' ingestion task (recursive: {recursive_crawl}) queued.",
        )

    except (ArqConnectionError, EnqueueTimeout, RuntimeError, Exception) as q_err:
        logger.exception(
            f"Failed to enqueue ingestion task for document {document_id} (URL): {q_err}"
        )
        try:
            async with AsyncSessionLocal() as db_fail:
                await knowledge_document_repo.update_document_status(
                    db_fail,
                    document_id=document_id,
                    status=DocumentStatus.FAILED,
                    error_message=f"Failed to queue task: {q_err}",
                )
                await db_fail.commit()
        except Exception as db_err:
            logger.error(
                f"Failed to update document {document_id} status to FAILED after queue error: {db_err}"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue ingestion task for URL.",
        ) from q_err


# --- Endpoint: Add Text ---
@router.post(
    "/knowledge/add-text",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add Knowledge Text",
    description="Adds raw text content to the knowledge base for processing.",
)
async def add_knowledge_text(
    request: AddTextRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a KnowledgeDocument record for raw text and enqueues the ingestion task.
    """
    account_id: UUID = auth_context.account.id
    source_identifier = request.title
    text_content = request.content

    logger.info(
        f"Received text ingestion request: '{source_identifier}' for account {account_id}"
    )

    if not DOCUMENT_REPO_AVAILABLE or not knowledge_document_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document repository unavailable.",
        )
    if not arq_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue unavailable.",
        )

    document_record: Optional[KnowledgeDocument] = None
    try:
        document_in = KnowledgeDocumentCreate(
            source_type="text",
            source_uri=source_identifier,
            original_filename=None,
        )
        document_record = await knowledge_document_repo.create_document(
            db=db,
            account_id=account_id,
            document_in=document_in,
            initial_status=DocumentStatus.PENDING,
        )
        await db.commit()
        await db.refresh(document_record)
        logger.info(
            f"Created KnowledgeDocument record (ID: {document_record.id}) for text."
        )
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"Failed to create KnowledgeDocument record for text '{source_identifier}': {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register text document.",
        ) from e

    if not document_record or not document_record.id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document ID after creation.",
        )

    document_id = document_record.id

    job: Optional[Job] = None
    try:
        await wake_worker(settings.BATCH_WORKER_INTERNAL_URL)
        job = await arq_pool.enqueue_job(
            KNOWLEDGE_TASK_NAME,
            account_id=account_id,
            source_type="text",
            source_uri=text_content,
            source_identifier=source_identifier,
            document_id=document_id,
            _queue_name=BATCH_ARQ_QUEUE_NAME,
        )
        if not job:
            raise RuntimeError("arq_pool.enqueue_job returned None.")

        logger.info(
            f"Enqueued knowledge ingestion job '{job.job_id}' for document {document_id} (Text)."
        )
        return IngestResponse(
            document_id=document_id,
            job_id=job.job_id,
            message=f"Text content '{source_identifier}' ingestion task queued.",
        )

    except (ArqConnectionError, EnqueueTimeout, RuntimeError, Exception) as q_err:
        logger.exception(
            f"Failed to enqueue ingestion task for document {document_id} (Text): {q_err}"
        )
        try:
            async with AsyncSessionLocal() as db_fail:
                await knowledge_document_repo.update_document_status(
                    db_fail,
                    document_id=document_id,
                    status=DocumentStatus.FAILED,
                    error_message=f"Failed to queue task: {q_err}",
                )
                await db_fail.commit()
        except Exception as db_err:
            logger.error(
                f"Failed to update document {document_id} status to FAILED after queue error: {db_err}"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue ingestion task for text.",
        ) from q_err


@router.get(
    "/knowledge/status/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Knowledge Job Status",
    description="Checks the status of a previously enqueued Knowledge background job.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Job ID not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Task queue unavailable"},
    },
)
async def get_knowledge_job_status(
    job_id: str,
    # auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> JobStatusResponse:
    """
    Retrieves the status of a background Knowledge job using its ID.
    """
    logger.info(f"Checking status for job ID: {job_id}")

    if not arq_pool:
        logger.error("ARQ Redis pool is not available for status check.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue unavailable.",
        )

    api_status: JobStatusEnum = JobStatusEnum.QUEUED  # Default inicial
    detail_message: Optional[str] = None

    try:
        job = Job(job_id, arq_pool)
        arq_job_status: Optional[JobStatus] = await job.status()

        logger.debug(f"Arq job status for {job_id}: {arq_job_status}")

        if arq_job_status == JobStatus.queued or arq_job_status == JobStatus.deferred:
            api_status = JobStatusEnum.QUEUED
            detail_message = "Job is waiting in the queue."
            if arq_job_status == JobStatus.deferred:
                detail_message = "Job is deferred, will run later."
        elif arq_job_status == JobStatus.in_progress:
            api_status = JobStatusEnum.IN_PROGRESS
            detail_message = "Job is currently being processed."
        elif arq_job_status == JobStatus.complete:
            api_status = JobStatusEnum.COMPLETE
            detail_message = "Job finished."
        elif arq_job_status == JobStatus.not_found:
            api_status = JobStatusEnum.QUEUED
            detail_message = "Job status not yet available, assuming queued."
            logger.warning(
                f"Arq status for job {job_id} is 'not_found'. Reporting as QUEUED for polling."
            )
        else:
            api_status = JobStatusEnum.FAILED
            detail_message = f"Job has an unexpected status: {arq_job_status}"
            logger.error(detail_message)

        if api_status == JobStatusEnum.FAILED or arq_job_status == JobStatus.complete:
            try:

                job_info = await job.info()
                logger.debug(f"Job Info for {job_id}: {job_info}")

                if job_info and not job_info.success:
                    api_status = JobStatusEnum.FAILED

                    try:
                        failed_result = await job.result(timeout=0.1)
                        error_str = str(failed_result)
                    except Exception as inner_err:
                        error_str = f"Failure indicated but error details unavailable ({inner_err})"

                    detail_message = f"Job failed: {error_str[:200]}"
                    logger.warning(f"Job '{job_id}' failed. Error: {error_str}")
                elif job_info and job_info.success:
                    api_status = JobStatusEnum.COMPLETE
                    detail_message = "Knowledge task completed successfully."

            except ResultNotFound:
                logger.warning(
                    f"Job '{job_id}' status is '{api_status}' but result/info not found (likely expired)."
                )
                if api_status == JobStatusEnum.COMPLETE:
                    detail_message = " task completed (result details expired)."
                elif api_status == JobStatusEnum.FAILED:
                    detail_message = "Job failed (result details expired)."
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting result details for job '{job_id}'.")
            except Exception as res_err:
                logger.exception(
                    f"Error getting result/info details for job '{job_id}': {res_err}"
                )

        return JobStatusResponse(
            job_id=job_id, status=api_status, detail=detail_message
        )

    except ConnectionError as redis_err:
        logger.exception(f"Redis connection error during status check: {redis_err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue connection error.",
        ) from redis_err
    except Exception as e:
        logger.exception(f"Unexpected error during status check for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check job status.",
        ) from e


# --- List Documents Endpoint ---
@router.get(
    "/knowledge/documents",
    response_model=PaginatedKnowledgeDocumentRead,  # Returns list directly for now
    # For full pagination use response_model=KnowledgeDocumentList
    summary="List Knowledge Documents",
    description="Retrieves a list of knowledge base documents for the authenticated account.",
)
async def list_knowledge_documents(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(
        100, ge=1, le=200, description="Maximum number of documents to return"
    ),
) -> PaginatedKnowledgeDocumentRead:
    """
    Fetches knowledge documents associated with the user's active account.
    """
    account_id: UUID = auth_context.account.id
    logger.info(
        f"Listing knowledge documents for account {account_id} (skip={skip}, limit={limit})"
    )

    if not DOCUMENT_REPO_AVAILABLE or not knowledge_document_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document repository unavailable.",
        )

    try:
        documents = await knowledge_document_repo.list_documents_by_account(
            db=db, account_id=account_id, skip=skip, limit=limit
        )
        count_documents = await knowledge_document_repo.count_documents(
            db=db, account_id=account_id
        )
        return PaginatedKnowledgeDocumentRead(total=count_documents, items=documents)

    except Exception as e:
        logger.exception(f"Error listing documents for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents.",
        ) from e


# --- Delete Document Endpoint ---
@router.delete(
    "/knowledge/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,  # HTTP 204 on successful deletion
    summary="Delete Knowledge Document",
    description="Deletes a specific knowledge document and all its associated chunks.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Document not found"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Permission denied to delete this document"
        },
    },
)
async def delete_knowledge_document(
    document_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Deletes a knowledge document by its ID, ensuring the user owns it.
    """
    account_id: UUID = auth_context.account.id
    logger.warning(
        f"Attempting to delete document {document_id} by account {account_id}"
    )

    if not DOCUMENT_REPO_AVAILABLE or not knowledge_document_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document repository unavailable.",
        )

    try:
        # Permission check: ensure the document belongs to the user
        doc_to_delete = await knowledge_document_repo.get_document_by_id(
            db, document_id
        )
        if not doc_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
            )
        if doc_to_delete.account_id != account_id:
            logger.error(
                f"Permission denied for account {account_id} to delete document {document_id} owned by {doc_to_delete.account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied to delete this document.",
            )

        # Perform deletion
        success = await knowledge_document_repo.delete_document(
            db=db, document_id=document_id
        )
        if success:
            await db.commit()  # Commit transaction on successful deletion
            logger.info(
                f"Successfully deleted document {document_id} for account {account_id}"
            )
            return None
        else:
            await db.rollback()
            logger.error(f"Unexpected deletion failure for document {document_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete document.",
            )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error deleting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document.",
        ) from e
