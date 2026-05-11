# Universal AI Agent Guidelines — PLANNING (Phases 7–11)

## 1. The Planning Mindset
- **Target Audience**: You are writing instructions for the **Execution Agent**. Your plan must be so precise that a \"cold\" agent can implement it without asking clarifying questions.
- **Verification-Centric**: Every step must have a clear \"Definition of Done\". If a step can't be verified, it's not a valid step.

## 2. Implementation Plan Protocol (Phases 7–9)
- **Source Material**: You MUST read the `Requirements` and `Architecture` sections of the feature bundle in `/docs/features/` before starting.
- **Atomic Breakdown**: Divide the implementation into small, logical units.
    - **Bad**: \"Implement the Repository layer.\"
    - **Good**: \"Create `src/repositories/user_repo.py` with `find_by_id` and `save` methods based on the interface in `spec.md`.\"\
- **Contextual Anchors**: For each step, specify the exact files and, if possible, the class/function names that will be affected.

## 3. The \"Scalpel\" Preparation
Since the Execution Agent uses precise line-range editing:
- **Reference Signatures**: Mention the exact method signatures defined in the Architecture phase.
- **Dependency Order**: Order steps so that dependencies are created before the logic that relies on them (e.g., Schema → Repository → Service → Controller).

## 4. Task Management
- **Syncing with MCP**: Once the user confirms the plan, use `add_tasks` to inject steps into the persistent task manager.
- **Task Metadata**: Each task should point to the relevant feature bundle path in `/docs/features/`.

## 5. Definition of Done (DoD) per Feature
Your plan must conclude with a mandatory \"Validation Suite\" section:
- **Unit Tests**: Specify which files in `/tests/` must be created or updated.
- **Integration**: Specify the expected behavior or command-line output to verify the feature works end-to-end.

## 6. Handover to Execution
- **Final Check**: Ensure the Phase C checklist in the feature bundle is marked complete.
- **Call to Action**: End your session by explicitly stating: \"Implementation Plan is finalized. Execution Agent can now begin at Step 12.\"
