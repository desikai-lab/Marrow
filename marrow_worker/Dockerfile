# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install marrow_common first (local dependency)
COPY marrow_common/ ./marrow_common/
RUN pip install --no-cache-dir ./marrow_common

# Install marrow_worker
COPY marrow_worker/ ./marrow_worker/
RUN pip install --no-cache-dir ./marrow_worker

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/marrow_worker/src

WORKDIR /app/marrow_worker

# Mount your source repositories here
VOLUME ["/watch"]

CMD ["python", "main.py"]
