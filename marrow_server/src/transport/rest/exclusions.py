REST_EXCLUSIONS: dict[str, str] = {
    "list_projects": "Global: would reveal other projects under a per-project key (REQ-03).",
    "init_project": "Global: creates projects that have no key yet (REQ-03).",
    "run_project_build": "Deferred by human decision 2026-10-01 (H2); needs an async-job design (ADR-0019).",
}
