# Changelog

All notable changes to Marrow are documented here.

This project adheres to [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Changed
- Project renamed from `BacklogMCP` to **Marrow** (ADR-0034)
- Directory structure: `TaskServiceMCP/` → `marrow_server/`, `SkeletonizerWorker/` → `marrow_worker/`, `common/` → `marrow_common/`
- MCP server identity updated: `FastMCP("marrow")`
- All logger namespaces updated to `marrow.*`
- Repository prepared for public open-source release

---

## [1.1.0] — 2026-05

### Focus: Workflow Hardening & Human-AI Synchronisation

### Added
- **Phase-aware session context**: `get_session_context` now injects role-specific guidelines based on the active pipeline phase
- **Maintenance scheduler**: Server-side background maintenance with configurable scheduling (ADR-0033)
- **Schema version enforcement**: Strict schema versioning between worker and server with rejection of mismatched payloads (ADR-0023)
- **TemplateRenderer utility**: Extracted as a standalone service for build engine template processing
- **Structured logging**: Consistent `marrow.*` logger namespace across all modules
- **Durable delete outbox**: Worker outbox now handles deletions durably with retry logic
- **Debug logging middleware**: Configurable request/response debug logging at transport layer

### Changed
- Worker outbox batch flush now uses semaphore-controlled concurrency (ADR-0030)
- Performance: singleton LanceDB table handles — eliminated repeated `open_table()` calls
- Performance: batched flush with `flush_pending_batched()` for worker outbox

### Fixed
- `os.path.relpath` cross-drive failure on Windows (B4000124)
- Server memory leak from unclosed async resources after requests
- HuggingFace offline mode handling for embedding model cold start

---

## [1.0.0] — 2026-04

### Focus: Solo-Execution & Context Continuity

### Added
- **MCP server** (`TaskServiceMCP`) with 21 structured tools over Streamable HTTP (ADR-0019)
- **Task backlog**: LanceDB-backed task management with semantic search
- **Artifact storage**: Versioned markdown blob storage with patch, replace, append, and section operations
- **Code skeleton indexer** (`SkeletonizerWorker`): real-time file watching, tree-sitter parsing, embedding generation, batched delivery
- **Semantic code search**: `search_code_skeletons`, `get_file_skeleton`, `get_project_map`, `view_file_source`
- **Build engine**: Declarative YAML manifest system for assembling context payloads (ADR-0015)
- **Session context tool**: `get_session_context` for agent cold-start recovery
- **Ghost file detection**: Automatic cleanup of stale skeleton index entries from deleted files
- **Repository pattern**: Full data access layer refactor (ADR-0018)
- **Service layer**: Command/query service separation across all domains
- **CLI**: Admin CLI with migrate, health, reindex, build, and maintenance commands (ADR-0021)
- **Multi-language parsing**: tree-sitter grammars for Python, TypeScript, JavaScript, and more (ADR-0022)
- **Multi-model embeddings**: Configurable embedding model with dimension validation (ADR-0025)
- **OAuth router**: Optional OAuth 2.0 transport layer
- **Metrics**: Basic request metrics middleware

---

[Unreleased]: https://github.com/your-org/marrow/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/your-org/marrow/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/your-org/marrow/releases/tag/v1.0.0
