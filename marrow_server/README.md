# Marrow — Version 1.0.0

> _The AI-native project management backbone._

Marrow is a self-hosted **Model Context Protocol (MCP)** server ecosystem built for agentic development workflows. It gives AI agents a persistent, semantically searchable memory for both project knowledge (tasks, documents, decisions) and live source code structure.

---

## 🏗️ Architecture

Marrow consists of two cooperating services:

```
┌──────────────────────────────────────────────────────┐
│                    AI Agent / IDE                     │
│         (Claude, Cursor, Antigravity, etc.)           │
└────────────────────┬─────────────────────────────────┘
                     │  MCP (Streamable HTTP / stdio)
                     ▼
┌──────────────────────────────────────────────────────┐
│                  marrow_server                        │
│  ┌────────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │  mcp_core  │  │  FastAPI │  │  LanceDB (vectors) │ │
│  │  (tools)   │  │  (REST)  │  │  + Markdown blobs  │ │
│  └────────────┘  └──────────┘  └───────────────────┘ │
└────────────────────┬─────────────────────────────────┘
                     │  POST /api/vectorize
                     │
┌────────────────────▼─────────────────────────────────┐
│                  marrow_worker                        │
│   Watches filesystem → extracts code skeletons →      │
│   embeds → delivers via persistent SQLite outbox      │
└──────────────────────────────────────────────────────┘
```

### Components

| Component | Role |
|---|---|
| **`marrow_server`** | Core MCP + REST server. Manages tasks, artifacts, semantic search, and code skeleton index. |
| **`marrow_worker`** | Background file watcher. Parses source code, generates embeddings, and pushes skeletons to `marrow_server`. See [`../marrow_worker/README.md`](../marrow_worker/README.md). |
| **`marrow_common`** | Shared schemas and utilities (e.g. `SkeletonChunk`, `SCHEMA_VERSION`). |

### Service internals

- **Transports, one codebase:** MCP (Streamable HTTP, `2025-03-26`) and REST are sibling ASGI apps behind a `PrefixDispatcher` (`src/transport/app_factory.py`). MCP mounts at `/`; REST lives at `/api/v1/projects/{project}` and falls through to MCP when `REST_API_ENABLED=false` (ADR-0053).
- **Shared logic:** both transports call the same `operations/` layer, so MCP tool parameter names equal REST body/query field names — enforced by the `test_rest_mcp_parity` CI test (ADR-0054). Not exposed on REST: `list_projects`, `init_project`, `run_project_build`.
- **Layers:** `transport/` (FastAPI app, middleware, routers incl. `rest/`, `oauth_router`, `vectorize_router`) → `tools/` (MCP tool implementations) → `services/` (business logic, incl. `api_key_service` for `API_KEYS`) → `storage/` (LanceDB repositories + Markdown blob I/O) → `models.py` / `config.py`. Domain logic stays transport-agnostic.
- **Storage:** LanceDB vectors + metadata (`EMBEDDING_MODEL_CODE` for code, `EMBEDDING_MODEL_TEXT` for tasks/artifacts, `EMBEDDING_DIMENSIONS=384`) plus Markdown blobs for task/artifact content. Worker ingest is a separate internal contract: `POST /api/vectorize` (schema-versioned, 422 on mismatch).
- **Worker pipeline:** filesystem events → debounce → tree-sitter parse (multi-language, ADR-0022) → skeleton extract → lazy `sentence-transformers` encode → SQLite outbox (`WORKER_OUTBOX_PATH`, `WORKER_FLUSH_INTERVAL_SECONDS`, `WORKER_FLUSH_CONCURRENCY`) → batched POST to server. Full worker reference: [`../marrow_worker/README.md`](../marrow_worker/README.md).

---

## ✨ Key Features

- **Semantic Search** — Find tasks, documents, or code units using natural language.
- **Code Skeleton Index** — Browse class/method signatures across your entire codebase without reading files.
- **Artifact Vault** — Versioned Markdown files for specs, ADRs, session state, and feature plans.
- **Multi-Project Isolation** — Each project has its own isolated LanceDB index and artifact storage.
- **Atomic Task Updates** — 2-phase-commit pattern with rollback prevents corrupted state.
- **Worker Outbox Pattern** — SQLite-backed delivery queue ensures no skeleton updates are lost during network instability.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+ (dependencies such as LanceDB, tree-sitter grammars and the embedding model are installed by `pip install -e .`)

### 1. Configure `marrow_server`

Create a `.env` file in the `marrow_server/` root:

```env
SECRET_TOKEN=your_secure_token_min_16_chars
TASKS_DIR=C:/Path/To/Your/Marrow/Data


# Embedding models
EMBEDDING_MODEL_CODE=BAAI/bge-small-en-v1.5
EMBEDDING_MODEL_TEXT=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSIONS=384

# REST API for third parties (see "REST API" below)
REST_API_ENABLED=true
# REST_CORS_ORIGINS=
# REST_KEY_CACHE_MAX_AGE_S=60
# REST_MAX_BODY_BYTES=5242880
# REST_MAX_CONCURRENCY=16
```

`SECRET_TOKEN` is required and should be at least 16 characters. `TASKS_DIR` is required — it is where project workspaces live.

### 2. Run the server

```bash
# From marrow_server/
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
python src/marrow_server.py
```

The server starts on `http://localhost:8000`.

### 3. Run the worker (optional, for code navigation)

```bash
# From marrow_worker/
pip install -e .
python main.py \
  --repo-dir "C:/Path/To/Your/Code" \
  --project-name "YourProject" \
  --target-url "http://localhost:8000" \
  --secret-token "your_secure_token" \
  --init
```

`--init` runs a full initial scan on first launch. Omit it on later runs. The worker's `--repo-dir` must equal the project's `SOURCE_ROOT` — see [Project settings](../README.md#project-settings-settings) in the root README.

### Project settings and REST API

Project-level `.settings` (including `SOURCE_ROOT` and REST `API_KEYS`) and the third-party REST API are documented once in the root README — see [Project settings](../README.md#project-settings-settings) and [REST API for third parties](../README.md#rest-api-for-third-parties) — instead of duplicating them here.

---

## 🧪 Running Tests

```bash
# From marrow_server/ (with .venv activated)
python -m pytest tests/ -v
```

---

## 📁 Project Structure

```
marrow_server/
├── src/
│   ├── marrow_server.py     ← Entry point (uvicorn)
│   ├── mcp_core.py          ← All MCP tool registrations
│   ├── transport/           ← FastAPI app, middleware, routers
│   ├── services/            ← Business logic layer
│   ├── storage/             ← LanceDB repositories + blob I/O
│   ├── tools/               ← MCP tool implementations
│   ├── models.py            ← Pydantic request/response models
│   └── config.py            ← Environment config
├── tests/
│   ├── unit/                ← Unit tests per area
│   └── integration/         ← End-to-end integration tests
└── docs/                    ← Agent-facing specs, ADRs, session state
```

---

## 🗺️ Roadmap

- **v1.1.0**: Enhanced surgical code navigation and multi-agent handoff automation.
- **v2.0.0**: Web-based administration UI and multi-user collaboration support.

---

## 📄 License

MIT License. See [`LICENSE`](../LICENSE) for details.
