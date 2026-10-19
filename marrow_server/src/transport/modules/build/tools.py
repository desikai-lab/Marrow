import asyncio
from typing import Annotated, Any

import config
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from tools import run_project_build_logic
from utils.error_middleware import mcp_error_handler


def use_build_tools(mcp: FastMCP) -> None:
    """Register the build tools on `mcp`; a no-op when TOOL_GROUP_BUILD_ENABLED=false."""
    if not config.BUILD_ENABLED:
        return

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
