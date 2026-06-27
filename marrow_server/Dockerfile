# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by some tree-sitter wheels and torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install marrow_common first (local dependency)
COPY marrow_common/ ./marrow_common/
RUN pip install --no-cache-dir ./marrow_common

# Install marrow_server
COPY marrow_server/ ./marrow_server/
RUN pip install --no-cache-dir ./marrow_server

# Runtime configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/marrow_server/src

WORKDIR /app/marrow_server

# Data directories
VOLUME ["/data", "/projects"]

EXPOSE 8000

CMD ["python", "src/marrow_server.py"]
