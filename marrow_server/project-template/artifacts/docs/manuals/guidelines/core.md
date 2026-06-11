# Universal AI Agent Guidelines — CORE

## 0. System Interactions & MCP Protocols
- **Logical Root**: Your root `/` is the `artifacts/` folder. You cannot see or access anything above this directory.
- **Mandatory Structure**: You must strictly adhere to the following hierarchy for all project artifacts:
    - `/session.md`: Current session state (SSOT).
    - `/spec.md`: Project specifications.
    - `/docs/features/active/`: Only place for ongoing work. Each feature must have its own folder `[ID]-[name]/`.
    - `/docs/decisions/adr/`: Only place for architectural decisions.
- **Remote Source access**: The `/src/` directory is a **REMOTE** entity. It is NOT part of your local filesystem. Access it ONLY via specialized Code Tools (e.g., `view_file_source`, `get_file_skeleton`).
- **Playbook Discovery**: Role-addressable procedure playbooks live at `/docs/playbooks/` and are searchable via `get_applicable_playbooks`.


## 1. Repository Hygiene
- **Artifacts Only**: You only have write access to your virtual root. Save all plans and docs in `/docs/`.
- **Tests Location**: All tests live in `/tests/` in the repository root. This is a project-wide constraint — all roles must respect it.
- **No Scratchpads**: Do not leave temporary files in the root. Use `/tmp/` if needed, and clean up before handover.

## 2. Programming Patterns (The Standard)
- **SOLID & Clean Code**: Apply SRP and OCP. No monolithic procedural files.
- **Architecture**: Follow the **Repository Pattern** and **Service Layer** as defined in `spec.md`.
- **Surgical Precision**: When modifying `src/`, use `view_file_source` to target specific line ranges. Full file overwrites are forbidden unless creating a new file.

## 3. Session Handover & State
- **Cold Start Recovery**: At the start of every session, you MUST read `session.md` and the relevant feature bundle in `/docs/features/`.
- **Persistence**: Update the checklist in your feature bundle immediately after a user confirms a step.
- **Handover Note**: Write your handover for the "next version of yourself". Be explicit about decisions, line ranges modified, and the exact next action.

### 3.1 Strict Handoff Protocol (The Relayer)
- **Zero-State Prohibited**: Every update to `session.md` MUST include the `next_agent_role` field.
- **Phase-to-Role Mapping** (single source of truth):

| Phase | Role | Approval gate |
|---|---|---|
| TD / Hotfix | Execution Agent | No gate — fast path (see §4) |
| 1–3 | Discovery Agent | HARD STOP at Phase 3 |
| 4–6 | Architecture Agent | HARD STOP at Phase 6 |
| 7–11 | Planning Agent | HARD STOP at Phase 11 |
| 12–15 | Execution Agent | HARD STOP at Phase 15 |
| After Phase 15 | Discovery Agent | Cycle restarts |

- **Handover Trigger**: Your final message in any session MUST start with:
  `SESSION EXIT: Phase [X] completed. Next Agent: [Role]. Task: [Description].`
- **`next_agent_role` is the authoritative switching signal.** The SESSION EXIT message is a human-readable log. If they conflict, `next_agent_role` wins.

### 3.2 Agent Role Switching — Human Authority Rule
- **Human is sole authority** on role transitions. Never set `next_agent_role` to a different role without explicit human instruction.
- **Fast-path is not self-declaring.** Fast-path is active only when the human says so.
- **HARD STOP — two mandatory states:**
  - **(A) Awaiting approval:** `next_agent_role` = current role. Do not write SESSION EXIT.
  - **(B) After explicit GO:** `next_agent_role` = next role per §3.1 table. Then write SESSION EXIT.
  - *Example:* If the human says GO at Phase 3 (Discovery completed), the agent must set `next_agent_role: Architecture Agent` before writing SESSION EXIT.
- **Failure mode to avoid:** Writing SESSION EXIT with `next_agent_role` = current role after GO. The next cold-start agent will re-enter the wrong phase.
## 4. Fast-Path Protocol (TD / Hotfix)
Not all work follows the full 15-phase pipeline. Technical debt tasks and hotfixes skip Discovery and Planning entirely.

- **When to use**: Task type is `TD` or `hotfix`, or the human explicitly says "just fix this".
- **Entry point**: Execution Agent starts directly at Phase 12. No feature bundle required.
- **Minimum artefacts**: Update `session.md` with the task ID and a one-line description of the change. No requirements.md or architecture.md needed.
- **Exit**: Same as standard Execution — tests pass, PR opened, `next_agent_role: Discovery Agent`.
