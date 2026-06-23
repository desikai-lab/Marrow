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
        """[TASK TOOLS] Search tasks through LanceDB."""
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
        """[TASK TOOLS] Updates a task."""
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
        """[SESSION TOOLS] Assemble and return the full context bundle (guidelines + ADRs) for a given agent role."""
        return await asyncio.to_thread(get_guideline_logic, project, role)

    ## Project tools

    @mcp.tool()
    @mcp_error_handler
    async def list_projects() -> list[str] | dict[str, Any]:
        """[PROJECT TOOLS] Returns a list of all available projects."""
        return await asyncio.to_thread(list_projects_logic)

    ## Artifact tools

    @mcp.tool()
    @mcp_error_handler
    async def read_project_artifacts(
        project: Annotated[str, Field(description="Project name")],
        reads: Annotated[list[ReadRequest], Field(description="List of read requests")],
    ) -> list[dict[str, Any]]:
        """[ARTIFACT TOOLS] Allows reading one or more artifacts."""
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
        """[ARTIFACT TOOLS] Allows creating/updating one or more artifacts."""
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
        """[ARTIFACT TOOLS] Returns files in artifact storage."""
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
        """[ARTIFACT TOOLS] Safely deletes an artifact."""
        return await delete_project_artifact_logic(project, path)

    @mcp.tool()
    @mcp_error_handler
    async def search_project_artifacts(
        project: Annotated[str, Field(description="Project name")],
        query: Annotated[str, Field(description="Search text")],
    ) -> list[dict[str, Any]]:
        """[ARTIFACT TOOLS] Global search across artifacts."""
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
        """[HISTORY TOOLS] List of history versions."""
        return await asyncio.to_thread(list_artifact_history_logic, project, path)

    @mcp.tool()
    @mcp_error_handler
    async def restore_project_artifact(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to artifact")],
        backup_name: Annotated[str, Field(description="Backup name")],
    ) -> str | dict[str, Any]:
        """[HISTORY TOOLS] Restores an artifact version."""
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
        """[BUILD TOOLS] Executes build pipeline."""
        result = await asyncio.to_thread(
            run_project_build_logic, project, build_name, variables=variables
        )
        return result.model_dump()
