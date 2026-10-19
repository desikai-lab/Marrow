from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from operations import artifacts as artifacts_ops
from pydantic import Field
from utils.error_middleware import mcp_error_handler


def use_history_tools(mcp: FastMCP) -> None:
    """Register the history tools on `mcp`."""

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
        return await artifacts_ops.list_artifact_history(project, path)

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
        return await artifacts_ops.restore_project_artifact(project, path, backup_name)
