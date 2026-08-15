"""
MCP Tool Registry — single source of truth for all tool stubs.
Add a new tool here; mcp_core.py bootstrapper picks it up automatically.
"""

import asyncio
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from models import ReadRequest, TaskInput, WriteRequest
from pydantic import Field
from services.artifact_command_service import save_project_artifacts_logic
from services.artifact_query_service import search_artifact_sections_logic
from services.skeleton_query_service import (
    get_file_skeleton_logic,
    get_project_map_logic,
    search_code_skeletons_logic,
)
from services.task_command_service import add_tasks_logic, complete_tasks_logic, update_task_logic
from services.task_query_service import get_task_details_logic, search_tasks_logic
from tools import (
    delete_project_artifact_logic,
    get_guideline_logic,
    get_project_artifact_outline_logic,
    get_session_context_logic,
    list_artifact_history_logic,
    list_artifacts_logic,
    list_projects_logic,
    move_project_artifact_logic,
    read_project_artifacts_logic,
    restore_project_artifact_logic,
    run_project_build_logic,
    search_project_artifacts_logic,
    view_file_source_logic,
)
from utils.error_middleware import mcp_error_handler


def register_all_tools(mcp: FastMCP) -> None:
    """Mount all MCP tools onto the provided FastMCP instance."""

    # MCP Tool Registration
    ## Task tools
    @mcp.tool()
    @mcp_error_handler
    async def add_tasks(
        project: Annotated[str, Field(description="Project name (e.g. 'YourProject', 'MCP')")],
        tasks: Annotated[list[TaskInput], Field(description="List of new tasks")],
    ) -> str | dict[str, Any]:
        """[TASK TOOLS] Adds a list of tasks to the project backlog."""
        return await add_tasks_logic(tasks, project)

    @mcp.tool()
    @mcp_error_handler
    async def search_tasks(
        project: Annotated[str, Field(description="Project name")],
        status: Annotated[str | None, Field(description="Status filter")] = "open",
        priority: Annotated[str | None, Field(description="Priority filter")] = None,
        type: Annotated[str | None, Field(description="Type filter")] = None,
    ) -> list[Any]:
        """[TASK TOOLS] Queries the task backlog in LanceDB with optional filters and returns
        matching task summaries ranked by creation order.

        All parameters are optional filters — omit to retrieve all tasks with default status.
        Default status filter is 'open'; pass status=None to retrieve tasks of all statuses.
        Do NOT call get_task_details on every result — use this tool for status checks and
        task selection, then call get_task_details on the single selected task for full content.

        Allowed `status` values:    open | in_progress | blocked | done | None (no filter)
        Allowed `priority` values:  low | medium | high | critical | None (no filter)
        Allowed `type` values:      feature | bug | task | td | None (no filter)

        Returns: list of task summary objects — each with task_id, title, status, priority,
                 type, and blocked_by. Full problem/solution content is excluded; call
                 get_task_details for that.
        Raises:  404 if project is not found.
        """
        results = await search_tasks_logic(project, status, priority, type)
        return [r.model_dump() for r in results]

    @mcp.tool()
    @mcp_error_handler
    async def get_task_details(
        project: Annotated[str, Field(description="Project name")],
        task_id: Annotated[str, Field(description="Task ID")],
    ) -> Any:
        """[TASK TOOLS] Returns full task details."""
        result = await get_task_details_logic(project, task_id)
        return result.model_dump()

    @mcp.tool()
    @mcp_error_handler
    async def update_task(
        project: Annotated[str, Field(description="Project name")],
        task_id: Annotated[str, Field(description="Task ID")],
        updates: Annotated[dict[str, Any], Field(description="Updates dict")],
    ) -> Any:
        """[TASK TOOLS] Partially updates mutable fields on an existing task (status, priority,
        title, solution, etc.) using a merge strategy — only keys present in `updates` are
        changed; all other fields remain intact. Use this for in-progress changes (e.g.
        updating priority or editing the solution).

        Do NOT use to close a task — call complete_tasks instead, which atomically closes
        and auto-unblocks dependents.
        Do NOT use to create tasks — call add_tasks instead.

        Allowed `updates` keys:
          status        : open | in_progress | blocked | done
          priority      : low | medium | high | critical
          title         : str
          problem       : str
          solution      : str
          blocked_by    : list[task_id]

        Returns: updated task object with all current field values.
        Raises:  404 if task_id not found in project.
        """
        result = await update_task_logic(project, task_id, updates)
        return result.model_dump()

    @mcp.tool()
    @mcp_error_handler
    async def complete_tasks(
        project: Annotated[str, Field(description="Project name")],
        task_ids: Annotated[
            list[str],
            Field(description="List of task keys to complete, e.g. ['TD4000078', 'TD4000080']"),
        ],
    ) -> str | dict[str, Any]:
        """[TASK TOOLS] Atomically closes one or more tasks and auto-unblocks dependents."""
        return await complete_tasks_logic(task_ids, project)

    @mcp.tool()
    @mcp_error_handler
    async def semantic_search(
        project: Annotated[str, Field(description="Project name")],
        query: Annotated[str, Field(description="Search text")],
        limit: Annotated[int, Field(description="Max results")] = 5,
    ) -> Any:
        """
        [ARTIFACT TOOLS] Perform semantic search on artifact sections.
        Calculates embeddings vector for the query and searches top results by distance.
        Returns the path, section name, line numbers, and distance.
        """
        results = await search_artifact_sections_logic(project, query, limit)
        return [r.model_dump() for r in results]

    @mcp.tool()
    @mcp_error_handler
    async def search_code_skeletons(
        project: Annotated[str, Field(description="Project name (e.g. 'YourProject')")],
        query: Annotated[
            str,
            Field(
                description="Natural language search query, e.g. 'order processing method' or 'database context constructor'"
            ),
        ],
        chunk_type: Annotated[
            str | None,
            Field(
                description="Optional filter by code unit type: 'namespace', 'class', 'method', 'constructor', 'property', 'file', etc."
            ),
        ] = None,
        limit: Annotated[int, Field(description="Maximum number of results to return")] = 10,
        include_tests: Annotated[
            bool, Field(description="Include test file chunks in results (default False)")
        ] = False,
        root_path: Annotated[
            str | None,
            Field(description="Restrict search to files under this path prefix, e.g. 'src/worker'"),
        ] = None,
    ) -> list[dict[str, Any]]:
        """
        [CODE TOOLS] Semantic search over indexed source code skeletons.
        Searches the code_skeleton_index populated by marrow_worker.
        Returns matching code units (methods, classes, namespaces, etc.) ranked by
        semantic similarity to the query, each with file path, line range, and skeleton text.
        Use root_path to scope to a module.
        """
        results = await search_code_skeletons_logic(
            project,
            query,
            chunk_type=chunk_type,
            limit=limit,
            include_tests=include_tests,
            root_path=root_path,
        )
        return [r.model_dump() for r in results]

    @mcp.tool()
    @mcp_error_handler
    async def get_file_skeleton(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[
            str, Field(description="Path to the source file (e.g. 'src/services/billing.ts')")
        ],
        depth: Annotated[
            int,
            Field(
                description="0=full (default) | 1=class/namespace names only, no skeleton_text | 2=classes+method signatures"
            ),
        ] = 2,
        summary_only: Annotated[
            bool, Field(description="Strip skeleton_text from output (applies at depth=0 only)")
        ] = False,
    ) -> list[dict[str, Any]]:
        """
        [CODE TOOLS] Retrieves a token-optimized outline of a file's code units (classes, methods) with line numbers.
        Use depth=1 for orientation (names only), depth=2 for analysis (signatures), depth=0 for full detail.
        """
        results = await get_file_skeleton_logic(
            project, path, depth=depth, summary_only=summary_only
        )
        return [r.model_dump() for r in results]

    @mcp.tool()
    @mcp_error_handler
    async def get_project_map(
        project: Annotated[str, Field(description="Project name")],
        depth: Annotated[int, Field(description="Maximum directory depth to show (default 4)")] = 4,
        include_tests: Annotated[
            bool, Field(description="Include test files in the map (default False)")
        ] = False,
    ) -> dict[str, Any]:
        """
        [CODE TOOLS] Returns a live directory tree of all files indexed in the code skeleton index.
        Use this to orient yourself and find relevant subdirectories before starting a scoped search.
        """
        result = await get_project_map_logic(project, depth=depth, include_tests=include_tests)
        return result.model_dump()

    @mcp.tool()
    @mcp_error_handler
    async def view_file_source(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Relative path to the file from SOURCE_ROOT")],
        start_line: Annotated[int, Field(description="First line to retrieve (1-based)")],
        end_line: Annotated[int, Field(description="Last line to retrieve (1-based)")],
    ) -> str | dict[str, Any]:
        """
        [CODE TOOLS] Read a precise line range from the live source repository ("The Scalpel").
        Requires SOURCE_ROOT to be configured in project/.settings.
        """
        return await asyncio.to_thread(view_file_source_logic, project, path, start_line, end_line)

    @mcp.tool()
    @mcp_error_handler
    async def get_session_context(
        project: Annotated[str, Field(description="Project name to read session state from")],
        start_role: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional. If provided, resolve this role directly without reading "
                    "session.md. Useful for invoking standalone or on-demand roles without "
                    "disturbing pipeline state. Returns an error string listing valid roles "
                    "if the value is unrecognised."
                ),
            ),
        ] = None,
    ) -> str:
        """[SESSION TOOLS] Reads session.md, detects the active pipeline phase,
        and returns core guidelines + phase-appropriate role guidelines + filtered foundational ADRs
        + role-linked skill stubs (=== PLAYBOOKS === section, when the role has skills registered)
        as a single assembled string.

        If start_role is provided, session.md is bypassed entirely: the named role
        is resolved directly and SESSION STATE is omitted from the response.
        """
        return await asyncio.to_thread(get_session_context_logic, project, start_role)

    @mcp.tool()
    @mcp_error_handler
    async def get_guideline(
        project: Annotated[str, Field(description="Project name")],
        role: Annotated[str, Field(description="Agent role name (e.g. 'discovery', 'execution')")],
    ) -> str:
        """[SESSION TOOLS] Assembles and returns the full context bundle (core guidelines +
        role-specific phase guidelines + filtered foundational ADRs) for a named agent role,
        without reading or modifying session.md.

        Use this for deliberate mid-session role switches when you already know the target
        role and do not want to disturb pipeline state.
        Do NOT use at session start — call get_session_context instead, which also injects
        the SESSION STATE block and the correct NEXT STEP directive.

        Allowed `role` values: any role registered in the project's role_profiles.yaml
        (e.g. 'discovery', 'architecture', 'planning', 'execution'). Returns an error
        string listing valid roles if the value is unrecognised.

        Returns: assembled markdown string (core guidelines + role guidelines + ADRs).
        Raises:  error string if role is not registered in role_profiles.yaml.
        """
        return await asyncio.to_thread(get_guideline_logic, project, role)

    ## Project tools

    @mcp.tool()
    @mcp_error_handler
    async def list_projects() -> list[str] | dict[str, Any]:
        """[PROJECT TOOLS] Returns a list of all available projects."""
        return await asyncio.to_thread(list_projects_logic)

    @mcp.tool()
    @mcp_error_handler
    async def init_project(
        project: Annotated[str, Field(description="Unique project name to create")],
        template: Annotated[str, Field(description="Scaffold template name")] = "default",
    ) -> dict[str, Any]:
        """[PROJECT TOOLS] Creates a new Marrow project workspace by copying the built-in
        default template into TASKS_DIR/projects/{project}. Produces a ready-to-use
        artifact tree (session.md, spec.md, guidelines, role_profiles.yaml).

        Primary use case: first-run initialization on Glama or any single-container
        deployment where shell access is unavailable. For docker-compose deployments,
        use the marrow-init service instead.

        Do NOT use to list existing projects — call list_projects instead.
        Do NOT use to read session state — call get_session_context(project) after init.

        Parameters:
          project   : str — unique project name (must not already exist)
          template  : str — scaffold template; only "default" is supported in this release

        Returns: { project, files_created } where files_created lists
                 every file path copied into the new workspace (relative to workspace root).

        Raises: ValidationError if project already exists or template is unsupported.
        """
        from tools.projects import init_project_logic

        result = await asyncio.to_thread(init_project_logic, project, template)
        return result.model_dump()  # returns { project, files_created }

    ## Artifact tools

    @mcp.tool()
    @mcp_error_handler
    async def read_project_artifacts(
        project: Annotated[str, Field(description="Project name")],
        reads: Annotated[list[ReadRequest], Field(description="List of read requests")],
    ) -> list[dict[str, Any]]:
        """[ARTIFACT TOOLS] Reads one or more artifact files in a single batch call.
        Each item in `reads` targets one file and specifies an independent read mode.

        Read modes per item:
          full    — returns the entire file content.
          paged   — windowed read of the entire file. max_chars (default 10000), skip_chars,
                    and direction (default).
          section — returns only the content under a named ## header (requires section_name).
          lines   — returns a specific line range (requires start_line and end_line).

        Optional per-item fields:
          max_chars     : int  — truncate response at N characters (default 10000).
          skip_chars    : int  — skip N characters from the start of the selection.
          direction     : 'begin' | 'end' — read from start or end of file (default 'begin').
          line_numbers  : bool — prefix each line with its 1-based line number.

        Do NOT loop this tool per file — batch all reads into a single call to minimise
        round-trips. For source code files in src/, use view_file_source instead.

        Returns: list of result objects — each with path and content (or error if not found).
        Raises:  per-item error entry if a path does not exist; does not abort the batch.
        """
        reads_dict = []
        for r in reads:
            d = r.model_dump()
            extra = d.pop("extra_fields", {})
            d.update(extra) if extra else None
            reads_dict.append(d)
        return await asyncio.to_thread(read_project_artifacts_logic, project, reads_dict)

    @mcp.tool()
    @mcp_error_handler
    async def save_project_artifacts(
        project: Annotated[str, Field(description="Project name")],
        updates: Annotated[list[WriteRequest], Field(description="List of write requests")],
    ) -> list[dict[str, Any]]:
        """[ARTIFACT TOOLS] Creates or updates one or more artifact files in a single
        atomic batch. Each item in `updates` targets one file and specifies an independent
        write mode — modes in the same batch do not interact.

        Write modes per update item:
          replace_file    — overwrites the entire file (creates it if absent).
          replace_section — replaces the content under a named ## header; raises if the
                            header appears more than once (ADR-0011).
          append_section  — appends a new ## section at the end of the file.
          replace_chunk   — replaces lines start_line..end_line with new content.
          patch           — finds old_str (must be unique in the file) and replaces it
                            with new content. Preferred for surgical single-line edits.
          delete_section  — removes a named ## section and its content.

        Do NOT use replace_file when only a section needs updating — use patch or
        replace_section to avoid clobbering concurrent edits.
        Do NOT use this tool for source code in src/ — the source directory is read-only
        from the agent's perspective.

        Returns: list of result objects, one per update — each with path and status.
        Raises:  duplicate-header error (with line numbers) if replace_section finds
                 multiple matching headers in the same file.
        """
        updates_dict = []
        for u in updates:
            d = u.model_dump()
            extra = d.pop("extra_fields", {})
            d.update(extra) if extra else None
            updates_dict.append(d)
        results = await save_project_artifacts_logic(project, updates_dict)
        return [r.model_dump() for r in results]

    @mcp.tool()
    @mcp_error_handler
    async def list_project_artifacts(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Relative folder path")] = "",
        recursive: Annotated[bool, Field(description="Recursive list")] = False,
    ) -> list[dict[str, str]]:
        """[ARTIFACT TOOLS] Lists artifact files in a project's artifact storage, optionally
        scoped to a subfolder and optionally traversing subdirectories.

        `path` narrows the listing to a specific folder (e.g. 'docs/features/active');
        omit or pass '' to list from the project root.
        `recursive=True` traverses all subdirectories; default is False (top-level only).

        Do NOT use to read file content — call read_project_artifacts instead.
        Do NOT use to browse source code — call get_project_map for the src/ tree.

        Returns: list of objects — each with path (relative to project root) and size in bytes.
        Raises:  404 if the project or path does not exist.
        """
        return await asyncio.to_thread(list_artifacts_logic, project, path, recursive=recursive)

    @mcp.tool()
    @mcp_error_handler
    async def move_project_artifact(
        project: Annotated[str, Field(description="Project name")],
        src_path: Annotated[str, Field(description="Source path")],
        dest_path: Annotated[str, Field(description="Destination path")],
    ) -> str | dict[str, Any]:
        """[ARTIFACT TOOLS] Moves or renames an artifact."""
        return await move_project_artifact_logic(project, src_path, dest_path)

    @mcp.tool()
    @mcp_error_handler
    async def delete_project_artifact(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to delete")],
    ) -> str | dict[str, Any]:
        """[ARTIFACT TOOLS] Permanently deletes a single artifact file from the project's
        artifact storage. The deletion is immediate and not automatically reversible.

        Before deleting, consider calling list_artifact_history to check whether a
        recoverable backup version exists — restore_project_artifact can recover a prior
        version if the file was previously saved with history enabled.
        Do NOT use to move or rename a file — call move_project_artifact instead.

        Returns: confirmation string with the deleted file path.
        Raises:  404 error if the path does not exist in artifact storage.
        """
        return await delete_project_artifact_logic(project, path)

    @mcp.tool()
    @mcp_error_handler
    async def search_project_artifacts(
        project: Annotated[str, Field(description="Project name")],
        query: Annotated[str, Field(description="Search text")],
    ) -> list[dict[str, Any]]:
        """[ARTIFACT TOOLS] Full-text search across all artifact files in a project,
        matching against file content and returning files and sections that contain
        the query string.

        Query is plain text — no special syntax required. Case-insensitive. For
        semantic / meaning-based search, use semantic_search instead.
        Do NOT use this to list files — call list_project_artifacts instead.
        Do NOT use this for source code — call search_code_skeletons instead.

        Returns: list of match objects — each with path, matched section name, and a
                 short excerpt of the matched content with surrounding context.
        Raises:  404 if the project does not exist.
        """
        return await search_project_artifacts_logic(project, query)

    @mcp.tool()
    @mcp_error_handler
    async def get_project_artifact_outline(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to .md file")],
    ) -> str | dict[str, Any]:
        """[ARTIFACT TOOLS] Extracts table of contents."""
        return await asyncio.to_thread(get_project_artifact_outline_logic, project, path)

    ## History tools

    @mcp.tool()
    @mcp_error_handler
    async def list_artifact_history(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to artifact")],
    ) -> list[dict[str, Any]]:
        """[HISTORY TOOLS] Returns the version history for a single artifact file — a list
        of backup snapshots automatically created by save_project_artifacts on each write.
        Each entry represents a point-in-time copy that can be restored.

        Use this to inspect available versions before calling restore_project_artifact.
        The most recent backup is listed first.
        Do NOT use this to read current file content — call read_project_artifacts instead.

        Returns: list of version objects — each with backup_name, created_at timestamp,
                 and size in bytes. Empty list if no history exists for the path.
        Raises:  404 if the artifact path does not exist in the project.
        """
        return await asyncio.to_thread(list_artifact_history_logic, project, path)

    @mcp.tool()
    @mcp_error_handler
    async def restore_project_artifact(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to artifact")],
        backup_name: Annotated[str, Field(description="Backup name")],
    ) -> str | dict[str, Any]:
        """[HISTORY TOOLS] Restores a named backup snapshot of an artifact, replacing the
        current live file with the backup content. The current live version is NOT
        automatically backed up before the restore — it will be overwritten.

        Use list_artifact_history first to retrieve valid backup_name values for the
        target path. The backup_name is the exact string returned in the history list.
        Do NOT guess or construct backup names — always read them from list_artifact_history.

        Returns: confirmation string with the restored path and backup_name applied.
        Raises:  404 if the path or backup_name does not exist.
        """
        return await asyncio.to_thread(restore_project_artifact_logic, project, path, backup_name)

    ## Build tools

    @mcp.tool()
    @mcp_error_handler
    async def run_project_build(
        project: Annotated[str, Field(description="Project name")],
        build_name: Annotated[str, Field(description="Manifest name")],
        variables: Annotated[
            dict[str, str] | None,
            Field(default=None, description='Runtime template variables e.g. {"FEATURE": "Auth"}'),
        ] = None,
    ) -> str | dict[str, Any]:
        """[BUILD TOOLS] Executes a named build pipeline defined in the project's build
        manifest (a YAML file registered under docs/builds/ in the artifact store).
        The manifest defines the sequence of steps (shell commands, artifact writes,
        tool calls) that run in order.

        Optional `variables` dict injects runtime values into manifest template
        placeholders, e.g. {"FEATURE": "Auth"} replaces {{FEATURE}} in step definitions.

        Do NOT use this to read or write individual artifacts — call save_project_artifacts
        or read_project_artifacts instead.

        Returns: build result object with status (success | failure), step outputs, and
                 elapsed time.
        Raises:  404 if build_name does not match any manifest in the project.
                 RuntimeError if any step in the pipeline fails (includes step output).
        """
        result = await asyncio.to_thread(
            run_project_build_logic, project, build_name, variables=variables
        )
        return result.model_dump()
