FROM python:3.11-slim-bullseye


ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    redis-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./backend/requirements.txt .


RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY ./backend /workspace/backend

ENV PYTHONPATH /workspace/backend

CMD ["python", "-c", "print('Worker base image ready. Specify command override.')"]