from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.enums import TaskPriority, TaskStatus, TaskType


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    project: Annotated[
        str | None, Field(default=None, description="Project name (e.g. 'YourProject', 'MCP')")
    ] = None
    type: Annotated[TaskType, Field(description="Task type: F (feature), B (bug), TD (tech debt)")]
    title: Annotated[str, Field(description="Short task title")]
    where: Annotated[Any, Field(default=[], description="List of affected files or modules")] = []
    problem: Annotated[str, Field(description="Detailed problem description")]
    solution: Annotated[str, Field(description="Proposed or implemented solution")]
    priority: Annotated[
        TaskPriority,
        Field(default=TaskPriority.medium, description="Priority: critical, high, medium, low"),
    ] = TaskPriority.medium
    blocked_by: Annotated[
        Any, Field(default=[], description="List of task IDs this task depends on")
    ] = []
    status: Annotated[
        TaskStatus,
        Field(
            default=TaskStatus.open,
            description="Current status (e.g. open, in_progress, paused, closed)",
        ),
    ] = TaskStatus.open

    @field_validator("title", "problem", "solution")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip() if isinstance(v, str) else v


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: Annotated[
        str, Field(description="Path to the artifact (e.g. 'README.md' or 'docs/spec.md')")
    ]
    mode: Annotated[
        Literal["full", "section", "lines"],
        Field(
            default="full",
            description="Read mode: 'full' (entire file), 'section' (single section), 'lines' (line range)",
        ),
    ] = "full"
    direction: Annotated[
        Literal["begin", "end"],
        Field(
            default="begin",
            description="Read direction: 'begin' (from start) or 'end' (from the end of file)",
        ),
    ] = "begin"
    section_name: Annotated[
        str | None, Field(default=None, description="Section header (for mode='section')")
    ] = None
    start_line: Annotated[
        int, Field(default=1, description="Starting line (for mode='lines' or pagination)")
    ] = 1
    end_line: Annotated[
        int | None, Field(default=None, description="Ending line (for mode='lines')")
    ] = None
    max_chars: Annotated[int, Field(default=10000, description="Response character limit")] = 10000
    skip_chars: Annotated[
        int, Field(default=0, description="Characters to skip from the beginning of selection")
    ] = 0
    line_numbers: Annotated[
        bool, Field(default=False, description="Include line numbers in response")
    ] = False

    extra_fields: Annotated[
        dict[str, Any], Field(default_factory=dict, description="Additional dynamic parameters")
    ]


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: Annotated[str, Field(description="Path to the artifact to write")]
    content: Annotated[
        str,
        Field(
            description="Content to write or replace. In 'patch' mode, this is the replacement string."
        ),
    ]
    mode: Annotated[
        Literal[
            "replace_file",
            "replace_section",
            "append_section",
            "replace_chunk",
            "patch",
            "delete_section",
        ],
        Field(
            default="replace_file",
            description="Write mode: replace_file, replace_section, append_section, replace_chunk, patch, delete_section",
        ),
    ] = "replace_file"

    extra_fields: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Additional dynamic parameters (e.g. old_str, start_line)",
        ),
    ]

    section_name: Annotated[
        str | None,
        Field(default=None, description="Section header (for append/replace/delete_section)"),
    ] = None
    old_str: Annotated[
        str | None,
        Field(default=None, description="String to find and replace (mode='patch' only)"),
    ] = None
    start_line: Annotated[
        int, Field(default=1, description="Starting line (mode='replace_chunk' only)")
    ] = 1
    end_line: Annotated[
        int | None, Field(default=None, description="Ending line (mode='replace_chunk' only)")
    ] = None
    header_level: Annotated[
        int, Field(default=2, description="Markdown header level (e.g. 2 for '##')")
    ] = 2

    @model_validator(mode="after")
    def validate_content_by_mode(self) -> "WriteRequest":
        # Content can be empty only for section deletion or chunk replacement (line deletion)
        if self.mode not in ["delete_section", "replace_chunk"] and not self.content.strip():
            raise ValueError(f"Field 'content' cannot be empty for mode '{self.mode}'")
        return self
