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
A FastAPI + FastMCP application that exposes 21 structured MCP tools and a REST API for the worker. Storage uses **LanceDB** for vector embeddings and metadata, and **Markdown blobs** for task and artifact content. Transport is Streamable HTTP MCP (protocol version 2025-03-26).

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
| `get_session_context` | Reads session state and returns phase-appropriate guidelines |

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

### 1. Clone the repository

```bash
git clone https://github.com/desikai-lab/Marrow.git
cd marrow
```

### 2. Set up marrow_server

```bash
cd marrow_server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

Copy and configure the environment file:

```bash
cp .env.example .env
# Edit .env to set PROJECTS_ROOT and other required vars
```

Start the server:

```bash
python src/marrow_server.py
```

The MCP server will be available at `http://localhost:8000/mcp` by default.

### 2b. Initialize your first project

```bash
python src/cli/admin_cli.py project-init --project MyProject
```

This copies the built-in project template into your `TASKS_DIR/MyProject/` workspace. Open `MyProject/spec.md` and fill in your tech stack before your first agent session.

### 3. Set up marrow_worker

In a separate terminal:

```bash
cd marrow_worker
pip install -e .
cp .env.example .env
# Edit .env to point WATCH_PATHS to your source directories
python main.py
```

### 4. Connect your agent

Add Marrow to your MCP client configuration. Example for Claude Desktop:

```json
{
  "mcpServers": {
    "marrow": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

---

## Configuration

Both services are configured via environment variables (`.env` files).

### marrow_server

| Variable | Description | Default |
|---|---|---|
| `PROJECTS_ROOT` | Path where project artifact directories are stored | Required |
| `LANCEDB_PATH` | Path to the LanceDB data directory | `./data/lancedb` |
| `EMBEDDING_MODEL` | Sentence-transformer model name | `all-MiniLM-L6-v2` |
| `EMBEDDING_DIMENSIONS` | Embedding vector dimensions | `384` |
| `PORT` | HTTP server port | `8000` |

### marrow_worker

| Variable | Description | Default |
|---|---|---|
| `WATCH_PATHS` | Comma-separated list of directories to watch | Required |
| `SERVER_URL` | URL of the running marrow_server | `http://localhost:8000` |
| `DEBOUNCE_SECONDS` | File change debounce interval | `1.0` |
| `BATCH_SIZE` | Max skeleton chunks per delivery batch | `50` |

---

## Project Structure (Agent Workspace)

Each project managed by Marrow has a structured workspace in `PROJECTS_ROOT`:

```
{project_name}/
├── session.md              # Session state — current focus, pipeline phase
├── spec.md                 # Project specification and architectural constants
├── builds/                 # YAML build manifests
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
