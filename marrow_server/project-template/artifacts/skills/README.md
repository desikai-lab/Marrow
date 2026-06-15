# Skills — Convention & Schema

This folder contains role-addressable procedure documents (skills/playbooks) that agents load at
session start to guide recurring workflows.

## Storage convention

- Each skill is stored in its own directory under `skills/`: `skills/<skill-name>/SKILL.md`.
- `SKILL.md` is the entry point for the skill, containing frontmatter and instructions.
- Any companion files (templates, prompt fragments) the skill needs live in the same directory and are referenced by their relative artifact paths.
- Filenames and directory names use kebab-case (e.g. `skills/pr-review/SKILL.md`).

## Frontmatter schema

Every skill's `SKILL.md` MUST begin with a YAML frontmatter block:

```yaml
---
name: "<unique-kebab-case-name>"
title: "<human-readable name>"
description: |
  <description of when and how to use the skill>
triggers:
  - "<situation or keyword that makes this skill relevant>"
scope: "<which roles or task types this applies to>"
last_updated: "YYYY-MM-DD"
---
```

Frontmatter is parsed by `playbook_service` to generate stub indexes. If a file is missing frontmatter, it degrades gracefully to a path-only reference.

## Linking a skill to a role

To make a skill automatically injected as a stub into `get_guideline` output for a role, add its path
to the role's `playbooks` list in `docs/manuals/role_profiles.yaml`:

```yaml
roles:
  execution:
    guideline: docs/manuals/guidelines/execution.md
    adrs: [...]
    playbooks:
      - skills/pr-review/SKILL.md
```

## Retrieval

Agents retrieve skill content directly using the path in the guideline stub by calling the `read_project_artifacts` tool. Companion files are read the same way as directed by the skill body.
