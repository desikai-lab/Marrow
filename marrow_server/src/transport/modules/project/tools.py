import asyncio
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from tools import list_projects_logic
from utils.error_middleware import mcp_error_handler


def use_project_tools(mcp: FastMCP) -> None:
    """Register the project tools on `mcp`."""

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

        Returns: { project, files_created, starting_role } where files_created lists
                 every file path copied into the new workspace (relative to workspace root)
                 and starting_role is Discovery Agent or Init Agent.

        Raises: ValidationError if project already exists or template is unsupported.
        """
        from tools.projects import init_project_logic

        result = await asyncio.to_thread(init_project_logic, project, template)
        return result.model_dump()  # returns { project, files_created, starting_role }
