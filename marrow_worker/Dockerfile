# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Upgrade build tooling in builder stage
RUN pip install --no-cache-dir --upgrade pip 'setuptools>=70.0.0' 'wheel>=0.46.2'

# Install CPU-only torch pinned (TD4000273 lock excludes torch: CPU index
# wheels differ from PyPI CUDA hashes, so torch is pinned separately).
RUN pip install --no-cache-dir --prefix=/install 'torch==2.14.0' --index-url https://download.pytorch.org/whl/cpu
ENV PYTHONPATH=/install/lib/python3.12/site-packages

# Install hashed runtime lockfile (TD4000273, ADR-0052 Decision 7).
# --no-deps: lock already lists the full transitive closure; torch above is pre-satisfied.
COPY marrow_worker/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --prefix=/install --require-hashes --no-deps -r requirements.lock

# Install local packages without deps (all runtime deps already in the prefix layer).
COPY marrow_common/ ./marrow_common/
COPY marrow_worker/ ./marrow_worker/
RUN pip install --no-cache-dir --prefix=/install --no-deps ./marrow_common ./marrow_worker

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

