# backend/app/api/routers/research.py

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from uuid import UUID, uuid4
from typing import Optional
import asyncio

# Arq imports
from arq.connections import ArqRedis, Job
from arq.jobs import JobStatus, ResultNotFound

# from redis.exceptions import ConnectionError


# Project imports
from app.core.arq_manager import get_arq_pool  # Assuming this path is correct
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.research import (
    ResearchRequest,
    ResearchResponse,
    ResearchJobStatusResponse,
    ResearchJobStatusEnum,
)

# Define the router
router = APIRouter()

# Define the name of the Arq task function as defined in the worker
RESEARCH_TASK_NAME = "run_profile_research"
RESEARCH_QUEUE_NAME = "researcher_queue"


@router.post(
    "/research/start",
    response_model=ResearchResponse,
    status_code=status.HTTP_202_ACCEPTED,  # Use 202 Accepted for async tasks
    summary="Start Company Profile Research",
    description="Enqueues a background task to research a company website URL and generate/update its profile.",
)
async def start_research_task(
    request: ResearchRequest,
    # auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ResearchResponse:
    """
    Accepts a URL and enqueues a background job to research and create
    a company profile associated with the authenticated user's active account.
    """
    # account_id: UUID = auth_context.account.id

    account_id: UUID = UUID("0c59ccfa-dc09-4a68-a1fa-d49726b2d519")
    url_to_research = str(request.url)  # Convert HttpUrl back to string for Arq

    logger.info(
        f"Received research request for URL: {url_to_research}, Account ID: {account_id}"
    )

    if not arq_pool:
        logger.error("ARQ Redis pool is not available. Cannot enqueue job.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background task queue is currently unavailable. Please try again later.",
        )

    try:
        job: Optional[Job] = await arq_pool.enqueue_job(
            RESEARCH_TASK_NAME,
            url=url_to_research,
            account_id=account_id,
            _queue_name=RESEARCH_QUEUE_NAME,
        )

        if job:
            logger.info(
                f"Successfully enqueued research job. Job ID: {job.job_id}, Account: {account_id}"
            )
            return ResearchResponse(
                job_id=job.job_id,
                message="Company profile research task successfully queued.",
            )
        else:
            # This might happen if enqueue_job fails silently (less common)
            logger.error("arq_pool.enqueue_job returned None. Failed to enqueue job.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue background task.",
            )

    except ConnectionError as redis_err:
        logger.exception(f"Redis connection error during job enqueue: {redis_err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to the background task queue. Please try again later.",
        ) from redis_err
    except Exception as e:
        logger.exception(
            f"Unexpected error during job enqueue for account {account_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while queueing the research task.",
        ) from e


@router.get(
    "/research/status/{job_id}",
    response_model=ResearchJobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Research Job Status",
    description="Checks the status of a previously enqueued research background job.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Job ID not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Task queue unavailable"},
    },
)
async def get_research_job_status(
    job_id: str,
    # auth_context: AuthContext = Depends(get_auth_context), # Optional: Add auth if status should be protected
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ResearchJobStatusResponse:
    """
    Retrieves the status of a background research job using its ID.
    """
    logger.info(f"Checking status for job ID: {job_id}")

    if not arq_pool:
        logger.error("ARQ Redis pool is not available for status check.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue unavailable.",
        )

    try:
        # Get job status directly
        job = Job(job_id, arq_pool)
        job_status: Optional[JobStatus] = await job.status()

        # Map Arq's ResearchJobStatus enum to our API's ResearchJobStatusEnum
        status_map = {
            JobStatus.queued: ResearchJobStatusEnum.QUEUED,
            JobStatus.in_progress: ResearchJobStatusEnum.IN_PROGRESS,
            JobStatus.complete: ResearchJobStatusEnum.COMPLETE,
            JobStatus.not_found: ResearchJobStatusEnum.NOT_FOUND,  # Should be caught above, but handle defensively
        }
        api_status = status_map.get(
            job_status, ResearchJobStatusEnum.FAILED
        )  # Default to FAILED if unknown status

        detail_message: Optional[str] = None
        if api_status == ResearchJobStatusEnum.COMPLETE:
            detail_message = (
                "Research task completed successfully."  # Generic success message
            )
            # Note: The graph itself doesn't return a value, success is implicit if no error
        elif job_status == JobStatus.deferred:
            # Handle deferred status if you use it (e.g., via Retry exception)
            api_status = (
                ResearchJobStatusEnum.QUEUED
            )  # Treat deferred as queued for simplicity
            detail_message = "Job is deferred, will run later."
        elif (
            job_status == JobStatus.not_found
        ):  # Should have been caught by JobNotFound
            api_status = ResearchJobStatusEnum.NOT_FOUND
            detail_message = f"Job ID '{job_id}' not found."

        # If status indicates completion or failure, try to get more details
        if api_status in [ResearchJobStatusEnum.COMPLETE, ResearchJobStatusEnum.FAILED]:
            try:
                job_result_info = await arq_pool.job_result(
                    job_id, timeout=0.5
                )  # Short timeout
                if not job_result_info.success:
                    api_status = ResearchJobStatusEnum.FAILED
                    # Extract error message if possible
                    error_str = str(
                        job_result_info.result
                    )  # Arq stores exception string here
                    detail_message = (
                        f"Job failed: {error_str[:200]}"  # Limit error length
                    )
                    logger.warning(f"Job '{job_id}' failed. Error: {error_str}")

            except ResultNotFound:
                # Job finished but result expired or key missing - status might be stale
                logger.warning(
                    f"Job '{job_id}' status is '{job_status}' but result info not found."
                )
                if api_status == ResearchJobStatusEnum.COMPLETE:
                    detail_message = "Research task completed (result details expired)."
                # Keep status as COMPLETE/FAILED based on job_status if result missing
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout getting result details for job '{job_id}'. Status might be slightly delayed."
                )
            except Exception as res_err:
                logger.exception(
                    f"Error getting result details for job '{job_id}': {res_err}"
                )

        return ResearchJobStatusResponse(
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
