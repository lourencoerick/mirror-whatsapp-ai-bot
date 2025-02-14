FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.11-bullseye

WORKDIR /

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openssh-client \
        build-essential \
        sqlite3 \
        libsqlite3-dev \
        cmake && \ 
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .

# Install Python dependencies
# RUN pip install --no-cache-dir -r requirements.txt