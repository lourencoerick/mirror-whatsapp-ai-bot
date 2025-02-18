# Base do DevContainer com Python 3.11
FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.11-bullseye

# Define o diretório de trabalho
WORKDIR /workspace

# Atualiza os pacotes do sistema e instala dependências essenciais
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    build-essential \
    sqlite3 \
    libsqlite3-dev \
    cmake \
    postgresql-client \
    redis-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do projeto para dentro do container
COPY . .

# Define o usuário padrão
CMD ["bash"]
