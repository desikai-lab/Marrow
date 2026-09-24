# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Upgrade build tooling in builder stage
RUN pip install --no-cache-dir --upgrade pip 'setuptools>=70.0.0' 'wheel>=0.46.2'

# Install hashed runtime lockfile (TD4000273, ADR-0052 Decision 7).
# --no-deps: lock already lists the full transitive closure.
COPY marrow_server/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --prefix=/install --require-hashes --no-deps -r requirements.lock

# Install local packages without deps (all runtime deps already in the prefix layer).
COPY marrow_common/ ./marrow_common/
COPY marrow_server/ ./marrow_server/
RUN pip install --no-cache-dir --prefix=/install --no-deps ./marrow_common ./marrow_server

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY marrow_common/ ./marrow_common/
COPY marrow_server/ ./marrow_server/

# Runtime configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/marrow_server/src

WORKDIR /app/marrow_server

# Data directories
VOLUME ["/data", "/projects"]

EXPOSE 8000

CMD ["python", "src/marrow_server.py"]

