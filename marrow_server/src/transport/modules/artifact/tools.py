from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from models import ReadRequest, WriteRequest
from operations import artifacts as artifacts_ops
from pydantic import Field
from utils.error_middleware import mcp_error_handler


def use_artifact_tools(mcp: FastMCP) -> None:
    """Register the artifact tools on `mcp`."""

    @mcp.tool()
    @mcp_error_handler
    async def semantic_search(
        project: Annotated[str, Field(description="Project name")],
        query: Annotated[str, Field(description="Search text")],
        limit: Annotated[int, Field(description="Max results")] = 5,
        scopes: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Directory paths to restrict hits to (OR'd, max 20). "
                    "Omit for unscoped (default). Files won't match -- use "
                    "read_project_artifacts for a known file."
                )
            ),
        ] = None,
    ) -> Any:
        """
        [ARTIFACT TOOLS] Semantic search over artifact chunks, optionally scoped to
        one or more directories; returns each hit's location plus file content.
        Read-only.

        Parameters:
          project : project name.
          query   : natural-language search text.
          limit   : max hits. With scopes, applies to the combined OR result, not
                    per scope.
          scopes  : project-relative directory paths, max 20, OR semantics. Omit
                    (or None/[]) for unscoped -- unchanged from before this param
                    existed. Directories only; a file path simply matches nothing.

        Returns: on a normal or unscoped call, a list of hits (path, section,
          start_line, end_line, distance, content, warning -- as before). If
          scopes matched zero chunks, returns a single object instead of a list:
          {"message": str} explaining why -- check for a "message" key, not list
          length, to tell the two shapes apart.
        Raises: 404 unknown project. Validation error for a bad scope (absolute,
          '..', outside project root) or >20 scopes -- names the scope, never a
          host path. Per-hit read failures set `warning` (partial success), not an exception.

        Do NOT use to read a known file -- call read_project_artifacts instead.
        Do NOT pass a file path as a scope -- scopes are directories.
        """
        return await artifacts_ops.semantic_search(project, query, limit, scopes)

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
        return await artifacts_ops.read_project_artifacts(project, reads)

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
        return await artifacts_ops.save_project_artifacts(project, updates)

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
        return await artifacts_ops.list_project_artifacts(project, path, recursive)

    @mcp.tool()
    @mcp_error_handler
    async def move_project_artifact(
        project: Annotated[str, Field(description="Project name")],
        src_path: Annotated[str, Field(description="Source path")],
        dest_path: Annotated[str, Field(description="Destination path")],
    ) -> str | dict[str, Any]:
        """[ARTIFACT TOOLS] Moves or renames an artifact."""
        return await artifacts_ops.move_project_artifact(project, src_path, dest_path)

    @mcp.tool()
    @mcp_error_handler
    async def delete_project_artifact(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to delete")],
    ) -> str | dict[str, Any]:
        """[ARTIFACT TOOLS] Deletes a single artifact file by moving it to the
        recycle bin. The file is preserved in the recycle bin and can be restored
        using restore_project_artifact if needed.

        Do NOT use to move or rename a file — call move_project_artifact instead.

        Returns: confirmation string with the deleted file path.
        Raises:  404 error if the path does not exist in artifact storage.
        """
        return await artifacts_ops.delete_project_artifact(project, path)

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
        return await artifacts_ops.search_project_artifacts(project, query)

    @mcp.tool()
    @mcp_error_handler
    async def get_project_artifact_outline(
        project: Annotated[str, Field(description="Project name")],
        path: Annotated[str, Field(description="Path to .md file")],
    ) -> str | dict[str, Any]:
        """[ARTIFACT TOOLS] Extracts table of contents."""
        return await artifacts_ops.get_project_artifact_outline(project, path)
