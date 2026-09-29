# Changelog

All notable changes to Marrow are documented here.

## [1.1.5-rc1]

## 🚀 What's New in This Release

### 🧪 Hybrid Search & Retrieval (Experimental)
* **Keyword Signal Blending:** Introduced Stage 1 hybrid search combining BM25 keyword matching with Reciprocal Rank Fusion (RRF) alongside vector search for natural language artifact search.
  > **Note (Experimental):** Controlled via `LITERAL_EXTRACTION=on` (defaults to `off`). Currently optimized for English text; non-English artifacts may produce low-quality keyword tokens or fallback stubs.

### 🧩 Structured Chunking & Context Modes
* **Typed Chunking Strategies:** Introduced targeted chunking strategies to optimize embedding quality based on document type:
  * **Header Tree Chunker:** Generates `H1 → H2 → H3` breadcrumb trails for every leaf chunk in structured Markdown.
  * **Overlap Chunker:** Utilizes sliding-window chunking with configurable overlap for unstructured text.
* **Inline Content & Scope Filtering:** Added support for inline content snippets in search results alongside fine-grained scope filters for targeted directory/file querying.

### 🛡️ File System, Security & Maintenance
* **Security & Vulnerability Hygiene:** Applied Stage 1 security updates and dependency hygiene based on automated Snyk vulnerability scans.
* **Strict Case-Sensitive Path Resolution:** Standardized path resolution mechanics by removing legacy case-insensitive matching for consistent cross-platform behavior.
* **Vectorization Path Fixes:** Resolved edge-case path mapping bugs encountered during vectorization pipelines.

### 🐛 Critical Bug Fixes
* **Session Context Truncation:** Introduced a `full` retrieval mode for session context documents, resolving a bug where large context files were being forcibly truncated.

---

## [1.1.4]

## 🚀 What's New in This Release

### 🧹 Storage & Artifact Management
- Ghost Chunk Pruning: Implemented an automated cleanup mechanism to detect and prune orphaned artifact chunks, keeping the vector store synchronized with the underlying file state.
- Unified Path Resolver: Centralized and standardized path resolution logic across the codebase to ensure consistent file routing and prevent directory traversal issues.
### 📜 Session History Infrastructure
- History Migration Framework: Introduced a structured migration engine to handle smooth schema transitions and backward compatibility for legacy session history files.
### 🛠️ Task Engine Enhancements
- Task ID Visibility: Expanded response payload when batch-adding tasks to return both the set of newly generated created_task_ids and the next_available_id for downstream sequence tracking.

---

## [1.1.3]

## 🚀 What's New in This Release

### 📜 Session History & Handover Management
- Automated Session History: Added automatic append support for session history logs, backed by strict append-only file guards to prevent accidental history overrides.
- Handover Reliability: Fixed a silent drop bug during session handover extractions, ensuring complete context retention across session transitions.
### ⚡ Vector Indexing & Synchronization
- Vector Sync on File Operations: Integrated automatic vector chunk synchronization whenever underlying artifact files are moved or relocated.
- Persistent Embedding Cache: Added opt-in support for persisting model caches across container restarts using the FASTEMBED_CACHE_DIR environment variable, alongside updated embedding dependencies.
- CLI Reindexing Fix: Ensured proper asynchronous execution when reindexing chunk repositories through the CLI interface.
### 🛡️ Concurrency & Field Normalization
- Database Table Locking: Introduced a non-blocking asynchronous table lock context manager equipped with execution timeouts and warning diagnostics to prevent concurrency bottlenecks.
- Unified Write Modes: Standardized write mode declarations across configuration models and updated character boundary safeguards to prevent payload truncation.

---

## [1.1.2]

## 🚀 What's New in This Release

### 📚 Documentation & Protocol Hardening
- Skill & Playbook Protocol: Formalized and integrated the "Skill & Playbook Protocol" specification into the core architectural documentation.
- Onboarding Restructure: Comprehensively overhauled the main repository documentation, introducing dedicated, production-focused guides for system configuration, the build engine, and the administrative CLI interface.

### ⚙️ Maintenance & Type Checking
- Pylance Dependency Alignment: Patched localized development and environment maintenance dependencies to fix static analysis type-checking errors under Pylance.

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
