from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from uuid import UUID, uuid4
from typing import Optional
import asyncio

from arq.connections import ArqRedis, Job
from arq.jobs import JobStatus, ResultNotFound

from redis.exceptions import ConnectionError


# Project imports
from app.core.arq_manager import get_arq_pool  # Assuming this path is correct
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.research import (
    ResearchRequest,
    ResearchResponse,
    ResearchJobStatusResponse,
    ResearchJobStatusEnum,
)


from app.core.wake_workers import wake_worker

# Define the name of the Arq task function as defined in the worker
from app.config import get_settings, Settings

settings: Settings = get_settings()

# Define the router
router = APIRouter()

RESEARCH_TASK_NAME = "run_profile_research"
BATCH_ARQ_QUEUE_NAME = settings.BATCH_ARQ_QUEUE_NAME


@router.post(
    "/research/start",
    response_model=ResearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Company Profile Research",
    description="Enqueues a background task to research a company website URL and generate/update its profile.",
)
async def start_research_task(
    request: ResearchRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ResearchResponse:
    """
    Accepts a URL and enqueues a background job to research and create
    a company profile associated with the authenticated user's active account.
    """
    account_id: UUID = auth_context.account.id
    url_to_research = str(request.url)

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
        await wake_worker(settings.BATCH_WORKER_INTERNAL_URL)
        job: Optional[Job] = await arq_pool.enqueue_job(
            RESEARCH_TASK_NAME,
            url=url_to_research,
            account_id=account_id,
            _queue_name=BATCH_ARQ_QUEUE_NAME,
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
    # auth_context: AuthContext = Depends(get_auth_context),
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

    api_status: ResearchJobStatusEnum = ResearchJobStatusEnum.QUEUED  # Default inicial
    detail_message: Optional[str] = None

    try:
        job = Job(job_id, arq_pool)
        arq_job_status: Optional[JobStatus] = await job.status()

        logger.debug(f"Arq job status for {job_id}: {arq_job_status}")

        if arq_job_status == JobStatus.queued or arq_job_status == JobStatus.deferred:
            api_status = ResearchJobStatusEnum.QUEUED
            detail_message = "Job is waiting in the queue."
            if arq_job_status == JobStatus.deferred:
                detail_message = "Job is deferred, will run later."
        elif arq_job_status == JobStatus.in_progress:
            api_status = ResearchJobStatusEnum.IN_PROGRESS
            detail_message = "Job is currently being processed."
        elif arq_job_status == JobStatus.complete:
            api_status = ResearchJobStatusEnum.COMPLETE
            detail_message = "Job finished."
        elif arq_job_status == JobStatus.not_found:
            api_status = ResearchJobStatusEnum.QUEUED
            detail_message = "Job status not yet available, assuming queued."
            logger.warning(
                f"Arq status for job {job_id} is 'not_found'. Reporting as QUEUED for polling."
            )
        else:
            api_status = ResearchJobStatusEnum.FAILED
            detail_message = f"Job has an unexpected status: {arq_job_status}"
            logger.error(detail_message)

        if (
            api_status == ResearchJobStatusEnum.FAILED
            or arq_job_status == JobStatus.complete
        ):
            try:

                job_info = await job.info()
                logger.debug(f"Job Info for {job_id}: {job_info}")

                if job_info and not job_info.success:
                    api_status = ResearchJobStatusEnum.FAILED

                    try:
                        failed_result = await job.result(timeout=0.1)
                        error_str = str(failed_result)
                    except Exception as inner_err:
                        error_str = f"Failure indicated but error details unavailable ({inner_err})"

                    detail_message = f"Job failed: {error_str[:200]}"
                    logger.warning(f"Job '{job_id}' failed. Error: {error_str}")
                elif job_info and job_info.success:
                    api_status = ResearchJobStatusEnum.COMPLETE
                    detail_message = "Research task completed successfully."

            except ResultNotFound:
                logger.warning(
                    f"Job '{job_id}' status is '{api_status}' but result/info not found (likely expired)."
                )
                if api_status == ResearchJobStatusEnum.COMPLETE:
                    detail_message = "Research task completed (result details expired)."
                elif api_status == ResearchJobStatusEnum.FAILED:
                    detail_message = "Job failed (result details expired)."
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting result details for job '{job_id}'.")
            except Exception as res_err:
                logger.exception(
                    f"Error getting result/info details for job '{job_id}': {res_err}"
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
