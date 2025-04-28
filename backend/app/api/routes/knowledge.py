import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)

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
)


router = APIRouter()


KNOWLEDGE_TASK_NAME = "process_knowledge_source"
KNOWLEDGE_QUEUE_NAME = "knowledge_ingestion_queue"


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
        job = await arq_pool.enqueue_job(
            KNOWLEDGE_TASK_NAME,
            account_id=account_id,
            source_type="file",
            source_uri=gcs_uri,
            source_identifier=original_filename,
            document_id=document_id,
            _queue_name=KNOWLEDGE_QUEUE_NAME,
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
    source_identifier = url_to_ingest

    logger.info(
        f"Received URL ingestion request: '{url_to_ingest}' for account {account_id}"
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
        job = await arq_pool.enqueue_job(
            KNOWLEDGE_TASK_NAME,
            account_id=account_id,
            source_type="url",
            source_uri=url_to_ingest,
            source_identifier=source_identifier,
            document_id=document_id,
            _queue_name=KNOWLEDGE_QUEUE_NAME,
        )
        if not job:
            raise RuntimeError("arq_pool.enqueue_job returned None.")

        logger.info(
            f"Enqueued knowledge ingestion job '{job.job_id}' for document {document_id} (URL)."
        )
        return IngestResponse(
            document_id=document_id,
            job_id=job.job_id,
            message=f"URL '{url_to_ingest}' ingestion task queued.",
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
    source_identifier = request.description
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
        job = await arq_pool.enqueue_job(
            KNOWLEDGE_TASK_NAME,
            account_id=account_id,
            source_type="text",
            source_uri=text_content,
            source_identifier=source_identifier,
            document_id=document_id,
            _queue_name=KNOWLEDGE_QUEUE_NAME,
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
