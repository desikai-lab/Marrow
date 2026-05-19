from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Task Query ────────────────────────────────────────────────────────────────


class TaskSummary(BaseModel):
    """Returned by search_tasks_logic — lightweight list item."""

    id: str
    title: str
    status: str
    priority: str
    project: str


class TaskDetailResult(BaseModel):
    """Returned by get_task_details_logic — full task record from blob + index."""

    # Index fields (always present)
    key: str
    id: int
    type: str
    title: str
    status: str
    priority: str
    updated: str
    # Blob frontmatter fields (always present in valid blobs)
    blocked_by: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    project: str | None = None
    # Body sections (optional — may be absent in older blobs)
    problem: str | None = None
    solution: str | None = None
    comments: str | None = None
    resolution: str | None = None


# ── Task Command ──────────────────────────────────────────────────────────────


class TaskUpdateResult(BaseModel):
    """Returned by update_task_logic."""

    status: str
    task: TaskUpdateDetail


class TaskUpdateDetail(BaseModel):
    """Nested detail inside TaskUpdateResult."""

    id: str
    status: str
    updated: str


# ── Artifact Query ────────────────────────────────────────────────────────────


class TaskSemanticResult(BaseModel):
    """Returned by semantic_search_tasks_logic — vector search hit."""

    key: str
    title: str
    status: str
    score: float


class ArtifactSectionResult(BaseModel):
    """Returned by search_artifact_sections_logic — chunk search hit."""

    path: str
    section: str
    start_line: int
    end_line: int
    distance: float


# ── Artifact Command ──────────────────────────────────────────────────────────


class ArtifactWriteResult(BaseModel):
    """Single entry in save_project_artifacts_logic result list."""

    path: str | None = None
    status: str
    message: str


# ── Skeleton Query ────────────────────────────────────────────────────────────


class SkeletonChunkResult(BaseModel):
    """One skeleton chunk — returned by search_code_skeletons_logic,
    get_file_skeleton_logic, get_exact_code_units_logic."""

    path: str
    project: str
    chunk_type: str
    chunk_name: str
    skeleton_text: str | None = None
    start_line: int
    end_line: int
    distance: float = 0.0


class ProjectMapResult(BaseModel):
    """Returned by get_project_map_logic."""

    root: str = "."
    structure: dict[str, Any] = Field(default_factory=dict)
