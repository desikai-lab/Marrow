[![Marrow MCP server](https://glama.ai/mcp/servers/desikai-lab/Marrow/badges/score.svg)](https://glama.ai/mcp/servers/desikai-lab/Marrow)
# Marrow

> **A persistent, multi-project intelligence backend for AI coding agents.**

Marrow gives AI agents structured, long-lived memory over your codebase and projects — served over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). It exposes a unified API surface covering task management, versioned document storage, semantic code navigation, session state, and a build pipeline.

At its core, a background daemon watches your source files in real time, extracts structural skeletons using language-aware grammars, generates vector embeddings, and keeps a semantic index always in sync. The result: agents can navigate your code by *meaning*, not just by filename.

---

## Why Marrow?

AI coding agents are stateless by nature. Every new session starts cold — no memory of what was decided, what was built, or where things stand. Marrow solves this by acting as a persistent, structured workspace that any agent can plug into via MCP and immediately orient itself.

| Without Marrow | With Marrow |
|---|---|
| Agent forgets context between sessions | Full session state persisted and recoverable |
| Agent searches code by filename | Agent searches code by semantic meaning |
| Notes and plans live in chat history | Versioned artifact storage with history and rollback |
| Tasks tracked in external tools | Native task backlog with semantic search |
| Build context assembled manually | Declarative build manifests assemble context automatically |

---

## Use Case: Multi-Agent Handoff
Marrow acts as the single source of truth for heterogeneous agent workflows. 
You can use Claude for heavy architectural lifting, let it save state into Marrow, and then spin up a cheaper local model to write unit tests. The second agent immediately aligns itself using `get_session_context` and semantic task backlogs.

---

## Architecture

Marrow is composed of three packages:

```
marrow_server/     — MCP + REST API server (the main service)
marrow_worker/     — Background file watcher and skeleton indexer
marrow_common/     — Shared schema (skeleton_schema.py)
```

### marrow_server
A FastAPI + FastMCP application that exposes 23 structured MCP tools and a REST API for the worker. Storage uses **LanceDB** for vector embeddings and metadata, and **Markdown blobs** for task and artifact content. Transport is Streamable HTTP MCP (protocol version 2025-03-26).

### marrow_worker
A standalone background daemon that:
1. Watches source files using filesystem events
2. Debounces rapid changes
3. Parses modified files with **tree-sitter** grammars (multi-language)
4. Extracts structural skeletons: classes, methods, namespaces, properties
5. Generates vector embeddings via a lazy-loaded encoder
6. Delivers skeleton chunks to `marrow_server` via a resilient batched outbox with retry logic

### marrow_common
Shared Pydantic schema (`SkeletonChunk`, `SCHEMA_VERSION`) used as the data contract between worker and server.

---

## MCP Tool Reference

All tools are available to any MCP-compatible client (Claude, Cursor, custom agents, etc.).

### 🗒️ Task Tools
| Tool | Description |
|---|---|
| `add_tasks` | Adds a list of tasks to the project backlog |
| `search_tasks` | Semantic search over tasks |
| `get_task_details` | Returns full task details by ID |
| `update_task` | Updates task fields (status, priority, etc.) |
| `complete_tasks` | Atomically closes tasks and auto-unblocks dependents |

### 📄 Artifact Tools
| Tool | Description |
|---|---|
| `read_project_artifacts` | Reads one or more markdown artifacts |
| `save_project_artifacts` | Creates or updates artifacts (patch, replace, append) |
| `list_project_artifacts` | Lists files in artifact storage |
| `move_project_artifact` | Moves or renames an artifact |
| `delete_project_artifact` | Safely deletes an artifact |
| `search_project_artifacts` | Global semantic search across all artifacts |
| `get_project_artifact_outline` | Extracts table of contents from a markdown file |
| `list_artifact_history` | Lists version history for an artifact |
| `restore_project_artifact` | Restores a previous artifact version |

### 🧠 Code Intelligence Tools
| Tool | Description |
|---|---|
| `search_code_skeletons` | Semantic search over indexed source code skeletons |
| `get_file_skeleton` | Retrieves a token-optimized structural outline of a file |
| `view_file_source` | Reads a precise line range from the live source repository |
| `get_project_map` | Returns a live directory tree of all indexed files |

### 📁 Session & Project Tools
| Tool | Description |
|---|---|
| `list_projects` | Returns a list of all available projects |
| `init_project` | Creates a new project workspace from the built-in template — use on Glama or any deployment without shell access |
| `get_session_context` | Reads session state and returns phase-appropriate guidelines for the active agent role |
| `get_guideline` | Assembles and returns the full context bundle (guidelines + ADRs) for any named agent role — use for mid-session role switches without disturbing pipeline state |

### 🛠️ Build Tools
| Tool | Description |
|---|---|
| `run_project_build` | Executes a YAML build manifest to assemble context payloads |

---

## Requirements

- Python 3.12+
- [LanceDB](https://lancedb.github.io/lancedb/) (installed via pip)
- [tree-sitter](https://tree-sitter.github.io/) with language wheels (see ADR-0022)
- A sentence-transformer compatible embedding model

---

## Quickstart

### Option A — Docker (recommended)

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and Docker Compose

**1. Get the compose file**

Download `docker-compose.yml` from the repository (no full clone needed):

```bash
curl -O https://raw.githubusercontent.com/desikai-lab/Marrow/main/docker-compose.yml
```

Or clone if you prefer:

```bash
git clone https://github.com/desikai-lab/Marrow.git
cd Marrow
```

**2. Configure**

Create a `.env` file in the same directory as `docker-compose.yml`:

```env
SECRET_TOKEN=your-strong-random-secret

# Name of the first project auto-created on first run
DEFAULT_PROJECT=MyProject

# Absolute path to the folder on your host that contains all your source repositories.
# This entire folder is mounted read-only at /projects inside both server and worker.
SOURCE_PATHS=C:\Users\you\sources       # Windows
# SOURCE_PATHS=/home/you/sources        # Linux / macOS

# Source path and project name for the first worker.
# PROJECT_1_PATH is relative to SOURCE_PATHS — it becomes /projects/PROJECT_1_PATH inside the container.
# It must exactly match SOURCE_ROOT in that project's .settings file.
PROJECT_1_NAME=MyProject
PROJECT_1_PATH=MyApp/src
```

**3. Configure source wiring for each project**

After first start, create a `.settings` file inside each project workspace:

```
TASKS_DIR/projects/MyProject/.settings
```

```ini
# Path as seen from inside the server container — must match PROJECT_1_PATH above.
SOURCE_ROOT=/projects/MyApp/src
```

See [Project Settings (.settings)](#project-settings-settings) for the full explanation.

**4. Start**

```bash
docker compose up
```

Marrow pulls the pre-built images, initializes your first project automatically, then starts the server and worker. Allow ~20 seconds on first run for the embedding model to download.

MCP endpoint: `http://localhost:8000/mcp`

**5. Connect your agent**

Add Marrow to your MCP client configuration:

```json
{
  "mcpServers": {
    "marrow": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-strong-random-secret"
      }
    }
  }
}
```

For Cursor: add the same block under `mcp` in your `~/.cursor/mcp.json`.

---

### Option B — Glama (hosted, no shell access)

Marrow is available as a hosted MCP server on the [Glama marketplace](https://glama.ai/mcp/servers/desikai-lab/Marrow). Glama manages the container — no Docker or shell access required.

**1.** Install the Marrow server from the Glama marketplace and set `SECRET_TOKEN` in the environment settings.

**2.** Open the Glama inspector and call `init_project` once to create your first project:

```json
{ "tool": "init_project", "arguments": { "project": "default" } }
```

**3.** Connect your agent and call `get_session_context` to verify the workspace is ready.

For additional projects, call `init_project` again with a new name.

> **Note:** Code intelligence tools (`search_code_skeletons`, `view_file_source`, etc.)
> require a running `marrow-worker` with access to your source code. These tools are
> unavailable on Glama unless you run a worker separately pointed at the Glama server URL.

---

### Option C — Manual / Development Setup

<details>
<summary>Expand for manual setup instructions</summary>

#### 1. Clone the repository

```bash
git clone https://github.com/desikai-lab/Marrow.git
cd Marrow
```

#### 2. Set up marrow_server

```bash
cd marrow_server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

Copy and configure the environment file:

```bash
cp .env.example .env
# Edit .env — set SECRET_TOKEN and TASKS_DIR (required)
```

Start the server:

```bash
python src/marrow_server.py
```

The MCP server will be available at `http://localhost:8000/mcp` by default.

#### 2b. Initialize your first project

```bash
marrow-admin project-init --project MyProject
```

This copies the built-in project template into your `TASKS_DIR/projects/MyProject/` workspace. Open `spec.md` and fill in your tech stack before your first agent session.

#### 2c. Configure source wiring

Create a `.settings` file in the project workspace:

```ini
# TASKS_DIR/projects/MyProject/.settings
SOURCE_ROOT=/absolute/path/to/your/source/code
```

#### 3. Set up marrow_worker

In a separate terminal, start the worker pointing at your source code:

```bash
cd marrow_worker
pip install -e .

python main.py \
  --repo-dir /absolute/path/to/your/source/code \
  --project-name MyProject \
  --target-url http://localhost:8000 \
  --secret-token your-strong-random-secret \
  --init
```

`--init` triggers a full scan on startup; omit it on subsequent runs.

#### 4. Connect your agent

```json
{
  "mcpServers": {
    "marrow": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-strong-random-secret"
      }
    }
  }
}
```

</details>

---

## Project Settings (.settings)

Each Marrow project workspace contains a `.settings` file that tells the server where the
corresponding source code lives on disk. Without it, the code intelligence tools
(`search_code_skeletons`, `get_file_skeleton`, `view_file_source`, `get_project_map`) are
disabled for that project.

**Location:** `TASKS_DIR/projects/{project_name}/.settings`

**Format:**
```ini
# Absolute path to the source code root as seen from inside the server container.
SOURCE_ROOT=/projects/MyApp/src
```

**The key constraint — server, worker, and .settings must all agree on the same path.**

Marrow uses a single shared volume (`SOURCE_PATHS` on the host, mounted as `/projects`
in both containers) to give the server and every worker access to all source repositories.
Each project's `.settings` then points `SOURCE_ROOT` at its own subfolder, and the
corresponding worker watches that exact same path:

```
Host machine:
  C:\Sources\                    ← SOURCE_PATHS in .env
    ├── MyApp\src\
    └── OtherApp\src\

Inside both server and worker containers:
  /projects/                     ← same volume, same paths
    ├── MyApp/src/
    └── OtherApp/src/

TASKS_DIR/projects/
  ├── MyApp/
  │   └── .settings  →  SOURCE_ROOT=/projects/MyApp/src
  └── OtherApp/
      └── .settings  →  SOURCE_ROOT=/projects/OtherApp/src

Worker for MyApp:    --repo-dir /projects/MyApp/src    --project-name MyApp
Worker for OtherApp: --repo-dir /projects/OtherApp/src --project-name OtherApp
```

**Multiple projects** each get their own `.settings` file and their own worker service in
`docker-compose.yml` (a commented template block is included in the compose file).

---

## Configuration

Both services are configured via environment variables (`.env` files).

### marrow_server

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

### marrow_worker (CLI arguments)

| Argument | Description | Default |
|---|---|---|
| `--repo-dir` | Absolute path to the source code to watch — must match `SOURCE_ROOT` in `.settings` | `os.getcwd()` |
| `--project-name` | Marrow project this worker indexes into | `DefaultProject` |
| `--target-url` | URL of the running marrow_server | `http://localhost:8000` |
| `--secret-token` | Must match `SECRET_TOKEN` on the server | — |
| `--init` | Run a full repo scan on startup | off |
| `--polling-interval` | File system polling interval in seconds — lower = faster response, higher CPU on large repos | `1.0` |

### .env (Docker Compose)

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

---

## Project Structure (Agent Workspace)

Each project managed by Marrow has a structured workspace in `TASKS_DIR/projects/`:

```
{project_name}/
├── .db                     # Vectore db and tasks Blob
├── .history                # Folder with the files history
├── .recycle_bin
├── .settings               # Additional Project Configuration like SOURCE_ROOT - to define path to the Code Base
└── artifacts               # Root folder of the project that the agent has access to        
    ├──session.md           # Session state — current focus, pipeline phase
    ├──spec.md              # Project specification and architectural constants
    ├──builds/              # YAML build manifests
    └── docs/
        ├── decisions/adr/        # Architectural Decision Records
        ├── features/
        │   ├── active/           # Features currently in development
        │   └── archive/          # Completed work history
        ├── manuals/              # Operational guidelines and docs
        └── templates/            # Standardization blueprints
```

---

## Build Engine

Marrow includes a declarative build system for assembling complex context payloads from multiple artifact sources. Define a YAML manifest and run it via MCP:

```yaml
# builds/my_context.yaml
name: feature_context
version: "1.0.0"
output:
  format: single_file
  filename: "context_{{DATE}}.md"
steps:
  - action: include_artifact
    path: session.md
    mode: full
  - action: include_artifact
    path: docs/decisions/adr/0034-product-name-marrow.md
    mode: section
    section_name: "Decision"
```

Run via MCP tool `run_project_build`, or locally:

```bash
python run_build.py --project MyProject --build my_context
```

---

## Roadmap

### ✅ v1.0.0 — The Foundation
Core MCP server, LanceDB storage, artifact management, task backlog, code skeleton indexing, build engine, session continuity.

### 🟡 v1.1.0 — The Sandbox & Sync *(Active)*
Workflow hardening, dynamic reindexing, phase-aware agent guidelines, handoff optimization.

### 🔴 v2.0.0 — The AI Orchestrator *(Planned)*
Declarative handoff, context sanitization, branch-aware indexing, diff intelligence, multi-agent orchestration.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the pull request process.

---

## License

MIT — see [LICENSE](LICENSE).
