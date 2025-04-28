import uuid
import os
from typing import Optional
from loguru import logger
import tempfile
from fastapi import UploadFile, HTTPException, status
from google.cloud import storage
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.exceptions import NotFound

from app.config import get_settings, Settings

settings: Settings = get_settings()

# Initialize the GCS client globally or via dependency injection
# Using a global instance here for simplicity, but dependency injection is often preferable.
# The client automatically uses the GOOGLE_APPLICATION_CREDENTIALS environment variable.
try:
    storage_client = storage.Client()
except Exception as e:

    logger.exception(
        f"Error initializing GCS client: {e}. Ensure GOOGLE_APPLICATION_CREDENTIALS is set."
    )
    storage_client = None

ALLOWED_KNOWLEDGE_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv"}


def get_gcs_bucket(bucket_name: str):
    """Gets the GCS bucket instance."""
    if not storage_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Cloud Storage service is not configured or available.",
        )
    try:
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():

            logger.warning(f"Bucket {bucket_name} does not exist.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GCS Bucket '{bucket_name}' not found.",
            )
        return bucket
    except GoogleAPICallError as e:
        logger.exception(f"Error accessing GCS bucket {bucket_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not access GCS Bucket: {e.message}",
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error getting GCS bucket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred with Cloud Storage.",
        ) from e


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

    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension != ".csv":

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are allowed.",
        )

    blob_name = f"imports/{job_id}/import.csv"

    try:
        bucket = get_gcs_bucket(settings.CONTACT_IMPORT_GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)

        content = await file.read()
        await file.close()

        blob.upload_from_string(
            data=content,
            content_type=file.content_type or "text/csv",
            timeout=120,
        )

        logger.info(
            f"File uploaded to GCS: gs://{settings.CONTACT_IMPORT_GCS_BUCKET_NAME}/{blob_name}"
        )
        return blob_name

    except GoogleAPICallError as e:
        logger.exception(f"GCS Upload Error: {e}")

        detail = f"Could not upload file to Cloud Storage: {e.message}"
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if e.code == 503
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=detail) from e
    except HTTPException as e:

        raise e
    except Exception as e:
        logger.exception(f"Unexpected error during GCS upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving the file.",
        ) from e
    finally:

        if hasattr(file, "close") and not file.file.closed:
            await file.close()


async def save_knowledge_file_gcs(
    file: UploadFile,
    account_id: uuid.UUID,
    document_id: uuid.UUID,
) -> str:
    """
    Uploads a knowledge base file to Google Cloud Storage.

    Args:
        file: The uploaded file object from FastAPI.
        account_id: The UUID of the account owning the file.
        document_id: The unique ID generated for the KnowledgeDocument record.

    Returns:
        The full GCS URI (gs://bucket-name/path/to/blob) where the file was stored.

    Raises:
        HTTPException: If the upload fails, file type is invalid, or GCS is unavailable.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename cannot be empty."
        )

    # Validate file extension
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_KNOWLEDGE_EXTENSIONS:
        allowed_str = ", ".join(ALLOWED_KNOWLEDGE_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {allowed_str}",
        )

    # Use the specific knowledge base bucket (must be configured in settings)
    if not settings.KNOWLEDGE_GCS_BUCKET_NAME:
        logger.error("KNOWLEDGE_GCS_BUCKET_NAME is not configured in settings.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Knowledge base storage is not configured.",
        )

    bucket_name = settings.KNOWLEDGE_GCS_BUCKET_NAME
    # Path structure: knowledge/account_id/document_id/original_filename.ext
    # Keeping the original name is useful for reference
    blob_name = f"knowledge/{account_id}/{document_id}/{file.filename}"

    try:
        bucket = get_gcs_bucket(bucket_name)  # Pass the correct bucket name
        blob = bucket.blob(blob_name)

        # Read content and close file
        content = await file.read()
        await file.close()

        # Upload to GCS
        logger.debug(f"Uploading knowledge file to gs://{bucket_name}/{blob_name}...")
        blob.upload_from_string(
            data=content,
            content_type=file.content_type,
            timeout=240,
        )

        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"Knowledge file uploaded successfully to GCS: {gcs_uri}")
        return gcs_uri

    except GoogleAPICallError as e:
        logger.exception(f"GCS Upload Error for knowledge file: {e}")
        detail = f"Could not upload file to Cloud Storage: {e.message}"
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if e.code == 503
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=detail) from e
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error during GCS knowledge upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving the knowledge file.",
        ) from e
    finally:
        if hasattr(file, "close") and hasattr(file, "file") and not file.file.closed:
            await file.close()


async def download_gcs_file(
    gcs_uri: str, destination_dir: Optional[str] = None
) -> Optional[str]:
    """
    Downloads a file from a GCS URI to a local temporary file or specified directory.

    Args:
        gcs_uri: The full GCS URI (gs://bucket-name/path/to/blob).
        destination_dir: Optional directory to save the file. If None, a temporary
                         directory is used.

    Returns:
        The local path to the downloaded file, or None if the download fails.
        The caller is responsible for deleting the file afterward if not in a temp dir.
    """
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        logger.error(f"Invalid GCS URI provided for download: {gcs_uri}")
        return None
    if not storage_client:
        logger.error("GCS client not available for download.")
        return None

    try:
        # Parse bucket name and blob name from the URI
        path_parts = gcs_uri[5:].split("/", 1)
        if len(path_parts) != 2:
            logger.error(f"Could not parse bucket/blob name from GCS URI: {gcs_uri}")
            return None
        bucket_name, blob_name = path_parts

        bucket = get_gcs_bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            logger.error(f"GCS object not found: {gcs_uri}")
            return None

        # Determine the destination path
        if destination_dir:
            os.makedirs(destination_dir, exist_ok=True)
            local_filename = os.path.basename(blob_name)
            destination_path = os.path.join(destination_dir, local_filename)
        else:
            # Create a named temporary file
            _, file_extension = os.path.splitext(blob_name)
            with tempfile.NamedTemporaryFile(
                suffix=file_extension, delete=False
            ) as temp_file:
                destination_path = temp_file.name
            logger.debug(f"Created temporary file for download: {destination_path}")

        # Download the file
        logger.info(f"Downloading {gcs_uri} to {destination_path}...")
        blob.download_to_filename(destination_path, timeout=180)
        logger.success(f"Successfully downloaded file to {destination_path}")

        return destination_path

    except NotFound:
        logger.error(f"GCS object not found during download attempt: {gcs_uri}")
        return None
    except GoogleAPICallError as e:
        logger.exception(f"GCS Download Error for {gcs_uri}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error during GCS download for {gcs_uri}: {e}")
        return None
