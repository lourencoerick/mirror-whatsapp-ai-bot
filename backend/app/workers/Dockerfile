# Dockerfile (for Workers)

# Use uma base slim para produção se possível
FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Instalação de Dependências Python ---
COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Copia o Código da Aplicação ---
COPY ./backend /workspace/backend

# --- Configuração do Ambiente Python ---
ENV PYTHONPATH /workspace/backend

# --- Configuração do Entrypoint ---
COPY ./backend/app/workers/worker-entrypoint.sh /worker-entrypoint.sh
RUN chmod +x /worker-entrypoint.sh


# Define o script como o ENTRYPOINT do container
ENTRYPOINT ["/worker-entrypoint.sh"]
