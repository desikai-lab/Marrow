[![Marrow MCP server](https://glama.ai/mcp/servers/desikai-lab/Marrow/badges/score.svg)](https://glama.ai/mcp/servers/desikai-lab/Marrow)
# Marrow

> Give your AI coding agents memory that survives between sessions.

Marrow is an MCP server that fixes agent amnesia. It gives any MCP-compatible agent (Claude, Cursor, custom agents) a persistent workspace with:

- **Session state:** pick up exactly where the last session stopped
- **Task backlog:** with semantic search and automatic dependency unblocking
- **Versioned documents:** history and rollback for specs, plans and decisions
- **Semantic code search:** find code by meaning, not just by filename

Jump to: [Quickstart](#quickstart-5-minutes) · [Your first session](#your-first-session) · [Tool reference](#mcp-tool-reference) · [Troubleshooting](#troubleshooting) · [REST API](#rest-api-for-third-parties) · [Docs](#documentation)

## Why Marrow?

AI coding agents are stateless. Every new session starts cold: no memory of what was decided, what was built, or where things stand.

| Without Marrow | With Marrow |
|---|---|
| Agent forgets context between sessions | Session state is persisted and recoverable |
| Agent searches code by filename | Agent searches code by semantic meaning |
| Notes and plans live in chat history | Versioned artifact storage with history and rollback |
| Tasks tracked in external tools | Native task backlog with semantic search |
| Build context assembled by hand | Declarative build manifests assemble it automatically |

**Typical use: multi-agent handoff.** Use a strong model for architecture and let it save its decisions into Marrow. Then start a cheaper or local model to write the tests. The second agent calls `get_session_context` and is immediately aligned.

## How it works

```text
 Your source code ──► marrow_worker ──────────► marrow_server ◄──── Your AI agent
 (watched live)       parses files into          stores tasks, docs   (via MCP over
                      skeletons + embeddings     and the code index   HTTP)
```

| Component | What it does |
|---|---|
| `marrow_server` | The main service. Exposes the MCP tools and a REST API for the worker. Stores data in LanceDB (vectors and metadata) plus Markdown blobs (tasks and artifacts). |
| `marrow_worker` | Background daemon. Watches your source files, extracts classes, methods and namespaces with tree-sitter, embeds them, and sends them to the server in resilient batches. |
| `marrow_common` | Shared data contract (`SkeletonChunk`, `SCHEMA_VERSION`) between worker and server. |

<details>
<summary>Architecture details (for developers)</summary>

`marrow_server` is a FastAPI + FastMCP app (Streamable HTTP MCP, protocol `2025-03-26`). Storage is **LanceDB** for embeddings/metadata plus **Markdown blobs** for task and artifact content. The REST API is a sibling ASGI app behind a `PrefixDispatcher`, sharing the `operations/` layer with MCP (see ADR-0053, ADR-0054).

Full service architecture, layer map (`transport / services / storage / tools`), and worker pipeline → [`marrow_server/README.md`](marrow_server/README.md).

</details>

## Quickstart (5 minutes)

Pick one path:

| I want to… | Use |
|---|---|
| Run it locally with everything included | [Option A: Docker](#option-a--docker-recommended) |
| Try it without installing anything | [Option B: Glama](#option-b--glama-hosted-no-shell-access) |
| Develop or hack on Marrow itself | [Option C: Manual](#option-c--manual--development-setup) |

### Option A — Docker (recommended)

You need: [Docker](https://docs.docker.com/get-docker/) with Docker Compose.

**1. Get the compose file**

```bash
curl -O https://raw.githubusercontent.com/desikai-lab/Marrow/main/docker-compose.yml
```

Windows PowerShell alternative (plain `curl -O` behaves differently there):

```powershell
Invoke-WebRequest -OutFile docker-compose.yml https://raw.githubusercontent.com/desikai-lab/Marrow/main/docker-compose.yml
```

Or `git clone https://github.com/desikai-lab/Marrow.git && cd Marrow`.

**2. Create a `.env` file next to `docker-compose.yml`:**

```env
# Required: the token your agent must send as a Bearer token (use at least 16 characters)
SECRET_TOKEN=your-strong-random-secret

# Name of the first project, auto-created on first run
DEFAULT_PROJECT=MyProject

# Absolute host path of the folder that contains ALL your source repositories.
# It is mounted read-only at /projects in both server and worker, so edits on
# the host reach the worker live.
# Windows example: C:\Users\you\sources
# Linux/macOS example: /home/you/sources
SOURCE_PATHS=/home/you/sources

# Worker for the first project.
# PROJECT_1_PATH is relative to SOURCE_PATHS and becomes /projects/<PROJECT_1_PATH> in the containers.
PROJECT_1_NAME=MyProject
PROJECT_1_PATH=MyApp/src
```

**3. Start it**

```bash
docker compose up
```

Marrow pulls the pre-built images, creates your first project, then starts the server and worker. The first run takes about 20 seconds while the embedding model downloads. `marrow-init` also writes the project's `.settings` with `SOURCE_ROOT=/projects/<PROJECT_1_PATH>` automatically, so there is nothing to configure by hand.

Check that it worked:

```bash
docker compose ps
```

`marrow-server` should show `healthy` (the compose healthcheck calls `GET /health`).

**4. Connect your agent**

Add Marrow to your MCP client config (for Cursor, `~/.cursor/mcp.json`):

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

MCP endpoint: `http://localhost:8000/mcp`. Next: [Your first session](#your-first-session).

### Option B — Glama (hosted, no shell access)

Marrow runs as a hosted MCP server on the [Glama marketplace](https://glama.ai/mcp/servers/desikai-lab/Marrow). Glama manages the container, so you need no Docker or shell.

1. Install Marrow from the marketplace and set `SECRET_TOKEN` in the environment settings.
2. In the Glama inspector, call `init_project` once to create your first project:

```json
{ "tool": "init_project", "arguments": { "project": "default" } }
```

3. Connect your agent and call `get_session_context` to verify the workspace is ready.

Call `init_project` again with a new name for each additional project.

> Limitation: code intelligence tools (`search_code_skeletons`, `view_file_source`, …) need a running `marrow_worker` with access to your source code. On Glama they are unavailable unless you run a worker yourself and point it at the Glama server URL.

### Option C — Manual / development setup

<details>
<summary>Expand manual setup</summary>

You need: Python 3.12+. Dependencies (LanceDB, tree-sitter grammars, a sentence-transformer embedding model) are installed by `pip install -e .`. See ADR-0022 for grammar details.

**1. Clone**

```bash
git clone https://github.com/desikai-lab/Marrow.git
cd Marrow
```

**2. Start the server**

```bash
cd marrow_server
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env           # set SECRET_TOKEN and TASKS_DIR (both required)
python src/marrow_server.py
```

The server listens on `http://localhost:8000/mcp` by default.

**3. Create a project**

```bash
marrow-admin project-init --project MyProject
```

This copies the built-in template into `TASKS_DIR/projects/MyProject/`. Open its `spec.md` and fill in your tech stack before the first agent session. All admin commands are in [docs/ADMIN_CLI.md](docs/ADMIN_CLI.md).

**4. Point the project at your code**

```ini
# TASKS_DIR/projects/MyProject/.settings
SOURCE_ROOT=/absolute/path/to/your/source/code
```

**5. Start the worker (separate terminal)**

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

`--init` runs a full initial scan. Omit it on later runs.

**6. Connect your agent with the same JSON config shown in [Option A, step 5](#option-a--docker-recommended).**

</details>

## Your first session

Once your agent is connected:

1. **Verify the connection.** Ask the agent to call `get_session_context` for your project (for example `MyProject`). It returns the current phase, guidelines and next step.
2. **Fill in `spec.md`.** This is the project specification every future session reads first. Keep your stack and architectural rules there.
3. **Add work to the backlog.** Ask the agent to create tasks with `add_tasks`, then find them later with `search_tasks`.
4. **Try semantic code search.** Once the worker has finished its initial scan, ask something like “find where we validate user input”. The agent will use `search_code_skeletons`.
5. **Hand off.** At the end of a session the agent saves state to `session.md`. The next agent, on any model, starts from `get_session_context`.

## MCP tool reference

All tools work with any MCP-compatible client.

<details open>
<summary><strong>Tasks</strong> (5)</summary>

| Tool | Description |
|---|---|
| `add_tasks` | Add tasks to the project backlog |
| `search_tasks` | Semantic search over tasks |
| `get_task_details` | Full details of a task by ID |
| `update_task` | Update task fields (status, priority, …) |
| `complete_tasks` | Close tasks and automatically unblock dependents |

</details>

<details open>
<summary><strong>Artifacts</strong> (10)</summary>

| Tool | Description |
|---|---|
| `read_project_artifacts` | Read one or more Markdown artifacts |
| `save_project_artifacts` | Create or update artifacts (patch, replace, append) |
| `list_project_artifacts` | List files in artifact storage |
| `move_project_artifact` | Move or rename an artifact |
| `delete_project_artifact` | Safely delete an artifact |
| `search_project_artifacts` | Search across all artifacts |
| `semantic_search` | Semantic search over artifact chunks, optionally scoped to directories |
| `get_project_artifact_outline` | Table of contents of a Markdown file |
| `list_artifact_history` | Version history of an artifact |
| `restore_project_artifact` | Restore a previous version |

</details>

<details open>
<summary><strong>Code intelligence</strong> (4) — requires a running worker</summary>

| Tool | Description |
|---|---|
| `search_code_skeletons` | Semantic search over indexed code |
| `get_file_skeleton` | Token-efficient structural outline of a file |
| `view_file_source` | Read an exact line range from the live repository |
| `get_project_map` | Directory tree of all indexed files |

</details>

<details open>
<summary><strong>Session &amp; project</strong> (4)</summary>

| Tool | Description |
|---|---|
| `list_projects` | List all available projects |
| `init_project` | Create a project from the built-in template (ideal for Glama or any deployment without a shell) |
| `get_session_context` | Read session state and return guidelines for the active agent role. Call this first in every session. |
| `get_guideline` | Return the full context bundle (guidelines and ADRs) for a named role, for mid-session role switches that leave pipeline state untouched |

</details>

<details open>
<summary><strong>Build</strong> (1)</summary>

| Tool | Description |
|---|---|
| `run_project_build` | Run a YAML build manifest to assemble context payloads (see [docs/BUILD_ENGINE.md](docs/BUILD_ENGINE.md)) |

</details>

## Project settings (.settings)

Each project workspace has a `.settings` file that tells the server where your source code lives. Without it, code intelligence tools are disabled for that project.

Location: `TASKS_DIR/projects/{project_name}/.settings`

```ini
# Absolute path to the source root, as seen from inside the server container
SOURCE_ROOT=/projects/MyApp/src

# Optional. Experimental keyword blending for artifact search. Default: off
LITERAL_EXTRACTION=off

# Optional. REST API keys for third-party access (see [REST API](#rest-api-for-third-parties)).
# API_KEYS=label:key,label:key
```

> `LITERAL_EXTRACTION=on` blends keyword signals (BM25 + RRF) into natural-language artifact search. It is experimental and tuned for English text — non-English artifacts may produce low-quality keyword tokens or fallback stubs.

**The one rule: three paths must agree.** `SOURCE_ROOT` in `.settings`, the server's mount, and the worker's `--repo-dir` must all be the **same path**. Both containers mount the same volume at `/projects`, so a project's path is identical everywhere:

```text
Host machine                       Inside server AND worker containers
C:\Sources\   (SOURCE_PATHS)  ──►  /projects/           (bind-mounted read-only)
  ├── MyApp\src\                     ├── MyApp/src/
  └── OtherApp\src\                  └── OtherApp/src/

TASKS_DIR/projects/
  ├── MyApp/.settings        →  SOURCE_ROOT=/projects/MyApp/src
  └── OtherApp/.settings     →  SOURCE_ROOT=/projects/OtherApp/src

Worker for MyApp:    --repo-dir /projects/MyApp/src    --project-name MyApp
Worker for OtherApp: --repo-dir /projects/OtherApp/src --project-name OtherApp
```

In Docker, `/projects` is your `SOURCE_PATHS` folder bind-mounted read-only into both containers (see [Option A](#option-a--docker-recommended)); for a manual setup it is any local path both processes can see, e.g. `SOURCE_ROOT=/absolute/path/to/your/source/code` with the same value passed as the worker's `--repo-dir`. `marrow-init` writes this `.settings` for the first project automatically.

<details>
<summary>Multi-project setup</summary>

Give each project its own `.settings` and its own worker service in `docker-compose.yml` (a commented template block is included).

</details>

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Agent gets 401 / unauthorized (MCP) | The `Authorization: Bearer …` value in the client config differs from `SECRET_TOKEN` on the server. |
| REST returns 401 Unauthorized | Wrong/missing project key, key sent in query string (header only), unknown project in path, or you used `SECRET_TOKEN` on REST / project key on MCP — they are not interchangeable. Check `API_KEYS` in `.settings`. |
| Code tools (`search_code_skeletons`, `view_file_source`, …) are disabled or empty | Check that `.settings` exists with `SOURCE_ROOT`, that it matches the worker's `--repo-dir`, and that the worker is running. |
| Semantic code search returns nothing on a new project | The initial scan may still be running. Start the worker once with `--init`. |
| First start is slow | The embedding model is downloading (about 20 seconds). Wait for it to finish. |
| Code tools do not work on Glama | Expected. Run your own worker against the Glama server URL (see [Option B](#option-b--glama-hosted-no-shell-access)). |

Still stuck? [Open an issue](https://github.com/desikai-lab/Marrow/issues).

## REST API for third parties

21 of Marrow's 24 MCP operations are also available over authenticated REST for non-MCP clients (scripts, CI, third-party services). Same `operations/` layer as MCP — field names equal MCP tool parameter names (bound by CI parity test).

Base URL: `/api/v1/projects/{project}` — project always comes from the path. Not exposed: `list_projects`, `init_project`, `run_project_build`.

**1. Enable it (default is on)**

```env
# .env — server side
REST_API_ENABLED=true   # set to false to disable /api/v1 (requests fall through to MCP app)
```

**2. Create a project key**

Keys live in the project workspace `.settings` file (outside `artifacts/`), NOT in `.env`:

```ini
# TASKS_DIR/projects/MyProject/.settings
SOURCE_ROOT=/projects/MyApp/src
API_KEYS=ci:mk_YOUR_GENERATED_KEY_HERE
```

Generate a key (shape: `mk_` + 32–128 url-safe chars):

```bash
python -c 'import secrets; print("mk_" + secrets.token_urlsafe(32))'
```

Rules:

- Label shape: `[A-Za-z0-9][A-Za-z0-9_-]{0,31}`. Multiple keys per project: `API_KEYS=label1:key1,label2:key2`.
- Duplicate labels or duplicate key values are dropped with a warning.
- Rotate without restart: append new entry → move consumer → remove old entry. Takes effect on next request (60 s cache backstop).
- `chmod 600 .settings` — it now holds credentials.
- Every key has full access to its project (artifact writes included).
- `SECRET_TOKEN` does NOT work on REST; project keys do NOT work on MCP (`/mcp`) or `/api/vectorize`. Tokens in query string are ignored (401).

**3. Call it**

Header only — `Authorization: Bearer mk_…`:

```bash
curl -H 'Authorization: Bearer mk_...' http://localhost:8000/api/v1/projects/MyProject/session-context
```

Success: `{result, request_id}`. Error: `{error: {type, message}, request_id}` + `X-Request-Id` header. Machine-readable contract (key required): `GET /api/v1/projects/{project}/openapi.json` — no interactive docs UI.

<details>
<summary>Optional server knobs</summary>

```env
REST_CORS_ORIGINS=              # comma-separated origins; empty (default) = no CORS headers
REST_KEY_CACHE_MAX_AGE_S=60     # key cache TTL, clamped 1..300
REST_MAX_BODY_BYTES=5242880     # 5 MiB; over cap = 413
REST_MAX_CONCURRENCY=16         # saturated = 503 + Retry-After: 1
```

</details>

## Workspace layout

<details>
<summary>What a project workspace looks like on disk</summary>

Each project lives in `TASKS_DIR/projects/{project_name}/`:

```text
{project_name}/
├── .db               # Vector database and task blobs
├── .history          # File version history
├── .recycle_bin      # Deleted artifacts
├── .settings         # Per-project config, e.g. SOURCE_ROOT
└── artifacts/        # Root folder the agent can read and write
    ├── session.md    # Session state: current focus, pipeline phase
    ├── spec.md       # Project spec and architectural constants
    ├── builds/       # YAML build manifests
    └── docs/
        ├── decisions/adr/   # Architectural Decision Records
        ├── features/
        │   ├── active/      # Features in development
        │   └── archive/     # Completed work
        ├── manuals/         # Guidelines and operational docs
        └── templates/       # Standardization blueprints
```

</details>

## Documentation

| Doc | Covers |
|---|---|
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | All environment variables and CLI arguments for server, worker and docker-compose |
| [docs/ADMIN_CLI.md](docs/ADMIN_CLI.md) | `marrow-admin` and `marrow-skills` commands, and `repair_blobs.py` |
| [docs/BUILD_ENGINE.md](docs/BUILD_ENGINE.md) | Build manifest YAML format and the `build` admin command |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards and the pull request process.

## License

MIT. See [LICENSE](LICENSE).
