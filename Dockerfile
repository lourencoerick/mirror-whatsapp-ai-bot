# DevContainer Base with Python 3.11
# FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.11-bullseye

# syntax=docker/dockerfile:1.4
FROM python:3.11-slim-bullseye

# Evita buffers e interações no apt
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# 1) Instala deps de SO em uma camada só
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential cmake libsqlite3-dev \
    openssh-client sqlite3 postgresql-client redis-tools \
    && rm -rf /var/lib/apt/lists/*

# 2) Copia só o requirements e instala Python deps
COPY backend/requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install -r requirements.txt

# 3) Copia todo o código depois (maximiza cache acima)
COPY . .

# 4) Entrypoint
COPY backend/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000

CMD ["/start.sh"]
