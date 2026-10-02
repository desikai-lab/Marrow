"""Request bodies. Field names equal the MCP tool parameter names (checked by the parity test)."""

from typing import Any

from models import ReadRequest, TaskInput, WriteRequest
from pydantic import BaseModel


class AddTasksBody(BaseModel):
    tasks: list[TaskInput]


class UpdateTaskBody(BaseModel):
    updates: dict[str, Any]


class CompleteTasksBody(BaseModel):
    task_ids: list[str]


class SemanticSearchBody(BaseModel):
    query: str
    limit: int = 5
    scopes: list[str] | None = None


class TextSearchBody(BaseModel):
    query: str


class ReadArtifactsBody(BaseModel):
    reads: list[ReadRequest]


class WriteArtifactsBody(BaseModel):
    updates: list[WriteRequest]


class MoveArtifactBody(BaseModel):
    src_path: str
    dest_path: str


class RestoreArtifactBody(BaseModel):
    path: str
    backup_name: str


class CodeSearchBody(BaseModel):
    query: str
    chunk_type: str | None = None
    limit: int = 10
    include_tests: bool = False
    root_path: str | None = None
