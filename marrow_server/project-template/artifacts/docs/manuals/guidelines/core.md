# Universal AI Agent Guidelines — CORE

## 0. System Interactions & MCP Protocols
- **Logical Root**: Your root `/` is the `artifacts/` folder. You cannot see or access anything above this directory.
- **Mandatory Structure**: You must strictly adhere to the following hierarchy for all project artifacts:
    - `/session.md`: Current session state (SSOT).
    - `/spec.md`: Project specifications.
    - `/docs/features/active/`: Only place for ongoing work. Each feature must have its own folder `[ID]-[name]/`.
    - `/docs/decisions/adr/`: Only place for architectural decisions.
- **Remote Source access**: The `/src/` directory is a **REMOTE** entity. It is NOT part of your local filesystem. Access it ONLY via specialized Code Tools (e.g., `view_file_source`, `get_file_skeleton`).
- **Skill Discovery**: Role-addressable skill directories live at `/skills/` (e.g. `/skills/<name>/SKILL.md`) and are registered in `role_profiles.yaml` for automatic injection in `get_guideline` stubs.


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
- **Role Sequencing**: Each role's position in the pipeline — and what comes next — is defined per-project in `role_profiles.yaml` (the `next` and `requires_approval` fields), not in this document. The default project ships with a `discovery → architecture → planning → execution → discovery` cycle as one example configuration; a project may define different roles or a different ordering entirely. Individual phase-guideline files (e.g. `architecture.md`'s \"Phases 4–6\") use phase numbers purely as a human-readable label for that role's slice of the *default* pipeline — they are descriptive only and carry no structural meaning; only `role_profiles.yaml` and the directive below define actual sequencing.
- **Your Actual Directive**: If you arrived via `get_session_context` (the normal session-start path), trust the `=== NEXT STEP ===` block injected at the bottom of its output — it already resolves your role's `next` and `requires_approval` settings into a concrete HARD STOP or auto-advance instruction. If you instead arrived via `get_guideline(role)` (a deliberate mid-session role switch to a specific role), no such block is injected — your next role there is whatever you or the human explicitly switched to; consult `role_profiles.yaml` directly if you need that role's own `next` value.

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
## 4. Flexible Entry Points
Not every task needs the full pipeline starting from Discovery. A human may set `next_agent_role` in `session.md` to any registered role to begin a session there directly — for example, setting it to `execution` lets a small, well-understood change (a technical-debt cleanup, a hotfix) skip straight to implementation without an existing feature bundle. This already works today via standard `session.md` resolution; it is not a separate mechanism.

- **When to use**: The human explicitly sets `next_agent_role` to a non-Discovery role, or says something equivalent to "just fix this."
- **Minimum artefacts**: Update `session.md` with the task ID and a one-line description of the change. No `requirements.md` or `architecture.md` is required if the entry role doesn't need one.
- **Exit**: Standard exit rules for whichever role you entered as apply — e.g. tests pass and a PR is opened if you entered as Execution — and `next_agent_role` is set per that role's `next` field in `role_profiles.yaml`.

## 5. Skill & Playbook Protocol
Skills are self-contained procedure files (SKILL.md) that extend agent behaviour for specific situations. They are registered per-role in `role_profiles.yaml` under `playbooks[]`. Every agent — regardless of role — MUST follow this protocol at session start.

### 5.1 When to load skills

Skills are **not loaded blindly**. You are responsible for deciding which skills apply to the current task. Loading irrelevant skills wastes context — do not do it.

### 5.2 Protocol (mandatory steps)

**Step 1 — Read the skill menu**
At the start of every session, the PLAYBOOKS section of `get_session_context` lists the skills registered for your role. Each entry contains the file path and the skill's `description` from its frontmatter. Read every description carefully.

**Step 2 — Match against the current task**
For each skill ask: *Does the current task or phase match this skill's stated trigger?*

| Signal in description | Load if… |
|---|---|
| "before any creative work" | You are about to design, plan, or spec something new |
| "stress-test / grill a plan" | You have a draft design or requirement ready for review |
| "before implementation" | You are about to write code or scaffold anything |
| "break into issues / tasks" | You are about to create stories or backlog items |
| "documentation / PRD" | You are about to write a spec, requirements.md, or ADR |

If none match, proceed without loading any skill.

**Step 3 — Load matching skills**
Call `read_project_artifacts` for each skill path you decided to load. Read the full content before continuing.

**Step 4 — Follow loaded skills faithfully**
Once loaded, a skill's checklist and HARD-GATE rules are **mandatory**. Do not skip steps. Do not proceed past a HARD-GATE without explicit user approval.

**Step 5 — Chain skills when instructed**
Some skills explicitly invoke another skill at their terminal state (e.g. brainstorming → writing-plans). When you reach that terminal state, load the next skill before proceeding.

### 5.3 Where skills live

- Project-local skills: `skills/<name>/SKILL.md` (registered in `role_profiles.yaml`)
- External skills can be installed from `www.skills.sh` or `mcpmarket.com` via `npx skills add`
- After installing an external skill, register it in `role_profiles.yaml` under the relevant role

### 5.4 Anti-patterns to avoid

- ❌ Loading all registered skills regardless of the task
- ❌ Reading only the description and skipping the full SKILL.md content
- ❌ Acknowledging a HARD-GATE and then proceeding anyway
- ❌ Forgetting to chain to the next skill at a terminal state
- ❌ Installing a skill externally but not registering it in `role_profiles.yaml`
