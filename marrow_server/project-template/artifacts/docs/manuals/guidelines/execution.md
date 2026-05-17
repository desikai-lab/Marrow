# Universal AI Agent Guidelines — EXECUTION (Phases 12–15)

## 1. Execution Philosophy
- **No Creativity**: Your Bible is the `implementation_plan.md`. Do not implement features or logic not described in the plan. If you see a better way, pause and request a plan revision from the Planning Agent.
- **Surgical Precision**: You do not "replace files". You "patch logic". Your primary tool is the Scalpel Protocol.

## 2. The Scalpel Protocol (Working with `src/`)
Since `src/` is a remote resource, follow this loop for every change:
1. **Locate**: Use `search_code_skeletons` to find the exact file and class.
2. **Examine**: Use `view_file_source` with specific line ranges to read the current implementation.
3. **Patch**: Apply changes using the appropriate write/patch tool.
4. **Validate**: Immediately call `get_file_skeleton` on the modified file to confirm the indexer sees the new structure and syntax is intact.

## 3. Test Implementation (Phase 14)
The Planning Agent specifies *what* to test. You implement and execute.

- **No Code Without Tests**: Every logic change in `src/` must have a corresponding test. The test file and method names are defined in the Planning Agent's Validation Suite — use them verbatim.
- **Pre-flight Check**: Before reporting "Done", run the full test suite as specified in the plan.
- **Evidence**: Paste successful test output into the `Execution Log` section of the feature bundle.
- **If test scope is missing from the plan**: Do not invent tests. Flag the gap to the human and request a plan update.

### 3.1 Feature Confirmation (Phase 15)
- If implementation is confirmed by the user → move `/docs/features/active/{ID}-{name}` to `/docs/features/archive/{year}/{month}/{roadmap_version}`.

## 4. Task Lifecycle & LanceDB
- **Atomic Updates**: Call `complete_tasks` as soon as a step is finished and verified — not at the end of the session.
- **Checklist Sync**: Keep `/docs/features/active/{ID}-{name}/implementation_plan.md` perfectly synced with actual progress.

## 5. Error Recovery
- **Linter/Compiler Errors**: Read the error log, use `view_file_source` on the exact lines from the stack trace, fix only those lines. Do not guess.
- **Rollback**: If implementation goes wrong, revert to the last known good state from skeletons or MCP rollback tools.

## 6. Final Handover (Phase 15)
- **Artifact Cleanup**: Remove temporary debug scripts or logs.
- **Session Finalization**:
    1. Update `session.md`: "Feature [Name] Implementation Completed. Tests passed."
    2. Set `next_agent_role: Discovery Agent`.
    3. State to the user: "All tasks completed, tests passed. Ready for final verification and closure."
    4. Do not close the session until the human confirms.

## 7. Git Protocol
- **Session start**: `git checkout main && git pull && git checkout -b <branch name from plan>`
- **During session**: Commit logical checkpoints with messages referencing the task ID.
- **Session end**: Push branch. If task is complete, open PR against `main`.
- **Multi-session task**: Push at end of every session. Never leave uncommitted changes locally.
- **One branch per task**: If you discover unrelated issues, register a new task — do not fix them inline.
