from typing import Annotated

from mcp.server.fastmcp import FastMCP
from operations import context as context_ops
from pydantic import Field
from utils.error_middleware import mcp_error_handler


def use_session_tools(mcp: FastMCP) -> None:
    """Register the session tools on `mcp`."""

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
        return await context_ops.get_session_context(project, start_role)

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
        return await context_ops.get_guideline(project, role)
