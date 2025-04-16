#!/bin/bash
set -e

cd /workspace/backend

echo "⌛ Applying Alembic migrations..."
alembic upgrade head

cd /workspace

echo "🚀 Starting app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
