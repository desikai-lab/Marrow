← Back to [README](../README.md)

# Admin CLI Reference

Marrow ships two CLI entry points for operators and developers:
- **`marrow-admin`** — full admin surface (12 subcommands)
- **`marrow-skills`** — lightweight skills-only surface (4 subcommands, subset of marrow-admin)

> One-off migration: `repair_blobs.py` is a standalone script, not a registered subcommand.
> Run it directly when upgrading from a pre-blob-format release.

## Contents
- [marrow-admin commands](#marrow-admin-commands)
  - [Project management](#project-management)
  - [Database operations](#database-operations)
  - [Indexing](#indexing)
  - [Skills management](#skills-management)
  - [Build](#build)
- [marrow-skills (standalone)](#marrow-skills-standalone)
- [repair_blobs.py (one-off migration)](#repair_blobspy)

---

## marrow-admin commands

### Project management

#### `project-init`
Initialize a new project workspace from the built-in template.
```bash
marrow-admin project-init --project <name>
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name (must be unique in TASKS_DIR) |

---

### Database operations

#### `health`
Database integrity check for a project.
```bash
marrow-admin health --project <name> [--json]
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |
| `--json` | No | Output result as JSON |

#### `maintenance`
LanceDB maintenance: compaction, version cleanup, and ghost pruning.
```bash
marrow-admin maintenance --project <name>
# or to run across all projects:
marrow-admin maintenance --all
```
> `--project` and `--all` are mutually exclusive.

#### `migrate`
Migrate YAML tasks to LanceDB.
```bash
marrow-admin migrate --project <name> [--dry-run] [--force]
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |
| `--dry-run` | No | Preview planned changes without writing |
| `--force` | No | Force update existing records |

---

### Indexing

#### `reindex`
Vector reindexing of tasks, artifacts, or both.
```bash
marrow-admin reindex --project <name> [--target {tasks,artifacts,both}] [--dry-run]
```
| Flag | Required | Description | Default |
|---|---|---|---|
| `--project` | Yes | Project name | — |
| `--target` | No | What to reindex | `both` |
| `--dry-run` | No | Do not write to database | off |

#### `reindex-chunks`
Section-based chunk reindexing (code skeleton index).
```bash
marrow-admin reindex-chunks --project <name> [--file <rel-path>] [--dry-run]
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |
| `--file` | No | Only reindex one specific file (relative path) |
| `--dry-run` | No | Do not write to database |

#### `diag-index`
Diagnose the code skeleton index for a project.
```bash
marrow-admin diag-index --project <name>
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name to inspect |

---

### Skills management

#### `skills-add`
Install a skill from a GitHub repository.
```bash
marrow-admin skills-add <repo_url> --project <name> --skill <skill-name>
```
| Arg / Flag | Required | Description |
|---|---|---|
| `repo_url` | Yes (positional) | GitHub repository URL |
| `--project` | Yes | Target project name |
| `--skill` | Yes | Skill name (folder under `skills/` in the repo) |

#### `skills-list`
List all skills installed in a project.
```bash
marrow-admin skills-list --project <name>
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |

#### `skills-update`
Update an installed skill to the latest version from its source repository.
```bash
marrow-admin skills-update --project <name> --skill <skill-name>
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |
| `--skill` | Yes | Skill name |

#### `skills-remove`
Remove an installed skill from a project.
```bash
marrow-admin skills-remove --project <name> --skill <skill-name>
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |
| `--skill` | Yes | Skill name |

---

### Build

#### `build`
Run a build pipeline from a YAML manifest. See [Build Engine](BUILD_ENGINE.md) for manifest format.
```bash
marrow-admin build --project <name> --build <template-name> [--var KEY=VALUE ...] [--verbose]
```
| Flag | Required | Description |
|---|---|---|
| `--project` | Yes | Project name |
| `--build` | Yes | Template name (without `.yaml` extension) |
| `--var KEY=VALUE` | No | Template variable override — repeatable |
| `--verbose` | No | Verbose output |

---

## marrow-skills (standalone)

`marrow-skills` is a lightweight entry point exposing only the four skills subcommands, for environments where the full admin surface is not needed. The commands and flags are identical to their `marrow-admin` counterparts:

```bash
marrow-skills skills-add <repo_url> --project <name> --skill <name>
marrow-skills skills-list --project <name>
marrow-skills skills-update --project <name> --skill <name>
marrow-skills skills-remove --project <name> --skill <name>
```

---

## repair_blobs.py

A one-time migration script for repairing corrupted Python-tagged YAML blob files. Not a registered subcommand — run it directly:

```bash
python repair_blobs.py <project_root>
```

> **When to use:** Only needed when upgrading from a release that used the old Python-tagged YAML blob format. Check the release notes before running.
