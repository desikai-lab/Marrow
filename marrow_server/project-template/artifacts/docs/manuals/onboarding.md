# Onboarding Guide — Getting Started with Marrow

Welcome. This guide is for **both humans and AI agents** starting work on a new project backed by Marrow.

---

## For Humans: Initial Setup

### 1. Fill in `spec.md`
This is the most important step. Open `spec.md` and fill in:
- Your tech stack (language, framework, database)
- Your repo directory structure
- Your linter and test commands
- Any hard constraints or architectural decisions

Agents read `spec.md` on every cold start. If it's empty or vague, agents will make poor decisions.

### 2. Start the Marrow server and worker
Follow the [Marrow quickstart](https://github.com/your-org/marrow#quickstart) to get the server and `marrow_worker` running and pointed at your source directory.

### 3. Connect your MCP client
Add Marrow to your Claude Desktop, Cursor, or other MCP client config:
```json
{
  \"mcpServers\": {
    \"marrow\": {
      \"url\": \"http://localhost:8000/mcp\"
    }
  }
}
```

### 4. Initialize your first task
Tell the agent what you want to build. It will create a task, set up a feature bundle in `docs/features/active/`, and begin the Discovery phase.

---

## For AI Agents: Cold Start Protocol

1. **Read `session.md`** — find the current phase, active task, and next agent role.
2. **Read `spec.md`** — understand the tech stack and constraints before touching anything.
3. **Read the active feature bundle** in `docs/features/active/` if one exists.
4. **Check your role** — `get_session_context` assembles all of the above automatically.
5. **Begin work** according to your phase guidelines (`docs/manuals/guidelines/`).

---

## Project Structure Reference

```
your-project/          (Marrow artifact workspace)
├── session.md         ← ALWAYS read first
├── spec.md            ← ALWAYS read second
└── docs/
    ├── features/
    │   ├── active/    ← current work
    │   └── archive/   ← completed history
    ├── decisions/
    │   ├── 0000-index.md
    │   └── adr/
    ├── templates/     ← feature, ADR, bug report templates
    └── manuals/
        └── guidelines/  ← agent behaviour rules
```
