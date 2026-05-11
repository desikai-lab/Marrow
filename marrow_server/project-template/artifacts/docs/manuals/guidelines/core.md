# Universal AI Agent Guidelines — CORE

## 0. System Interactions & MCP Protocols
- **Logical Root**: Your root `/` is the `artifacts/` folder. You cannot see or access anything above this directory.
- **Mandatory Structure**: You must strictly adhere to the following hierarchy for all project artifacts:
    - `/session.md`: Current session state (SSOT).
    - `/spec.md`: Project specifications.
    - `/docs/features/active/`: Only place for ongoing work. Each feature must have its own folder `[ID]-[name]/`.
    - `/docs/decisions/adr/`: Only place for architectural decisions.
- **Remote Source access**: The `/src/` directory is a **REMOTE** entity. It is NOT part of your local filesystem. Access it ONLY via specialized Code Tools (e.g., `view_file_source`, `get_file_skeleton`).

## 1. Repository Hygiene
- **Artifacts Only**: You only have write access to your virtual root. Save all plans and docs in `/docs/`.
- **Tests Location**: All tests must be created/modified in the `/tests/` directory (mirrored to the remote repository via MCP).
- **No Scratchpads**: Do not leave temporary files in the root. Use `/tmp/` if needed, and clean up before handover.

## 2. Programming Patterns (The Standard)
- **SOLID & Clean Code**: Apply SRP and OCP. No monolithic procedural files.
- **Architecture**: Follow the **Repository Pattern** and **Service Layer** as defined in `spec.md`.
- **Surgical Precision**: When modifying `src/`, use `view_file_source` to target specific line ranges. Full file overwrites are forbidden unless creating a new file.

## 3. Session Handover & State
- **Cold Start Recovery**: At the start of every session, you MUST read `session.md` and the relevant feature bundle in `/docs/features/`.
- **Persistence**: Update the checklist in your feature bundle immediately after a user confirms a step.
- **Handover Note**: Write your handover for the \"next version of yourself\". Be explicit about decisions, line ranges modified, and the exact next action.

## 3.1 Strict Handoff Protocol (The Relayer)
- **Zero-State Prohibited**: Every update to `session.md` MUST include the `next_agent_role` field.
- **Role Mapping**:
    - If Phase < 3 -> `next_agent_role: Discovery Agent`
    - If Phase 4-6 -> `next_agent_role: Architecture Agent`
    - If Phase 7-11 -> `next_agent_role: Planning Agent`
    - If Phase 12-15 -> `next_agent_role: Execution Agent`
    - If Execution Agent finishes -> `next_agent_role: Discovery Agent`
- **Handover Trigger**: Your final message in any session MUST start with:
  \"SESSION EXIT: Phase [X] completed. Next Agent: [Role]. Task: [Description].\"

## 4. Execution & Implementation (Execution Agent Specific)
- **Scalpel First**: You are the only agent with \"Write\" access to `src/` via MCP.
- **Verification Loop**: After writing code, you must verify it by running tests and checking the updated code skeleton to ensure the indexer picked up your changes.
- **Task Integrity**: Use `complete_tasks` only after the user has confirmed the implementation and tests have passed.
