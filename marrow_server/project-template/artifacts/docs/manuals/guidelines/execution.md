# Universal AI Agent Guidelines — EXECUTION (Phases 12–15)

## 1. Execution Philosophy
- **No Creativity**: Your Bible is the `implementation_plan.md`. Do not implement features or logic not described in the plan. If you see a better way, pause and ask for a plan revision.
- **Surgical Precision**: You do not \"replace files\". You \"patch logic\". Your primary tool is the **Scalpel Protocol**.

## 2. The Scalpel Protocol (Working with `src/`)
Since `src/` is a remote resource, follow this loop for every change:
1. **Locate**: Use `search_code_skeletons` to find the exact file and class.
2. **Examine**: Use `view_file_source` with specific line ranges to read the current implementation.
3. **Patch**: Apply changes via the write/patch tool.
4. **Validate**: Immediately call `get_file_skeleton` on the modified file to confirm the indexer sees the new structure.

## 3. Mandatory Testing (Step 14)
- **No Code Without Tests**: For every logic change in `src/`, there must be a corresponding change or new file in `/tests/`.
- **Pre-flight Check**: Before reporting \"Done\", execute the test suite.
- **Evidence**: Paste successful test output into the `Execution Log` section of the feature bundle.

## 3.1 Feature Confirmation (Step 15)
- If feature implementation is confirmed by the user → move `/docs/features/active/{ID}-{name}` to `/docs/features/archive/{year}/{month}/{version}`.

## 4. Task Lifecycle
- **Atomic Updates**: As soon as a step from the Implementation Plan is finished and verified, call `complete_tasks`.
- **Checklist Sync**: Keep the checklist in the feature folder perfectly synced with actual progress.

## 5. Error Recovery
- **Linter/Compiler Errors**: Read the error log, use `view_file_source` to see the lines in the stack trace, fix only those lines.
- **Rollback**: If an implementation goes wrong, revert to the last known good state from the skeletons.

## 6. Final Handover (Step 15)
- **Artifact Cleanup**: Remove any temporary debug scripts or logs.
- **Session Finalization**:
    1. Update `session.md` with \"Feature [Name] Implementation Completed\".
    2. State to the user: \"All tasks completed, tests passed. Ready for final verification and closure.\"\
    3. Do not close the session until the human confirms.
