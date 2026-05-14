# Marrow MCP — Tool Context

## Purpose

**Marrow** is a self-hosted Model Context Protocol (MCP) server ecosystem for AI-driven development workflows. It gives agents a persistent, semantically searchable memory layer covering both project knowledge (tasks, documents, decisions) and live source code structure (class/method skeletons).

This document is intended to be read by an AI agent at the start of a session to understand the available tools and how to use them effectively.

---

## Architecture

```
AI Agent (Claude / Cursor / Antigravity)
    │
    │  MCP (Streamable HTTP or stdio)
    ▼
marrow_server  ──  FastAPI + FastMCP
    │
    ├── LanceDB (.db/)              ← Vector index (tasks, artifacts, skeletons)
    └── Artifact Vault (projects/)  ← Markdown/YAML blobs (tasks, docs, ADRs)
    │
    │  POST /api/vectorize
    ▼
marrow_worker                       ← File watcher + skeleton extractor
```

---

## Storage Model

### Tasks (YAML Blobs + LanceDB Index)

Tasks are stored as YAML lists within project artifact files. Each task has a fixed base schema but supports unlimited extra fields thanks to `Pydantic extra='allow'`.

```yaml
- id: F48
  type: F                        # F=Feature, B=Bug, T=Task, E=Epic
  title: Add support for examples
  problem: |
    Agent needs to attach code examples to tasks.
  solution: |
    Add support for arbitrary YAML fields.
  priority: 1 — high
  status: open
  updated: 2026-03-19T00:15
  where: [tools.py, models.py]
  example: |                     # ← Custom extra field (no schema change needed)
    print("This is an example!")
```

### Artifacts (Markdown Blobs)

Artifacts are plain Markdown files stored under `projects/{project}/artifacts/`. They are versioned, searchable via semantic embeddings, and can be read/written by agents via MCP tools.

---

## MCP Tool Reference

### 📋 Task Tools

| Tool | Description |
|---|---|
| `search_tasks` | Search tasks by status, priority, or type using LanceDB. |
| `get_task_details` | Retrieve full task content (YAML blob) by ID. |
| `add_tasks` | Append new tasks to a project backlog. |
| `update_task` | Atomically update task fields with 2PC rollback. |
| `complete_tasks` | Mark one or more tasks as done and auto-unblock dependents. |

### 📄 Artifact Tools

| Tool | Description |
|---|---|
| `read_project_artifacts` | Read one or more artifact files (Markdown). |
| `save_project_artifacts` | Create or update artifact files. |
| `search_project_artifacts` | Full-text search across all artifacts. |
| `semantic_search` | Semantic search over artifact sections via vector embeddings. |
| `get_project_artifact_outline` | Extract table of contents from a Markdown artifact. |
| `list_project_artifacts` | List files in the artifact storage for a project. |
| `move_project_artifact` | Move or rename an artifact. |
| `delete_project_artifact` | Safely delete an artifact. |
| `list_artifact_history` | View version history of an artifact. |
| `restore_project_artifact` | Restore an artifact to a previous version. |

### 🔍 Code Skeleton Tools

| Tool | Description |
|---|---|
| `search_code_skeletons` | Semantic search over indexed source code skeletons (class/method signatures). |
| `get_file_skeleton` | Get the outline (depth-configurable) of a specific source file. |
| `get_project_map` | Get the full directory tree of indexed files. |
| `view_file_source` | Read a precise line range from the live source repository (The Scalpel). |

### ⚙️ Session & Build Tools

| Tool | Description |
|---|---|
| `get_session_context` | Reads `session.md`, detects the active pipeline phase, and returns role-specific guidelines. |
| `run_project_build` | Executes a build pipeline defined in a build manifest artifact. |
| `list_projects` | Returns all available projects. |

---

## Agent Operational Rules

1. **Storage is the Source of Truth** — Always retrieve task state via `get_task_details` before updating. Never rely on in-context memory alone.
2. **Surgical Code Access** — For code edits, always use `view_file_source` to read the exact lines before patching. Never guess line numbers.
3. **Artifact Hierarchy** — Artifacts follow a strict layout:
   - `/session.md` — Current session state (SSOT)
   - `/spec.md` — Project specification
   - `/docs/features/active/` — Active feature bundles
   - `/docs/decisions/adr/` — Architectural Decision Records
4. **Task Lifecycle** — Use `complete_tasks` only after the user has confirmed implementation and tests have passed.
5. **Task Status Values**:
   - `open` — Ready for work
   - `blocked` — Waiting on another task
   - `in_progress` — Actively being worked on
   - `evaluation` — Requires review or discussion
   - `closed` — Done

---

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `TASKS_DIR` | Root path for the Marrow data vault (projects + LanceDB). |
| `SECRET_TOKEN` | Bearer token required for all API requests. |

| `EMBEDDING_MODEL_TEXT` | Sentence-transformer model for artifact embeddings. |
| `EMBEDDING_MODEL_CODE` | Model for code skeleton embeddings. |
| `EMBEDDING_DIMENSIONS` | Vector dimension size (must match the model). |
| `MAINTENANCE_INTERVAL_SECONDS` | How often background maintenance runs (default: 1800). |
| `MCP_DEBUG_TRANSPORT` | `true` to enable verbose transport logging. |
