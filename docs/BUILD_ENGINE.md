← Back to [README](../README.md)

# Build Engine

Marrow includes a declarative build system for assembling complex context payloads from multiple artifact sources. You can define a YAML manifest and run it to compile state, guidelines, decisions, or files into a single context file.

## Contents
- [Manifest format](#manifest-format)
- [Running a build](#running-a-build)
- [build admin command](#build-admin-command)

## Manifest format

Example manifest:

```yaml
# builds/my_context.yaml
name: feature_context
version: "1.0.0"
output:
  format: single_file
  filename: "context_{{DATE}}.md"
steps:
  - action: include_artifact
    path: session.md
    mode: full
  - action: include_artifact
    path: docs/decisions/adr/0034-product-name-marrow.md
    mode: section
    section_name: "Decision"
```

## Running a build

You can trigger a build via the MCP tool `run_project_build`, or run it locally using the admin CLI or build script:

```bash
python run_build.py --project MyProject --build my_context
```

Examples:
```bash
marrow-admin build --project MyProject --build my_context
marrow-admin build --project MyProject --build my_context --var FEATURE=Auth --verbose
```

## build admin command

| Flag | Description | Required |
|---|---|---|
| `--project` | Project name | Yes |
| `--build` | Build template name (without `.yaml` extension) | Yes |
| `--var KEY=VALUE` | Template variable override, repeatable | No |
| `--verbose` | Verbose output | No |

Also accessible via MCP tool `run_project_build`.
