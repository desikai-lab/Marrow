← Back to [README](../README.md)

# Configuration Reference

## Contents
- [marrow_server environment variables](#marrow_server)
- [marrow_worker CLI arguments](#marrow_worker)
- [Docker Compose .env variables](#docker-compose-env)

## marrow_server

| Variable | Description | Default |
|---|---|---|
| `SECRET_TOKEN` | Bearer token for MCP and REST API authentication | Required |
| `TASKS_DIR` | Absolute path where project workspaces are stored | Required |
| `DEFAULT_PROJECT` | Name of the project auto-created on first run (Docker only) | `default` |
| `EMBEDDING_MODEL_CODE` | Sentence-transformer model for code skeleton embeddings | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_MODEL_TEXT` | Sentence-transformer model for text/artifact embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `EMBEDDING_DIMENSIONS` | Embedding vector dimensions — must match the chosen model | `384` |
| `MAX_EMBED_CHARS` | Maximum characters to embed per chunk | `2000` |
| `VECT_DEBOUNCE_SECONDS` | Debounce delay before vectorizing a changed file | `0.5` |
| `PORT` | HTTP server port | `8000` |

## marrow_worker

| Argument | Description | Default |
|---|---|---|
| `--repo-dir` | Absolute path to the source code to watch — must match `SOURCE_ROOT` in `.settings` | `os.getcwd()` |
| `--project-name` | Marrow project this worker indexes into | `DefaultProject` |
| `--target-url` | URL of the running marrow_server | `http://localhost:8000` |
| `--secret-token` | Must match `SECRET_TOKEN` on the server | — |
| `--init` | Run a full repo scan on startup | off |
| `--polling-interval` | File system polling interval in seconds — lower = faster response, higher CPU on large repos | `1.0` |

## Docker Compose .env

| Variable | Description |
|---|---|
| `SECRET_TOKEN` | Shared secret across all services |
| `SOURCE_PATHS` | Host path mounted as `/projects` in server and all workers |
| `DEFAULT_PROJECT` | First project name, auto-created on first run |
| `PROJECT_1_NAME` | Marrow project name for the first worker |
| `PROJECT_1_PATH` | Subfolder inside `SOURCE_PATHS` the first worker watches |
| `PROJECT_2_NAME` | Project name for a second worker (if used) |
| `PROJECT_2_PATH` | Subfolder for the second worker |
| `EMBEDDING_MODEL_CODE` | Override the code skeleton embedding model (passed to both server and worker) — default `BAAI/bge-small-en-v1.5` |
| `HF_HUB_OFFLINE` | Set to `1` after first run to block all HuggingFace network calls and use the local cache only — default `0` |
| `POLLING_INTERVAL` | File polling interval in seconds for the worker — increase for large repos to reduce CPU | `1.0` |
