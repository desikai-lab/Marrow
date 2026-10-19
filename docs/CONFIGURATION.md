← Back to [README](../README.md)

# Configuration Reference

## Contents
- [marrow_server](#marrow_server)
  - [Server environment variables](#server-environment-variables)
  - [Tool groups](#tool-groups)
- [marrow_worker](#marrow_worker)
  - [Worker CLI arguments](#worker-cli-arguments)
  - [Worker environment variables](#worker-environment-variables)
- [Docker Compose .env variables](#docker-compose-env)

## marrow_server

### Server environment variables

| Variable | Description | Default |
|---|---|---|
| `SECRET_TOKEN` | Bearer token for MCP and REST API authentication | Required |
| `TASKS_DIR` | Absolute path where project workspaces are stored | Required |
| `DEFAULT_PROJECT` | Name of the project auto-created on first run (Docker only) | `default` |
| `EMBEDDING_MODEL_CODE` | Sentence-transformer model for code skeleton embeddings | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_MODEL_TEXT` | Sentence-transformer model for text/artifact embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `EMBEDDING_MODEL_REVISION` | Pinned Hub commit for `EMBEDDING_MODEL_CODE` — server and worker must resolve the same revision, or stored and fresh vectors silently disagree | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| `EMBEDDING_DIMENSIONS` | Embedding vector dimensions — must match the chosen model | `384` |
| `MAX_EMBED_CHARS` | Maximum characters to embed per chunk | `2000` |
| `VECT_DEBOUNCE_SECONDS` | Debounce delay before vectorizing a changed file | `0.5` |
| `PORT` | HTTP server port | `8000` |
| `TOOL_GROUP_CODE_ENABLED` | `false` removes the code tools (`search_code_skeletons`, `get_file_skeleton`, `get_project_map`, `view_file_source`) from MCP, answers their REST routes with `409`, and rejects `marrow_worker` pushes to `/api/vectorize` with `409` — see [Tool groups](#tool-groups) | `true` |
| `TOOL_GROUP_TASK_ENABLED` | `false` removes the task tools (`add_tasks`, `search_tasks`, `get_task_details`, `update_task`, `complete_tasks`) from MCP and answers their REST routes with `409` | `true` |
| `TOOL_GROUP_BUILD_ENABLED` | `false` removes `run_project_build` from MCP (it has no REST route) | `true` |

### Tool groups

Set a variable to `false` to switch a group off. As with `REST_API_ENABLED`, only the value `true` (any case) keeps a group on: anything else, including an empty value, `1`, `yes` or a misspelled name, switches it off or has no effect, and nothing validates the names, so double-check the spelling. The artifact, history, session-context and project tools are core and cannot be switched off.

- Changes apply on restart. An MCP client that caches the tool list must reconnect before it stops offering a removed tool.
- A disabled tool is not registered on MCP. Its REST routes answer `409` with error type `ToolGroupDisabledError`; authentication still runs first.
- With the code group off, the descriptions of the artifact tools and the shipped guidelines still mention the code tools; an agent that follows them gets an unknown-tool error. This is a known limitation.
- With `TOOL_GROUP_CODE_ENABLED=false` the `marrow_worker` ingestion routes (`POST` and `DELETE /api/vectorize`) also answer `409`, so a deployed worker can no longer deliver chunks: its pushes are rejected until the group is re-enabled. Stop the worker to avoid failed retries.
- The flags only change what the server exposes: stored data, indexes and project init are untouched, so re-enabling a group finds everything intact.

## marrow_worker

### Worker CLI arguments

| Argument | Description | Default |
|---|---|---|
| `--repo-dir` | Absolute path to the source code to watch — must match `SOURCE_ROOT` in `.settings` | `os.getcwd()` |
| `--project-name` | Marrow project this worker indexes into | `DefaultProject` |
| `--target-url` | URL of the running marrow_server | `http://localhost:8000` |
| `--secret-token` | Must match `SECRET_TOKEN` on the server | — |
| `--init` | Run a full repo scan on startup | off |
| `--polling-interval` | File system polling interval in seconds — lower = faster response, higher CPU on large repos | `1.0` |

### Worker environment variables

| Variable | Description | Default |
|---|---|---|
| `MCP_SECRET_TOKEN` | Bearer token for `marrow_server` authentication (fallback for `--secret-token`) — must match `SECRET_TOKEN` on the server | — |
| `EMBEDDING_MODEL_CODE` | Sentence-transformer model for code skeleton embeddings | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_MODEL_REVISION` | Pinned Hub commit for the embedding model — must match the server | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| `HF_HUB_OFFLINE` | Set to `1` to block all HuggingFace network calls — the model must be pre-downloaded first | `0` |
| `WORKER_OUTBOX_PATH` | Path to the persistent SQLite delivery queue | `./worker_outbox.db` |
| `WORKER_FLUSH_INTERVAL_SECONDS` | Seconds between background outbox flush attempts | `60` |
| `WORKER_FLUSH_CONCURRENCY` | Concurrent outbox flush workers | `3` |
| `POLLING_INTERVAL` | File system polling interval in seconds (same as `--polling-interval`) | `1.0` |
| `LOG_LEVEL` | Worker log verbosity | `INFO` |

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
| `EMBEDDING_MODEL_REVISION` | Override the pinned model commit (rarely needed) — default is the built-in pin, identical in server and worker |
| `HF_HUB_OFFLINE` | Set to `1` after first run to block all HuggingFace network calls and use the local cache only — default `0` |
| `POLLING_INTERVAL` | File polling interval in seconds for the worker — increase for large repos to reduce CPU | `1.0` |
