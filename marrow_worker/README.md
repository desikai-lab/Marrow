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
    ├── Embedder      → Generates vectors via fastembed (local, offline)
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
- **Offline embeddings** — Uses `fastembed` locally; no API keys or internet access required during operation.
- **Persistent outbox** — SQLite-backed queue guarantees at-least-once delivery.
- **Debounced events** — Batches rapid file changes to avoid redundant re-indexing.
- **Initial scan** — `--init` flag performs a full repository index on first launch.
- **Graceful shutdown** — Flushes pending payloads and closes connections cleanly on CTRL+C.

---

## Prerequisites

- Python 3.12+
- `fastembed` (embedding model must be pre-downloaded; see below)
- `watchdog`

Install all dependencies:

```bash
pip install -r requirements.txt
```

### Pre-downloading the embedding model (recommended)

```bash
python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
```

Set `HF_HUB_OFFLINE=1` in `.env` after downloading to prevent any network calls at runtime.

---

## Configuration (`.env`)

```env
# Outbox: path to the persistent SQLite delivery queue
WORKER_OUTBOX_PATH=./worker_outbox.db

# Outbox: seconds between background flush attempts
WORKER_FLUSH_INTERVAL_SECONDS=60

# Prevent huggingface_hub from making network calls — model must be pre-downloaded
HF_HUB_OFFLINE=1
```

---

## Running the Worker

```powershell
python main.py `
  --repo-dir    "C:/Path/To/Your/Code" `
  --project-name "YourProject" `
  --target-url  "http://localhost:8000" `
  --secret-token "your_marrow_server_token" `
  --extensions  ".py,.ts,.cs" `
  --init
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--repo-dir` | `cwd` | Absolute path to the codebase to monitor. |
| `--project-name` | `DefaultProject` | Project identifier used in `marrow_server`. |
| `--target-url` | `http://localhost:8000` | Base URL of the `marrow_server` instance. |
| `--secret-token` | `$MCP_SECRET_TOKEN` | Bearer token for `marrow_server` authentication. |
| `--extensions` | `.cs,.ts,.py` | Comma-separated list of file extensions to index. |
| `--init` | `false` | Run a full initial scan before starting the file watcher. |

---

## Project Structure

```
marrow_worker/
├── main.py                  ← Entry point (CLI + event loop)
├── src/
│   ├── parser/              ← Language-specific skeleton extractors (tree-sitter)
│   ├── embedding/           ← LazyEncoder (fastembed wrapper)
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

MIT License. See [`LICENSE`](../marrow_server/LICENSE) for details.
