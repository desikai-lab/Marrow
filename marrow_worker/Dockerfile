# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Upgrade build tooling in builder stage
RUN pip install --no-cache-dir --upgrade pip 'setuptools>=70.0.0' 'wheel>=0.46.2'

# Install CPU-only torch pinned (CPU index wheels differ from default PyPI
# CUDA wheels, so torch is pinned separately before dependency resolution).
RUN pip install --no-cache-dir 'torch==2.14.0' --index-url https://download.pytorch.org/whl/cpu

# Install runtime dependencies from requirements.txt (B4000278: hashed
# lockfiles retired). With full dependency resolution, the pre-installed
# CPU torch satisfies `torch>=2.2` and pip keeps it (no CUDA wheels pulled).
# Installed into the default /usr/local (NOT --prefix=/install): anything pip
# deems "already satisfied" in the builder must still land in the final
# stage, and only a full /usr/local copy guarantees that (B4000279).
COPY marrow_worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install local packages without deps (all runtime deps already installed above).
COPY marrow_common/ ./marrow_common/
COPY marrow_worker/ ./marrow_worker/
RUN pip install --no-cache-dir --no-deps ./marrow_common ./marrow_worker

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY marrow_common/ ./marrow_common/
COPY marrow_worker/ ./marrow_worker/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/marrow_worker/src

WORKDIR /app/marrow_worker

# Mount your source repositories here
VOLUME ["/watch"]

CMD ["python", "main.py"]

