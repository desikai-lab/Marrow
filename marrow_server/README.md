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
| **`marrow_worker`** | Background file watcher. Parses source code, generates embeddings, and pushes skeletons to `marrow_server`. |
| **`marrow_common`** | Shared schemas and utilities (e.g. `SkeletonChunk`, `SCHEMA_VERSION`). |

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

- Python 3.12+
- [`fastembed`](https://github.com/qdrant/fastembed) — local embedding generation (no API key required)
- [`lancedb`](https://lancedb.github.io/lancedb/) — embedded vector database

### 1. Configure `marrow_server`

Create a `.env` file in the `marrow_server/` root:

```env
SECRET_TOKEN=your_secure_token_min_16_chars
TASKS_DIR=C:/Path/To/Your/Marrow/Data


# Embedding models
EMBEDDING_MODEL_CODE=BAAI/bge-small-en-v1.5
EMBEDDING_MODEL_TEXT=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSIONS=384
```

### 2. Run the server

```powershell
# From marrow_server/
$env:PYTHONPATH="src"
python src/marrow_server.py
```

The server starts on `http://localhost:8000`.

### 3. Run the worker (optional, for code navigation)

```powershell
# From marrow_worker/
python main.py `
  --repo-dir "C:/Path/To/Your/Code" `
  --project-name "YourProject" `
  --target-url "http://localhost:8000" `
  --secret-token "your_secure_token" `
  --init
```

---

## 🧪 Running Tests

```powershell
# From marrow_server/
$env:PYTHONPATH="src"; python -m pytest tests/ -v
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

MIT License. See [`LICENSE`](LICENSE) for details.
