# Contributing to Marrow

Thank you for your interest in contributing! This document covers everything you need to get started.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Report a Bug](#how-to-report-a-bug)
- [How to Request a Feature](#how-to-request-a-feature)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)

---

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold a welcoming and respectful environment for everyone.

---

## How to Report a Bug

Use the [Bug Report issue template](.github/ISSUE_TEMPLATE/bug_report.md). Please include:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behaviour
- Your environment (OS, Python version, relevant config)
- Relevant log output

---

## How to Request a Feature

Use the [Feature Request issue template](.github/ISSUE_TEMPLATE/feature_request.md). Please describe:

- The problem you are trying to solve
- Your proposed solution or idea
- Any alternatives you have considered

---

## Development Setup

### Prerequisites

- Python 3.12+
- `git`
- A virtual environment tool (`venv` or `uv`)

### Clone and install

```bash
git clone https://github.com/your-org/marrow.git
cd marrow

# Install marrow_common first (shared dependency)
cd marrow_common && pip install -e . && cd ..

# Install marrow_server
cd marrow_server && pip install -e ".[dev]" && cd ..

# Install marrow_worker
cd marrow_worker && pip install -e ".[dev]" && cd ..
```

### Running tests

```bash
# Unit tests
cd marrow_server
$env:PYTHONPATH="src"  # Windows
export PYTHONPATH=src  # Linux/macOS
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/
```

### Linting

This project uses `ruff`. It is mandatory — CI will reject code that does not pass.

```bash
ruff check .
ruff format .
```

---

## Coding Standards

- **Language**: Python 3.12+
- **Linter**: `ruff` (mandatory, see above)
- **Tests**: `pytest` — required for all logic changes
- **Test naming**: `MethodName_InputDescription_ExpectedResult`
  - Example: `search_tasks_valid_query_returns_results`
- **Architecture**: Repository Pattern + Service Layer (see `spec.md` in any project workspace)
- **SOLID principles**: Apply SRP and OCP. No monolithic procedural files.
- **Logic isolation**: Domain logic must be transport-agnostic.

### Test locations

```
tests/unit/{area}/        # Unit tests
tests/integration/{area}/ # Integration tests
```

---

## Pull Request Process

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Make your changes** following the coding standards above.
3. **Add or update tests** — PRs without tests for logic changes will not be merged.
4. **Run the full test suite and linter** locally before pushing.
5. **Open a Pull Request** against `main` with a clear description of what and why.
6. **Address review feedback** — maintainers will review within a reasonable timeframe.

### Commit message style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add semantic search to task query service
fix: correct debounce interval in worker watcher
docs: update quickstart in README
refactor: extract TemplateRenderer from build processor
test: add unit tests for artifact chunker
```

---

## Project Structure

See [README.md](README.md#architecture) for the full architecture overview.

Key directories for contributors:

```
marrow_server/src/
  tools/          # MCP tool definitions (thin wrappers)
  services/       # Business logic (command + query services)
  storage/
    repositories/ # Data access layer (LanceDB)
  transport/      # HTTP + MCP transport layer
  utils/          # Shared utilities

marrow_worker/src/
  parser/         # tree-sitter parsing and skeleton extraction
  embedding/      # Lazy-loaded embedding model
  watcher/        # Filesystem event watcher + debouncer
  transport/      # Outbox and API client for marrow_server
```
