from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from operations import code_intel as code_intel_ops
from pydantic import Field
from utils.error_middleware import mcp_error_handler


def use_code_tools(mcp: FastMCP) -> None:
    """Register the code tools on `mcp`."""

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
        return await code_intel_ops.search_code_skeletons(
            project, query, chunk_type, limit, include_tests, root_path
        )

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
        return await code_intel_ops.get_file_skeleton(project, path, depth, summary_only)

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
        return await code_intel_ops.get_project_map(project, depth, include_tests)

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
        return await code_intel_ops.view_file_source(project, path, start_line, end_line)
