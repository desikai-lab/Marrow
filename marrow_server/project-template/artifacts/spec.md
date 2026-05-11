# {{FILL_IN: Your Project Name}} — Technical Specification

> ✏️ **Before your first agent session, replace every `{{FILL_IN}}` marker in this file.**
>
> **Option A — Fill manually:** open this file and search for `FILL_IN`.
> **Option B — Ask an agent:** paste this file to Claude with a description of your stack
> and ask it to replace every `{{FILL_IN}}` with the correct value.

## Core Architecture
- **Language(s)**: {{FILL_IN: e.g. Python 3.12 | Go 1.22 | C# 12 | TypeScript 5 | Ruby 3.3}}
- **Framework(s)**: {{FILL_IN: e.g. FastAPI | Gin | ASP.NET Core | Vue 3 + Vite | Rails}}
- **Database / Storage**: {{FILL_IN: e.g. PostgreSQL | SQLite | LanceDB | MongoDB | Redis}}
- **Transport / Protocol**: {{FILL_IN: e.g. REST | gRPC | MCP Streamable HTTP | WebSocket | n8n workflows}}
- **Architecture Pattern**: {{FILL_IN: e.g. Repository + Service Layer | MVC | Hexagonal | CQRS}}

## Services / Components
<!-- One row per deployable unit or major module. Add or remove rows as needed. -->
| Service / Component | Language | Role |
|---------------------|----------|------|
| {{FILL_IN: e.g. api-server}} | {{FILL_IN: e.g. Go}} | {{FILL_IN: e.g. REST API, handles auth and business logic}} |

## Repository Structure
```
{{FILL_IN: paste your directory tree here — run `tree -L 3` or describe the layout}}
```

## Coding Standards
- **Linter**: {{FILL_IN: e.g. ruff | golangci-lint | eslint | dotnet-format | rubocop}}
- **Formatter**: {{FILL_IN: e.g. black | gofmt | prettier | csharpier}}
- **Test Runner**: {{FILL_IN: e.g. pytest | go test | jest/vitest | xunit | rspec}}
- **Test Naming Convention**: `MethodName_InputDescription_ExpectedResult`

## Test Locations
```
{{FILL_IN: describe your test directory layout}}
# Standard Marrow convention (adapt as needed):
# tests/unit/{area}/         ← Unit tests
# tests/integration/{area}/  ← Integration tests
```

## How to Run Tests
```bash
{{FILL_IN: paste your test command here}}
# Examples:
#   PYTHONPATH=src python -m pytest tests/
#   go test ./...
#   npx vitest run
#   dotnet test
```

## Key Architectural Decisions
- No ADRs yet. Create `/docs/decisions/adr/0001-*.md` for your first significant decision.

## Security & Constraints
- {{FILL_IN: list hard constraints — forbidden libraries, required auth patterns, data residency rules, etc.}}

## External Integrations
- {{FILL_IN: list external services your code calls — e.g. Stripe API, n8n webhook, Kafka topic, S3 bucket, third-party OAuth provider}}
