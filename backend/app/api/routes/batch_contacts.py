# app/routers/batch_contacts.py

from uuid import UUID, uuid4
import json
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Path
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from arq import ArqRedis  # Assuming ARQ with Redis
from loguru import logger

# --- Local Imports ---
# Adjust these paths based on your project structure

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
    ContactImportError,
)

# Authentication
from app.core.dependencies.auth import get_auth_context, AuthContext

# s
from app.services.cloud_storage import save_import_file_gcs  # GCS Upload function
from app.workers.batch_contacts.contact_importer import ARQ_TASK_NAME
from app.config import get_settings, Settings  # Importa as configurações

settings: Settings = get_settings()

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
    # Use actual user/account ID from authentication context
    account_id = auth_context.account.id  # Example: Assuming user model has account_id

    job_id = uuid4()

    # 1. Upload File to GCS
    try:
        # The save_import_file_gcs function should handle basic validation (e.g., .csv extension)
        gcs_blob_name = await save_import_file_gcs(file=file, job_id=job_id)
        logger.success(
            f"File uploaded to GCS. Bucket: {settings.GCS_BUCKET_NAME}, Blob: {gcs_blob_name}"
        )  # Use proper logging
    except HTTPException as http_exc:
        # Re-raise specific HTTP errors from the upload function (e.g., 400, 404, 503)
        raise http_exc
    except Exception as e:
        # Catch unexpected errors during upload
        logger.exception(
            f"Unexpected error saving file to GCS: {e}"
        )  # Use proper logging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during file upload.",
        )

    # 2. Create ImportJob record in Database
    db_job = ImportJob(
        id=job_id,
        account_id=account_id,  # Use real account_id
        status=ImportJobStatus.PENDING,  # Initial status
        file_key=gcs_blob_name,  # Store the GCS blob name/path
        arq_task_id=None,  # ARQ task ID will be added after enqueuing
        result_summary={},  # Initialize result summary as empty dict or null
    )
    try:
        db.add(db_job)
        await db.commit()
        await db.refresh(db_job)
        logger.info(
            f"ImportJob {job_id} created in DB with status PENDING."
        )  # Use proper logging
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"Error creating ImportJob in DB for job {job_id}: {e}"
        )  # Use proper logging
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
        # Enqueue the job defined in your ARQ worker settings
        arq_task = await arq_pool.enqueue_job(
            ARQ_TASK_NAME,  # Name of the task function (e.g., 'process_contact_csv_task')
            _job_id=f"contact_import_{job_id}",  # Optional: Custom ARQ job ID for traceability
            # Pass necessary identifiers for the task to retrieve job details
            job_pk=db_job.id,  # Pass the primary key of our ImportJob record
            account_id=db_job.account_id,
        )
        if not arq_task:
            # This case might happen if the queue is full or connection lost momentarily
            raise ConnectionError("Failed to enqueue job: ARQ pool returned None.")

        arq_job_id = arq_task.job_id  # Get the actual job ID from ARQ
        logger.info(
            f"Task enqueued via ARQ with ARQ Job ID: {arq_job_id} for ImportJob {job_id}\n------{arq_task}"
        )  # Use proper logging

        # 4. Update ImportJob with ARQ Task ID
        db_job.arq_task_id = arq_job_id
        await db.commit()
        logger.info(
            f"ImportJob {job_id} updated with ARQ task_id."
        )  # Use proper logging

    except Exception as e:
        logger.exception(
            f"Error enqueuing task or updating job for ImportJob {job_id}: {e}"
        )  # Use proper logging
        # If enqueuing fails, mark our DB job as FAILED
        db_job.status = ImportJobStatus.FAILED
        db_job.result_summary = {
            "error": "Failed to enqueue processing task",
            "detail": str(e),
        }
        await db.commit()
        # No need to re-raise here, we will return the final response,
        # but the job status reflects the failure to enqueue.
        # However, it might be better UX to return 500 if enqueuing fails critically.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not enqueue import task: {e}",
        )

    # 5. Return Success Response (202 Accepted)
    response_data = ContactImportJobStartResponse(
        job_id=db_job.id,
        status=str(db_job.status.value),  # Return current status (should be PENDING)
    )
    return response_data


@router.get(
    "/contacts/batch/import/status/{job_id}",
    response_model=ContactImportJobStatusResponse,
    summary="Get Contact Batch Import Job Status",
    description="Retrieves the current status and results (if available) "
    "for a specific contact import job.",
    responses={
        404: {"description": "Import job not found or access denied."},
        # Add other potential responses like 401/403 if auth is active
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
    # Use actual user/account ID from authentication context
    account_id = auth_context.account.id

    # Query the database for the job using AsyncSession
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

    # --- Handle result_summary parsing (if needed) ---
    # Pydantic's from_attributes=True handles this well if the DB model's
    # result_summary field is a dict/JSONB type.
    # If it's stored as a JSON *string*, you might need manual parsing:
    parsed_summary = None
    if isinstance(db_job.result_summary, str):  # Check if it's a string
        try:
            summary_dict = json.loads(db_job.result_summary)
            parsed_summary = ContactImportSummary(**summary_dict)
        except (json.JSONDecodeError, TypeError, ValidationError) as e:
            logger.warning(f"Could not parse result_summary JSON for job {job_id}: {e}")
            # Decide how to handle: return null, return raw string, or error?
            # Returning null is often safest.
            parsed_summary = None  # Keep as None if parsing fails
    elif isinstance(
        db_job.result_summary, dict
    ):  # If it's already a dict (e.g., from JSONB)
        try:
            # Validate dict against the schema
            parsed_summary = ContactImportSummary(**db_job.result_summary)
        except ValidationError as e:
            logger.warning(
                f"Could not validate result_summary dict for job {job_id}: {e}"
            )
            parsed_summary = None  # Keep as None if validation fails

    # Create the response object using the Pydantic model
    # Pydantic automatically maps fields by name due to Config.from_attributes = True
    # We override result_summary if we did manual parsing/validation
    response_data = ContactImportJobStatusResponse.model_validate(db_job)
    response_data.result_summary = parsed_summary  # Assign the parsed/validated summary

    # Convert status Enum to string if necessary (Pydantic might handle this)
    if isinstance(response_data.status, ImportJobStatus):
        response_data.status = response_data.status.value

    return response_data
