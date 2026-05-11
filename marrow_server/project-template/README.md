# Marrow Project Template

This is a ready-to-use workspace template for projects backed by [Marrow](https://github.com/your-org/marrow) — the persistent MCP intelligence backend for AI coding agents.

## How to Use

### 1. Copy this template into Marrow

When starting a new project, point your `marrow_worker` at your source code and initialize a new project workspace in Marrow using this template as the starting structure.

Or, if you are using Marrow's CLI:
```bash
marrow init --project MyProject --template ./project-template
```

### 2. Fill in `spec.md`

This is the most important step. Open `spec.md` and describe your:
- Tech stack and framework
- Repository structure
- Coding standards and test commands
- Key architectural constraints

Every agent reads `spec.md` on cold start. A well-filled spec means better agent decisions.

### 3. Connect your MCP client and start working

See [Marrow's quickstart](https://github.com/your-org/marrow#quickstart) for how to connect Claude Desktop, Cursor, or any MCP-compatible client.

---

## Template Structure

```
project-template/
├── session.md                        ← Live session state (agent reads this first)
├── spec.md                           ← Your project’s technical specification
└── docs/
    ├── decisions/
    │   ├── 0000-index.md               ← ADR index
    │   └── adr/                        ← Architectural Decision Records
    ├── features/
    │   ├── active/                     ← Features currently in development
    │   └── archive/                    ← Completed work history
    ├── templates/
    │   ├── feature_template.md         ← Multi-agent feature bundle template
    │   ├── adr_template.md             ← ADR template
    │   └── bug_report_template.md      ← Bug report template
    └── manuals/
        ├── onboarding.md               ← Getting started guide
        └── guidelines/
            ├── core.md                 ← Universal agent rules
            ├── discovery.md            ← Discovery & Architecture agent rules
            ├── planning.md             ← Planning agent rules
            └── execution.md            ← Execution agent rules
```

---

## The Agent Pipeline

Marrow structures AI agent work into four roles, each with strict phase boundaries:

| Role | Phases | Responsibility |
|---|---|---|
| **Discovery Agent** | 1–6 | Understand the codebase, define requirements, draft architecture |
| **Planning Agent** | 7–11 | Break architecture into atomic executable steps |
| **Execution Agent** | 12–15 | Implement, test, and verify — no creative decisions |
| **Discovery Agent** | 1 (next cycle) | Review completed work, pick next task |

Each phase transition requires explicit human approval. See `docs/manuals/guidelines/` for the full ruleset.
