#!/bin/sh
# backend/app/workers/worker-entrypoint.sh

# Exit immediately if a command exits with non-zero status
set -e

# Define the path to the HTTP server script relative to WORKDIR (/workspace)
HTTP_SERVER_SCRIPT="/workspace/backend/app/workers/worker_http_server.py"

# Start the dedicated FastAPI HTTP server in the background
echo "Starting worker HTTP server in background from ${HTTP_SERVER_SCRIPT}..."
python3 ${HTTP_SERVER_SCRIPT} &

# Store the PID of the background server (optional, for potential cleanup)
HTTP_SERVER_PID=$!
echo "HTTP Server running with PID ${HTTP_SERVER_PID}"

# Now, execute the actual command passed to the container (e.g., arq ...)
# This command comes from the 'args' defined in the Cloud Run service definition.
echo "Executing main worker command: $@"
exec "$@"

# Optional: Cleanup background process on exit (might not always execute depending on how the main command exits)
# trap "echo 'Stopping HTTP server...'; kill $HTTP_SERVER_PID" SIGINT SIGTERM
# wait $HTTP_SERVER_PID