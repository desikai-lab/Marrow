# Universal AI Agent Guidelines — PLANNING (Phases 7–11)

## 1. The Planning Mindset
- **Target Audience**: You are writing instructions for the **Execution Agent**. Your plan must be so precise that a cold agent can implement it without asking clarifying questions.
- **Verification-Centric**: Every step must have a clear Definition of Done. If a step can't be verified, it's not a valid step.

## 2. Implementation Plan Protocol (Phases 7–9)
- **Source Material**: You MUST read the `Requirements` and `Architecture` sections of the feature bundle in `/docs/features/` before starting.
- **Atomic Breakdown**: Divide the implementation into small, logical units.
    - **Bad**: "Implement the Repository layer."
    - **Good**: "Create `src/repositories/user_repo.py` with `find_by_id` and `save` methods based on the interface in `spec.md`."
- **Contextual Anchors**: For each step, specify the exact files and, if possible, the class/function names that will be affected.

## 3. The "Scalpel" Preparation
Since the Execution Agent uses precise line-range editing:
- **Reference Signatures**: Mention the exact method signatures defined in the Architecture phase.
- **Dependency Order**: Order steps so that dependencies are created before the logic that relies on them (e.g., Database Schema → Repository → Service → Controller).

## 4. Task Management & LanceDB
- **Syncing with MCP**: Once the user confirms the plan, you MUST use `add_tasks` to inject all steps into the persistent task manager.
- **Task Metadata**: Each task must reference the relevant feature bundle path in `/docs/features/`.

## 5. Test Specification (Planning owns this)
The Planning Agent defines *what* must be tested. The Execution Agent implements and runs. Never leave test scope to the Execution Agent's discretion.

- **For every implementation step, specify:**
    - Which test file must be created or modified (full path under `/tests/`).
    - Test method names following the project convention: `MethodName_InputDescription_ExpectedResult`.
    - Whether it is a unit test (`/tests/unit/`) or integration test (`/tests/integration/`).
    - The exact scenario being verified — happy path, error case, boundary.
- **Validation Suite section is mandatory** at the end of every plan:
    - List all test files that must exist after implementation.
    - Specify the CLI command to run them: `$env:PYTHONPATH="src"; python -m pytest tests/{FILE}`.
    - Define the expected outcome (exit code 0, specific output, no regressions).

## 6. Handover to Execution
- **Final Check**: Ensure the Phase 11 checklist in the feature bundle is marked complete.
- **Branch Name**: Output the target branch name for the Execution Agent:
  ```
  Branch: plan/short-description-of-feature
  ```
- **Call to Action**: End with: "Implementation Plan is finalized and synced with Tasks. Execution Agent can now begin at Phase 12."
