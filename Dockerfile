# DevContainer Base with Python 3.11
# FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.11-bullseye
FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /workspace

# Update system packages and install essential dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    build-essential \
    sqlite3 \
    libsqlite3-dev \
    cmake \
    postgresql-client \
    redis-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Python Dependencies Installation ---
COPY ./backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt


ENV PYTHONPATH /workspace/backend

# --- Final Setup ---
# Specify the port that the container will expose
EXPOSE 8000

# Copy the project files into the container
COPY . .

# --- Entrypoint Setup ---
COPY ./backend/start.sh /start.sh
RUN chmod +x /start.sh

# Set the default user command
CMD ["/start.sh"]
