# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Upgrade build tooling in builder stage
RUN pip install --no-cache-dir --upgrade pip 'setuptools>=70.0.0' 'wheel>=0.46.2'

# Install CPU-only torch

RUN pip install --no-cache-dir --prefix=/install torch --index-url https://download.pytorch.org/whl/cpu

# Install marrow_common first (local dependency)
COPY marrow_common/ ./marrow_common/
RUN pip install --no-cache-dir --prefix=/install ./marrow_common

# Install marrow_worker
COPY marrow_worker/ ./marrow_worker/
RUN pip install --no-cache-dir --prefix=/install ./marrow_worker

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY marrow_common/ ./marrow_common/
COPY marrow_worker/ ./marrow_worker/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/marrow_worker/src

WORKDIR /app/marrow_worker

# Mount your source repositories here
VOLUME ["/watch"]

CMD ["python", "main.py"]

