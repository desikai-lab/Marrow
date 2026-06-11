---
title: "PR Review Checklist"
triggers:
  - "pull request"
  - "code review"
  - "open PR"
  - "ready to merge"
scope: "execution"
last_updated: "2026-06-12"
---

# PR Review Checklist

Use this playbook whenever opening or reviewing a pull request.

## Before opening a PR

1. Run `ruff check .` — zero violations required.
2. Run the full test suite: `pytest tests/` — all passing, no regressions.
3. Confirm branch is named per ADR-0035 convention (`feature/`, `td/`, `hotfix/`).
4. Verify branch is off latest `main` (`git log --oneline main..HEAD`).

## PR description

- Title: one-line summary matching the task title.
- Body: link to the task ID and feature bundle path.
- Note any deliberate deviations from the architecture doc.

## After merge

1. Delete the feature branch.
2. Update `session.md`: set `next_agent_role: Discovery Agent` and write SESSION EXIT.
3. Mark the task `done` via `complete_tasks`.
