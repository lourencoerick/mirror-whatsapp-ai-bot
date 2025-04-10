# app/worker/tasks.py

import uuid
import csv
import io
import datetime
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from typing import AsyncGenerator
from loguru import logger

# --- Local Imports ---
from app.database import AsyncSessionLocal
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.contact import Contact
from app.api.schemas.contact import ContactCreate
from app.api.schemas.contact_importer import ContactImportSummary, ContactImportError
from app.services.repository import contact as contact_repo
from app.services.helper.contact import normalize_phone_number
from app.services.cloud_storage import get_gcs_bucket

# --- Async Database Session Management for Worker ---


@asynccontextmanager
async def get_worker_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional scope around a series of async operations."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Commit on successful exit
        except Exception:
            await session.rollback()  # Rollback on exception
            raise


async def _create_contact_in_db_async(
    db: AsyncSession, contact_data: ContactCreate, account_id: uuid.UUID
) -> Contact | None:
    """
    Placeholder: Creates a single contact asynchronously in the database.

    Args:
        db: The async database session.
        contact_data: Pydantic model with validated contact data.
        account_id: The account ID to associate the contact with.

    Returns:
        The created Contact object or None if creation failed (e.g., duplicate).

    Raises:
        Exception: For unexpected database errors.
    """
    normalized_phone = normalize_phone_number(contact_data.phone_number)
    if not normalized_phone:
        raise ValidationError(
            detail=f"Invalid or unparseable phone number: {contact_data.phone_number}",
        )

    # Check if identifier already exists for an *active* contact
    existing_contact = await contact_repo.find_contact_by_identifier(
        db=db, identifier=normalized_phone, account_id=account_id
    )

    if existing_contact:
        logger.info(f"Skipping duplicate phone number: {contact_data.phone_number}")
        return None

    try:
        new_contact = await contact_repo.create_contact(
            db=db, contact_data=contact_data, account_id=account_id
        )
        db.add(new_contact)
        await db.flush()  # Await flush to catch constraints early
        await db.commit()
        await db.refresh(new_contact)  # Await refresh if needed
        logger.success(
            f"Contact created: {new_contact.name} ({new_contact.phone_number})"
        )
        return new_contact
    except Exception as e:
        # Context manager will rollback
        logger.exception(
            f"Unexpected DB error creating contact {contact_data.phone_number}: {e}"
        )
        raise  # Re-raise unexpected errors to fail the job


# --- ARQ Task Definition (Async) ---
async def process_contact_csv_task(ctx, job_pk: uuid.UUID, account_id: uuid.UUID):
    """
    ARQ task to process a CSV file from GCS for contact import using AsyncSession.

    Args:
        ctx: The ARQ context.
        job_pk: The primary key of the ImportJob record.
        account_id: The account ID associated with this job.
    """
    print(
        f"Starting async task process_contact_csv_task for job_pk: {job_pk}, account_id: {account_id}"
    )

    job_status = ImportJobStatus.PROCESSING
    result_summary_data = {}
    finished_time = datetime.datetime.now(datetime.timezone.utc)

    try:
        # Use async context manager for DB session
        async with get_worker_async_db_session() as db:

            # 1. Fetch the ImportJob record (Async)
            stmt = select(ImportJob).where(
                ImportJob.id == job_pk, ImportJob.account_id == account_id
            )
            result = await db.execute(stmt)
            db_job = result.scalars().first()

            if not db_job:
                logger.error(f"ImportJob not found for job_pk: {job_pk}")
                return

            if db_job.status != ImportJobStatus.PENDING:
                logger.warning(
                    f"Job {job_pk} already processed or processing (status: {db_job.status}). Skipping."
                )
                return

            # 2. Update Job Status to Processing (Async)
            db_job.status = ImportJobStatus.PROCESSING
            # Commit is handled by the context manager at the end,
            # but we might want intermediate commits for status updates.
            # Let's commit the status change explicitly here.
            await db.commit()
            print(f"Job {job_pk} status updated to PROCESSING.")

            # --- Start Processing Logic ---
            total_rows = 0
            successful_imports = 0
            failed_imports = 0
            errors_list: list[ContactImportError] = []

            try:
                # 3. Get File from GCS (Run blocking I/O in thread)
                print(f"Fetching file {db_job.file_key} from GCS...")
                bucket = (
                    get_gcs_bucket()
                )  # Assuming get_gcs_bucket is synchronous setup
                blob = bucket.blob(db_job.file_key)

                # Check existence (synchronous, run in thread)
                blob_exists = await asyncio.to_thread(blob.exists)
                if not blob_exists:
                    raise FileNotFoundError(f"GCS file not found: {db_job.file_key}")

                # Download (synchronous, run in thread)
                csv_content_bytes = await asyncio.to_thread(blob.download_as_bytes)
                print(f"File {db_job.file_key} downloaded.")

                # Decode (synchronous, CPU-bound, usually fast enough)
                try:
                    csv_content_string = csv_content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        csv_content_string = csv_content_bytes.decode("latin-1")
                        print(
                            f"Warning: Decoded CSV for job {job_pk} using latin-1 encoding."
                        )
                    except UnicodeDecodeError:
                        raise ValueError(
                            "Cannot decode CSV file. Ensure it's UTF-8 or Latin-1 encoded."
                        )

                csv_file = io.StringIO(csv_content_string)

                # 4. Process CSV Rows (Remains synchronous CPU-bound logic)
                reader = csv.DictReader(
                    csv_file,
                    fieldnames=["name", "phone_number", "email"],
                    skipinitialspace=True,
                )
                header = next(reader)
                print(f"CSV Header: {header}")

                for i, row in enumerate(reader):
                    row_number = i + 2
                    total_rows += 1
                    print(f"Processing row {row_number}: {row}")

                    try:
                        if not row.get("name") or not row.get("phone_number"):
                            raise ValueError(
                                "Missing required field: 'name' or 'phone_number'"
                            )

                        cleaned_phone = "".join(
                            filter(str.isdigit, row["phone_number"])
                        )
                        if not cleaned_phone:
                            raise ValueError("Invalid phone number format")

                        contact_input = ContactCreate(
                            name=row["name"].strip(),
                            phone_number=cleaned_phone,
                            email=row.get("email", "").strip() or None,
                        )

                        # Attempt to create contact (Async)
                        created_contact = await _create_contact_in_db_async(
                            db=db, contact_data=contact_input, account_id=account_id
                        )

                        if created_contact:
                            successful_imports += 1
                        else:
                            failed_imports += 1
                            errors_list.append(
                                ContactImportError(
                                    row_number=row_number,
                                    reason="Skipped: Duplicate phone number.",
                                    data=row,
                                )
                            )

                    except ValidationError as e:
                        failed_imports += 1
                        errors_list.append(
                            ContactImportError(
                                row_number=row_number,
                                reason=f"Validation Error: {e.errors()}",
                                data=row,
                            )
                        )
                    except ValueError as e:
                        failed_imports += 1
                        errors_list.append(
                            ContactImportError(
                                row_number=row_number, reason=str(e), data=row
                            )
                        )
                    except Exception as e:
                        failed_imports += 1
                        errors_list.append(
                            ContactImportError(
                                row_number=row_number,
                                reason=f"Unexpected processing error: {str(e)}",
                                data=row,
                            )
                        )
                        logger.error(f"Error processing row {row_number}: {e}")
                        # Decide if row error stops import? Continue for now.

                # Processing finished successfully
                job_status = ImportJobStatus.COMPLETE
                logger.success(
                    f"CSV processing finished for job {job_pk}. Status: COMPLETE"
                )

            except FileNotFoundError as e:
                logger.exception(f"Error: File not found for job {job_pk}. {e}")
                job_status = ImportJobStatus.FAILED
                result_summary_data = {"error": "Import file not found in storage."}
            except ValueError as e:
                logger.exception(f"Error: Invalid file content for job {job_pk}. {e}")
                job_status = ImportJobStatus.FAILED
                result_summary_data = {"error": f"Invalid file content: {e}"}
            except Exception as e:
                logger.exception(f"Critical Error processing job {job_pk}: {e}")
                job_status = ImportJobStatus.FAILED
                result_summary_data = {
                    "error": f"An unexpected error occurred during processing: {str(e)}"
                }

            # --- End Processing Logic ---

            # 5. Finalize Results and Update Job (Async)
            finished_time = datetime.datetime.now(datetime.timezone.utc)
            # Re-fetch the job object within the same session if needed,
            # or ensure the original db_job object is still bound to the session.
            # It should be, as we haven't closed the session.
            db_job.finished_at = finished_time
            db_job.status = job_status

            if job_status == ImportJobStatus.COMPLETE:
                summary = ContactImportSummary(
                    total_rows_processed=total_rows,
                    successful_imports=successful_imports,
                    failed_imports=failed_imports,
                    errors=errors_list[:50],  # Limit stored errors
                )
                db_job.result_summary = summary.model_dump(mode="json")
            else:
                db_job.result_summary = result_summary_data

            # Final commit is handled by the async context manager `get_worker_async_db_session`
            logger.info(
                f"Finalizing job {job_pk} with status {job_status}. Session commit pending."
            )

    except Exception as e:
        # Catch errors outside the DB session context (e.g., initial DB connection)
        # Or errors re-raised from within the context manager
        logger.exception(f"FATAL ASYNC ERROR in task for job {job_pk}: {e}")
        # Attempt to mark the job as FAILED if possible
        try:
            async with get_worker_async_db_session() as db_fail:
                # Fetch job again in new session
                stmt_fail = select(ImportJob).where(ImportJob.id == job_pk)
                result_fail = await db_fail.execute(stmt_fail)
                job_fail = result_fail.scalars().first()

                if job_fail and job_fail.status == ImportJobStatus.PROCESSING:
                    job_fail.status = ImportJobStatus.FAILED
                    job_fail.finished_at = datetime.datetime.now(datetime.timezone.utc)
                    job_fail.result_summary = {
                        "fatal_error": f"Task failed unexpectedly: {str(e)}"
                    }
                    # Commit handled by context manager
                logger.info(f"Marked job {job_pk} as FAILED due to fatal async error.")
        except Exception as db_fail_e:
            logger.exception(
                f"Could not mark job {job_pk} as FAILED after fatal async error: {db_fail_e}"
            )

    finally:
        logger.info(f"Finished async task execution for job_pk: {job_pk}")
