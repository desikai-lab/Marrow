from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa

from config import EMBEDDING_DIMENSIONS

# PyArrow schema for LanceDB
TASK_SCHEMA = pa.schema([
    pa.field("id",        pa.int64()),           # Integer ID (sequential)
    pa.field("key",       pa.string()),          # "F1", "B23"
    pa.field("title",     pa.string()),
    pa.field("type",      pa.string()),          # "F" / "B" / "TD"
    pa.field("status",    pa.string()),
    pa.field("priority",  pa.string()),
    pa.field("file_path", pa.string()),          # relative: "db/blobs/active/F1.md"
    pa.field("updated",   pa.string()),          # ISO datetime string
    pa.field("project",   pa.string()),
    pa.field("vector",    pa.list_(pa.float32(), EMBEDDING_DIMENSIONS)), # Semantic vector (Phase 3)
])

@dataclass
class TaskRecord:
    """DTO bridging the LanceDB index and .md blobs."""
    id: int
    key: str
    title: str
    type: str
    status: str
    priority: str
    file_path: str       # relative path from PROJECTS_ROOT/{project}/
    updated: str
    project: str
    
    # Fields from the blob body (not in the LanceDB index):
    problem: str | None = None
    solution: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    where: list[str] = field(default_factory=list)
    comments: str | None = None
    resolution: str | None = None
    
    # Vector for semantic search
    vector: list[float] | None = None

    def to_index_row(self) -> dict[str, Any]:
        """Returns only the LanceDB-schema fields."""
        row = {
            "id": self.id,
            "key": self.key,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "file_path": self.file_path,
            "updated": self.updated,
            "project": self.project,
        }
        if self.vector is not None:
            row["vector"] = self.vector
        return row

# --- Artifacts (Phase 3) ---

ARTIFACT_SCHEMA = pa.schema([
    pa.field("path",    pa.string()),          # relative path: "docs/readme.md"
    pa.field("updated", pa.string()),          # ISO datetime
    pa.field("vector",  pa.list_(pa.float32(), EMBEDDING_DIMENSIONS)),
])

@dataclass
class ArtifactRecord:
    """DTO for storing artifact vectors."""
    path: str
    updated: str
    vector: list[float] | None = None

    def to_index_row(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "updated": self.updated,
            "vector": self.vector
        }

ARTIFACT_CHUNK_SCHEMA = pa.schema([
    pa.field('path',       pa.string()),
    pa.field('section',    pa.string()),
    pa.field('start_line', pa.int32()),
    pa.field('end_line',   pa.int32()),
    pa.field('updated',    pa.string()),
    pa.field('vector',     pa.list_(pa.float32(), EMBEDDING_DIMENSIONS)),
])

@dataclass
class ArtifactChunkRecord:
    path: str
    section: str
    start_line: int
    end_line: int
    updated: str
    vector: list[float] | None = None

    def to_index_row(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "section": self.section,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "updated": self.updated,
            "vector": self.vector
        }


# --- Code Skeleton Index (SKEL-7) ---

SKELETON_CHUNK_SCHEMA = pa.schema([
    pa.field('path',          pa.string()),          # e.g. "src/Services/BigService.cs"
    pa.field('project',       pa.string()),          # e.g. "YourProject"
    pa.field('chunk_type',    pa.string()),          # "namespace" | "class" | "method" | ...
    pa.field('chunk_name',    pa.string()),          # e.g. "YourProject.Services", "ProcessOrder"
    pa.field('skeleton_text', pa.string()),          # raw extracted skeleton text
    pa.field('start_line',    pa.int32()),
    pa.field('end_line',      pa.int32()),
    pa.field('updated',       pa.string()),          # ISO 8601 UTC
    pa.field('is_test',       pa.bool_()),           # True if path matches test file patterns (ADR-23)
    pa.field('vector',        pa.list_(pa.float32(), EMBEDDING_DIMENSIONS)),
])


@dataclass
class SkeletonChunkRecord:
    """DTO for a single pre-vectorized code skeleton chunk (sent by marrow_worker)."""
    path: str
    project: str
    chunk_type: str
    chunk_name: str
    skeleton_text: str
    start_line: int
    end_line: int
    updated: str
    is_test: bool = False
    vector: list[float] | None = None

    def to_index_row(self) -> dict[str, Any]:
        return {
            "path":          self.path,
            "project":       self.project,
            "chunk_type":    self.chunk_type,
            "chunk_name":    self.chunk_name,
            "skeleton_text": self.skeleton_text,
            "start_line":    self.start_line,
            "end_line":      self.end_line,
            "updated":       self.updated,
            "is_test":       self.is_test,
            "vector":        self.vector,
        }
