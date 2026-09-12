import os
from dataclasses import dataclass, field

import yaml
from common import path_resolver
from common.path_resolver import ResourceKind
from common.project_file_error import ProjectFileError

PROJECT_META_FILENAME = "project.yaml"


@dataclass
class ProjectMeta:
    schema_versions: dict[str, int] = field(default_factory=dict)
    plugins: dict = field(default_factory=dict)


def get_subsystem_version(meta: ProjectMeta, subsystem: str) -> int:
    """Missing subsystem key defaults to version 1 (the pre-framework baseline), per ADR-0046 Decision 1."""
    return meta.schema_versions.get(subsystem, 1)


def load_project_meta(project: str) -> ProjectMeta:
    try:
        raw_path = path_resolver.get_raw_path(
            project, PROJECT_META_FILENAME, ResourceKind.MARROW_META
        )
    except ProjectFileError:
        return ProjectMeta()

    if not os.path.exists(raw_path):
        return ProjectMeta()

    with open(raw_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return ProjectMeta(
        schema_versions=dict(data.get("schema_versions") or {}),
        plugins=dict(data.get("plugins") or {}),
    )


def save_project_meta(project: str, meta: ProjectMeta) -> None:
    """Atomic write: temp file in the same directory, then os.replace (POSIX/NTFS atomic rename
    within one filesystem) -- ADR-0046 Decision point on .marrow/project.yaml atomicity."""
    raw_path = path_resolver.get_raw_path(project, PROJECT_META_FILENAME, ResourceKind.MARROW_META)
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)

    payload = {"schema_versions": meta.schema_versions, "plugins": meta.plugins}
    tmp_path = raw_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp_path, raw_path)
