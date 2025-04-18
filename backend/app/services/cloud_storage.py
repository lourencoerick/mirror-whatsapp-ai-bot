import uuid
import os
from loguru import logger
from fastapi import UploadFile, HTTPException, status
from google.cloud import storage
from google.api_core.exceptions import GoogleAPICallError

from app.config import get_settings, Settings

settings: Settings = get_settings()

# Initialize the GCS client globally or via dependency injection
# Using global instance here for simplicity, but DI is often better.
# The client uses GOOGLE_APPLICATION_CREDENTIALS environment variable automatically.
try:
    storage_client = storage.Client()
except Exception as e:
    # Handle potential errors during client initialization (e.g., missing credentials)
    logger.exception(
        f"Error initializing GCS client: {e}. Ensure GOOGLE_APPLICATION_CREDENTIALS is set."
    )
    storage_client = None  # Set to None to indicate failure


def get_gcs_bucket():
    """Gets the GCS bucket instance."""
    if not storage_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Cloud Storage service is not configured or available.",
        )
    try:
        bucket = storage_client.bucket(settings.CONTACT_IMPORT_GCS_BUCKET_NAME)
        if not bucket.exists():
            # Optional: Create bucket if it doesn't exist (requires storage.buckets.create permission)
            # Or raise an error if it's expected to exist
            logger.warning(
                f"Bucket {settings.CONTACT_IMPORT_GCS_BUCKET_NAME} does not exist."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GCS Bucket '{settings.CONTACT_IMPORT_GCS_BUCKET_NAME}' not found.",
            )
        return bucket
    except GoogleAPICallError as e:
        logger.exception(
            f"Error accessing GCS bucket {settings.CONTACT_IMPORT_GCS_BUCKET_NAME}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not access GCS Bucket: {e.message}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting GCS bucket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred with Cloud Storage.",
        )


async def save_import_file_gcs(file: UploadFile, job_id: uuid.UUID) -> str:
    """
    Uploads the contact import file to Google Cloud Storage.

    Args:
        file: The uploaded file object from FastAPI.
        job_id: The unique ID of the import job.

    Returns:
        The GCS object path (blob name) where the file was stored.

    Raises:
        HTTPException: If the upload fails or GCS is unavailable.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename cannot be empty."
        )

    # Define a structured path within the bucket
    # Example: imports/aabbccdd-1122-3344-5566-ffeeddccbbaa/original_filename.csv
    # Sanitize filename if necessary, or use a fixed name like 'import.csv'
    # Using a fixed name simplifies processing later.
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension != ".csv":
        # Enforce CSV, adjust if other types are allowed later
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are allowed.",
        )

    blob_name = f"imports/{job_id}/import.csv"  # Consistent name within job folder

    try:
        bucket = get_gcs_bucket()  # Get the bucket instance
        blob = bucket.blob(blob_name)

        # Read the file content asynchronously
        content = await file.read()
        await file.close()  # Close the file handle

        # Upload the content to GCS
        # upload_from_string handles bytes directly
        # Use a timeout for the upload operation
        blob.upload_from_string(
            data=content,
            content_type=file.content_type
            or "text/csv",  # Use provided content type or default
            timeout=120,  # Example: 2 minutes timeout
        )

        print(
            f"File uploaded to GCS: gs://{settings.CONTACT_IMPORT_GCS_BUCKET_NAME}/{blob_name}"
        )  # Logging
        return blob_name  # Return the object path/name

    except GoogleAPICallError as e:
        print(f"GCS Upload Error: {e}")
        # Provide a more specific error message if possible
        detail = f"Could not upload file to Cloud Storage: {e.message}"
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if e.code == 503
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=detail)
    except HTTPException as e:
        # Re-raise HTTPExceptions from get_gcs_bucket or validation
        raise e
    except Exception as e:
        print(f"Unexpected error during GCS upload: {e}")  # Use proper logging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving the file.",
        )
    finally:
        # Ensure file is closed even if errors occur before explicit close
        if hasattr(file, "close") and not file.file.closed:
            await file.close()
