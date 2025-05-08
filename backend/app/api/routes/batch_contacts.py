from uuid import UUID, uuid4
import json
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    status,
    Path,
    Query,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from arq import ArqRedis
from loguru import logger

# Database and Task Queue Dependencies
from app.database import get_db
from app.core.arq_manager import get_arq_pool  # Function to get ARQ pool

# Models and Schemas
from app.models.import_job import (
    ImportJob,
    ImportJobStatus,
)  # DB Model and Status Enum
from app.api.schemas.contact_importer import (
    ContactImportJobStartResponse,
    ContactImportJobStatusResponse,
    ContactImportSummary,
    PaginatedImportJobListResponse,
)

# Authentication
from app.core.dependencies.auth import get_auth_context, AuthContext


from app.services.cloud_storage import save_import_file_gcs
from app.workers.batch.contacts.tasks.contact_importer import (
    ARQ_TASK_NAME as CONTACT_IMPORTER_ARQ_TASK_NAME,
)

from app.core.wake_workers import wake_worker
from app.config import get_settings, Settings

settings: Settings = get_settings()

BATCH_ARQ_QUEUE_NAME = settings.BATCH_ARQ_QUEUE_NAME
# --- Router Setup ---
router = APIRouter(
    prefix="",
    tags=["Contacts Batch Operations"],
)


@router.post(
    "/contacts/batch/import",
    response_model=ContactImportJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate Contact Batch Import via File Upload",
    description="Upload a CSV file with contact data. The file will be processed "
    "in the background. Returns a job ID to track the import status.",
)
async def initiate_contact_import(
    file: UploadFile = File(
        ...,
        description="CSV file containing contacts. Required columns: 'name', 'phone_number'. Optional: 'email'.",
        media_type="text/csv",
    ),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Receives a contact CSV file, uploads it to Google Cloud Storage,
    creates a tracking database record (ImportJob), and enqueues a
    background task (ARQ) to process the file content.

    Args:
        file: The uploaded CSV file.
        db: Database session dependency.
        arq_pool: ARQ Redis pool dependency.
        current_user: The authenticated user performing the action.

    Returns:
        A response containing the unique ID (`job_id`) and initial status
        of the background import job.

    Raises:
        HTTPException:
            - 400 Bad Request: If the file is not a valid CSV or filename is missing.
            - 404 Not Found: If the configured GCS bucket doesn't exist.
            - 500 Internal Server Error: If database operation, file upload, or
              task enqueuing fails unexpectedly.
            - 503 Service Unavailable: If GCS or the Task Queue is not available.
    """
    account_id = auth_context.account.id

    job_id = uuid4()

    # 1. Upload File to GCS
    try:
        gcs_blob_name = await save_import_file_gcs(file=file, job_id=job_id)
        logger.success(
            f"File uploaded to GCS. Bucket: {settings.CONTACT_IMPORT_GCS_BUCKET_NAME}, Blob: {gcs_blob_name}"
        )
    except HTTPException as http_exc:

        raise http_exc
    except Exception as e:

        logger.exception(f"Unexpected error saving file to GCS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during file upload.",
        )

    # 2. Create ImportJob record in Database
    db_job = ImportJob(
        id=job_id,
        account_id=account_id,
        status=ImportJobStatus.PENDING,
        file_key=gcs_blob_name,
        original_filename=file.filename,
        arq_task_id=None,
        result_summary={},
    )
    try:
        db.add(db_job)
        await db.commit()
        await db.refresh(db_job)
        logger.info(f"ImportJob {job_id} created in DB with status PENDING.")
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error creating ImportJob in DB for job {job_id}: {e}")
        # Optional: Attempt to delete the uploaded GCS file for cleanup? (Can also fail)
        # try:
        #     bucket = get_gcs_bucket()
        #     blob = bucket.blob(gcs_blob_name)
        #     if blob.exists():
        #         blob.delete()
        #         print(f"Cleaned up GCS file: {gcs_blob_name}")
        # except Exception as cleanup_e:
        #     print(f"Failed to cleanup GCS file {gcs_blob_name} after DB error: {cleanup_e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initiate import job record.",
        )

    # 3. Enqueue Background Task (ARQ)
    arq_job_id = None
    try:
        await wake_worker(settings.RESPONSE_SENDER_WORKER_INTERNAL_URL)
        arq_task = await arq_pool.enqueue_job(
            CONTACT_IMPORTER_ARQ_TASK_NAME,
            _job_id=f"contact_import_{job_id}",
            job_pk=db_job.id,
            account_id=db_job.account_id,
            _queue_name=BATCH_ARQ_QUEUE_NAME,
        )
        if not arq_task:

            raise ConnectionError("Failed to enqueue job: ARQ pool returned None.")

        arq_job_id = arq_task.job_id
        logger.info(
            f"Task enqueued via ARQ with ARQ Job ID: {arq_job_id} for ImportJob {job_id}\n------{arq_task}"
        )

        # 4. Update ImportJob with ARQ Task ID
        db_job.arq_task_id = arq_job_id
        await db.commit()
        logger.info(f"ImportJob {job_id} updated with ARQ task_id.")

    except Exception as e:
        logger.exception(
            f"Error enqueuing task or updating job for ImportJob {job_id}: {e}"
        )

        db_job.status = ImportJobStatus.FAILED
        db_job.result_summary = {
            "error": "Failed to enqueue processing task",
            "detail": str(e),
        }
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not enqueue import task: {e}",
        )

    # 5. Return Success Response (202 Accepted)
    response_data = ContactImportJobStartResponse(
        id=db_job.id,
        status=str(db_job.status.value),
    )
    return response_data


@router.get(
    "/contacts/batch/import/status/{job_id}",
    response_model=ContactImportJobStatusResponse,
    response_model_by_alias=True,
    summary="Get Contact Batch Import Job Status",
    description="Retrieves the current status and results (if available) "
    "for a specific contact import job.",
    responses={
        404: {"description": "Import job not found or access denied."},
    },
)
async def get_contact_import_status(
    job_id: UUID = Path(..., description="The unique ID of the import job to query."),
    db: AsyncSession = Depends(get_db),  # Use AsyncSession
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Fetches the status and details of a background contact import job.

    Args:
        job_id: The UUID of the job passed in the URL path.
        db: Async database session dependency.
        current_user: The authenticated user performing the action.

    Returns:
        The job status details matching the ContactImportJobStatusResponse schema.

    Raises:
        HTTPException: 404 Not Found if the job doesn't exist or doesn't belong
                       to the requesting user's account.
    """

    account_id = auth_context.account.id

    stmt = select(ImportJob).where(
        ImportJob.id == job_id, ImportJob.account_id == account_id
    )
    result = await db.execute(stmt)
    db_job = result.scalars().first()

    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job with ID '{job_id}' not found.",
        )

    parsed_summary = None
    if isinstance(db_job.result_summary, str):
        try:
            summary_dict = json.loads(db_job.result_summary)
            parsed_summary = ContactImportSummary(**summary_dict)
        except (json.JSONDecodeError, TypeError, ValidationError) as e:
            logger.warning(f"Could not parse result_summary JSON for job {job_id}: {e}")

            parsed_summary = None
    elif isinstance(db_job.result_summary, dict):
        try:

            parsed_summary = ContactImportSummary(**db_job.result_summary)
        except ValidationError as e:
            logger.warning(
                f"Could not validate result_summary dict for job {job_id}: {e}"
            )
            parsed_summary = None

    response_data = ContactImportJobStatusResponse.model_validate(db_job)

    response_data.result_summary = parsed_summary

    if isinstance(response_data.status, ImportJobStatus):
        response_data.status = response_data.status.value

    return response_data


@router.get(
    "/contacts/batch/import/jobs",
    response_model=PaginatedImportJobListResponse,
    summary="List Contact Import Jobs",
    description="Retrieves a paginated list of contact import jobs initiated by the user.",
)
async def list_contact_import_jobs(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    size: int = Query(20, ge=1, le=100, description="Number of items per page"),
):
    """
    Fetches a paginated list of import jobs for the authenticated user's account.
    """
    account_id = auth_context.account.id
    offset = (page - 1) * size

    count_stmt = select(func.count(ImportJob.id)).where(
        ImportJob.account_id == account_id
    )
    total_items_result = await db.execute(count_stmt)
    total_items = total_items_result.scalar_one_or_none() or 0

    if total_items == 0:
        return PaginatedImportJobListResponse(
            total_items=0, total_pages=0, page=page, size=size, items=[]
        )

    select_stmt = (
        select(ImportJob)
        .where(ImportJob.account_id == account_id)
        .order_by(ImportJob.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    jobs_result = await db.execute(select_stmt)
    jobs = jobs_result.scalars().all()

    total_pages = (total_items + size - 1) // size

    return PaginatedImportJobListResponse(
        total_items=total_items,
        total_pages=total_pages,
        page=page,
        size=size,
        items=jobs,
    )
