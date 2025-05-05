# backend/app/workers/worker_http_server.py

import os
import uvicorn
from fastapi import FastAPI, status

# Get the port from the environment variable set by Cloud Run, default to 8080
PORT = int(os.getenv("PORT", 8080))

# Create a minimal FastAPI application instance
http_server_app = FastAPI(
    title="Worker HTTP Server",
    description="Minimal server to handle Cloud Run health/scaling checks.",
    docs_url=None,  # Disable docs for this internal server
    redoc_url=None,
)


@http_server_app.get(
    "/_internal/keep_alive",
    status_code=status.HTTP_200_OK,
    tags=["Internal"],
    summary="Simple endpoint for Cloud Scheduler pings",
    response_description="Returns a simple status message.",
)
async def keep_alive():
    """
    Handles GET requests to /_internal/keep_alive.

    This endpoint is used by Cloud Scheduler to periodically ping the service,
    allowing Cloud Run to scale from zero instances when needed.

    Returns:
        dict: A simple JSON response indicating the service is alive.
    """
    return {"status": "alive"}


# Add a root endpoint just for basic verification if needed
@http_server_app.get("/", include_in_schema=False)
async def root():
    return {"message": "Worker HTTP server is running."}


if __name__ == "__main__":
    print(f"Starting worker HTTP server on 0.0.0.0:{PORT}...")
    # Run uvicorn programmatically
    uvicorn.run(
        http_server_app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",  # Keep logs quieter for this simple server
        workers=1,  # Only need one worker process for this simple task
    )
