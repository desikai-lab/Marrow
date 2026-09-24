# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Upgrade build tooling in builder stage
RUN pip install --no-cache-dir --upgrade pip 'setuptools>=70.0.0' 'wheel>=0.46.2'

# Install runtime dependencies from requirements.txt (B4000278: hashed
# lockfiles retired — pip resolves the full closure at build time, which
# honours upstream environment markers that a hand-maintained lock dropped).
# Installed into the default /usr/local (NOT --prefix=/install): anything pip
# deems "already satisfied" in the builder (e.g. packaging, pulled in by the
# setuptools upgrade above) must still land in the final stage, and only a
# full /usr/local copy guarantees that (B4000279).
COPY marrow_server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install local packages without deps (all runtime deps already installed above).
COPY marrow_common/ ./marrow_common/
COPY marrow_server/ ./marrow_server/
RUN pip install --no-cache-dir --no-deps ./marrow_common ./marrow_server

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local /usr/local
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

