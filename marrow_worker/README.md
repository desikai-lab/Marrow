# Marrow Worker — Version 1.0.0

> _The code skeleton indexer for the Marrow ecosystem._

Marrow Worker is a background service that watches your local source code, extracts structural skeletons (namespaces, classes, method signatures), generates vector embeddings, and pushes them to `marrow_server` for AI-powered semantic code navigation.

---

## How It Works

```
Your Codebase (filesystem)
    │
    │  watchdog (file events)
    ▼
marrow_worker
    ├── Parser        → Extracts skeletons (class/method/namespace signatures)
    ├── Embedder      → Generates vectors via sentence-transformers (local, offline)
    ├── WorkerOutbox  → SQLite-backed persistent delivery queue
    │
    │  POST /api/vectorize  (Bearer token)
    ▼
marrow_server  →  LanceDB skeleton index
```

The **Worker Outbox pattern** ensures that skeleton updates are never lost — even if `marrow_server` is temporarily unavailable, payloads are queued in a local SQLite database and flushed on reconnect.

---

## Features

- **Multi-language parsing** — Supports Python, TypeScript, C#, and more (tree-sitter grammars).
- **Offline embeddings** — Uses `sentence-transformers` locally; no API keys or internet access required during operation (after first model download).
- **Persistent outbox** — SQLite-backed queue guarantees at-least-once delivery.
- **Debounced events** — Batches rapid file changes to avoid redundant re-indexing.
- **Initial scan** — `--init` flag performs a full repository index on first launch.
- **Graceful shutdown** — Flushes pending payloads and closes connections cleanly on CTRL+C.

---

## Prerequisites

- Python 3.12+ (dependencies such as `sentence-transformers` and `watchdog` are installed by `pip install -e .`)

Install all dependencies:

```bash
pip install -e .
```

> Full setup (server first, project wiring, connecting your agent) lives in the [root README](../README.md#quickstart-5-minutes). This file is the worker-specific reference.

### Downloading the embedding model (required when `HF_HUB_OFFLINE=1`)

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

You must pre-download the model before setting `HF_HUB_OFFLINE=1` — offline mode prevents any network calls at runtime, so a worker started offline without a cached model cannot generate embeddings. The model can also be overridden per run with `EMBEDDING_MODEL_CODE` (default `BAAI/bge-small-en-v1.5`, revision pinned in `src/embedding/lazy_model.py`).

---

## Configuration (`.env`)

```env
# Outbox: path to the persistent SQLite delivery queue
WORKER_OUTBOX_PATH=./worker_outbox.db

# Outbox: seconds between background flush attempts
WORKER_FLUSH_INTERVAL_SECONDS=60

# Outbox: concurrent flush workers (default 3)
WORKER_FLUSH_CONCURRENCY=3

# Embedding model override (default BAAI/bge-small-en-v1.5)
# EMBEDDING_MODEL_CODE=BAAI/bge-small-en-v1.5

# Prevent huggingface_hub from making network calls — only set this after pre-downloading the model (see above)
# HF_HUB_OFFLINE=1
```

---

## Running the Worker

```bash
python main.py \
  --repo-dir    "C:/Path/To/Your/Code" \
  --project-name "YourProject" \
  --target-url  "http://localhost:8000" \
  --secret-token "your_marrow_server_token" \
  --extensions  ".py,.ts,.cs" \
  --init
```

> `--repo-dir` must equal the project's `SOURCE_ROOT` in its `.settings` file — the server and the worker have to resolve the exact same path. See [Project settings](../README.md#project-settings-settings) in the root README for why, and [Option A](../README.md#option-a--docker-recommended) for the Docker values.

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--repo-dir` | `cwd` | Absolute path to the codebase to monitor. Must match the project's `SOURCE_ROOT`. |
| `--project-name` | `DefaultProject` | Project identifier used in `marrow_server`. |
| `--target-url` | `http://localhost:8000` | Base URL of the `marrow_server` instance. |
| `--secret-token` | `$MCP_SECRET_TOKEN` | Bearer token for `marrow_server` authentication (or set the `MCP_SECRET_TOKEN` env var). This is the worker-side name; the server side calls the same value `SECRET_TOKEN`. |
| `--extensions` | `.cs,.ts,.py` | Comma-separated list of file extensions to index. |
| `--polling-interval` | `1.0` (`POLLING_INTERVAL`) | File system polling interval in seconds. Lower = more responsive, higher CPU on large repos. |
| `--init` | `false` | Run a full initial scan before starting the file watcher. |

---

## Project Structure

```
marrow_worker/
├── main.py                  ← Entry point (CLI + event loop)
├── src/
│   ├── parser/              ← Language-specific skeleton extractors (tree-sitter)
│   ├── embedding/           ← LazyEncoder (sentence-transformers wrapper)
│   ├── transport/
│   │   ├── api_client.py    ← HTTP client for /api/vectorize
│   │   └── outbox.py        ← SQLite-backed WorkerOutbox
│   └── watcher/
│       ├── bridge.py        ← watchdog event handler → debouncer
│       └── debouncer.py     ← Async debouncer (coalesces rapid changes)
├── logs/
│   └── worker.log           ← Rotating log file
└── worker_outbox.db         ← Persistent delivery queue (SQLite)
```

---

## License

MIT License. See [`LICENSE`](../LICENSE) for details.
