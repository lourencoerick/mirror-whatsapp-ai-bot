#!/bin/sh
# worker-entrypoint.sh

# Exit immediately if a command exits with non-zero status
set -e

# Start a simple HTTP server in the background on the port specified by Cloud Run ($PORT)
# It only needs to listen; it doesn't need to serve anything meaningful.
echo "Starting dummy HTTP server on port ${PORT:-8080} for Cloud Run health check..."
python3 -m http.server ${PORT:-8080} --bind 0.0.0.0 &

# Now, execute the actual command passed to the container
# (this will be the command specified in Cloud Run's 'command' and 'args')
echo "Executing main worker command: $@"
exec "$@"