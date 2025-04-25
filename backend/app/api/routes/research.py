# backend/app/api/routers/research.py

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from uuid import UUID, uuid4
from typing import Optional

# Arq imports
from arq.connections import ArqRedis, Job
from redis.exceptions import ConnectionError


# Project imports
from app.core.arq_manager import get_arq_pool  # Assuming this path is correct
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.research import ResearchRequest, ResearchResponse

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
    auth_context: AuthContext = Depends(get_auth_context),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ResearchResponse:
    """
    Accepts a URL and enqueues a background job to research and create
    a company profile associated with the authenticated user's active account.
    """
    account_id: UUID = auth_context.account.id
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
        # Enqueue the job to the queue the researcher worker listens to
        # The queue name is defined in the worker's WorkerSettings
        job: Optional[Job] = await arq_pool.enqueue_job(
            RESEARCH_TASK_NAME,  # Name of the task function in researcher.py
            url=url_to_research,  # Argument for the task function
            account_id=account_id,  # Argument for the task function
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
