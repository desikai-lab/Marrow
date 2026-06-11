# Playbooks — Convention & Schema

This folder contains role-addressable procedure documents (playbooks) that agents load at
session start to guide recurring workflows.

## Storage convention

- Each playbook is a single Markdown file directly inside `docs/playbooks/`.
- Filenames use kebab-case: `<purpose>.md` (e.g. `pr-review.md`, `post-merge-cleanup.md`).
- Playbooks are indexed by the artifact pipeline — they are discoverable via `get_applicable_playbooks`.

## Frontmatter schema

Every playbook MUST begin with a YAML frontmatter block:

```yaml
---
title: "<human-readable name>"
triggers:
  - "<situation or keyword that makes this playbook relevant>"
scope: "<which roles or task types this applies to>"
last_updated: "YYYY-MM-DD"
---
```

Frontmatter is convention only — it is not parsed by the service. Semantic search operates on
chunk content. Malformed or missing frontmatter degrades gracefully (file still indexed as plain text).

## Linking a playbook to a role

To make a playbook automatically injected into `get_guideline` output for a role, add its path
to the role's `playbooks` list in `docs/manuals/role_profiles.yaml`:

```yaml
roles:
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: [...]
    playbooks:
      - docs/playbooks/pr-review.md
```

Playbooks not listed in a role profile are still searchable via `get_applicable_playbooks`.
