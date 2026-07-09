import logging
import os

from tools.utils.artifact_integrity_hooks import ArtifactIntegrityRegistry, IntegrityHook
from tools.utils.filesystem_utils import (
    get_artifact_history,
    validate_artifact_path,
    validate_project_path,
)

logger = logging.getLogger(__name__)
SESSION_MD_HEADER_PREFIXES = (
    "# Session State",
    "**Current Task:**",
    "**next_agent_role:**",
    "next_agent_role:",
)


class SessionMdIntegrityHook(IntegrityHook):
    def validate_and_repair(
        self, project: str, rel_path: str, content: str, mode: str, **kwargs
    ) -> str:
        if mode != "replace_file":
            return content  # other modes (patch, replace_section, etc.) can't drop the header wholesale

        has_header = "# Session State" in content and "next_agent_role:" in content
        if has_header:
            return content

        logger.warning(
            "session.md write for project '%s' is missing required header — repairing from history.",
            project,
        )
        header_block = self._extract_header_block(project, rel_path)
        if header_block:
            return header_block + content
        # Nothing recoverable to repair from — let it persist as-is.
        # session_service.load() will raise its own clear, actionable error on next read.
        return content

    def _extract_header_block(self, project: str, rel_path: str) -> str | None:
        """Two-stage recovery: try live file first (catches the common case where only the
        incoming content is broken but the on-disk file is still intact), then fall back
        to the .history archive for when the live file was already clobbered."""
        live_block = self._extract_from_live_file(project, rel_path)
        if live_block:
            return live_block
        return self._extract_from_history(project, rel_path)

    def _extract_from_live_file(self, project: str, rel_path: str) -> str | None:
        try:
            target_path = validate_artifact_path(project, rel_path)
        except ValueError:
            return None
        if not os.path.exists(target_path):
            return None
        try:
            with open(target_path, encoding="utf-8-sig", errors="replace") as f:
                live_content = f.read()
        except OSError as e:
            logger.warning(
                "Could not read live file '%s' during session.md repair: %s", rel_path, e
            )
            return None
        if "# Session State" in live_content and "next_agent_role:" in live_content:
            lines = [
                line
                for line in live_content.splitlines()
                if line.startswith(SESSION_MD_HEADER_PREFIXES)
            ]
            if lines:
                return "\n".join(lines) + "\n\n"
        return None

    def _extract_from_history(self, project: str, rel_path: str) -> str | None:
        history = get_artifact_history(project, rel_path)
        prj_path = validate_project_path(project)
        rel_dir = os.path.dirname(rel_path)
        for h in history:
            backup_path = os.path.join(prj_path, ".history", "artifacts", rel_dir, h["backup_name"])
            try:
                with open(backup_path, encoding="utf-8-sig", errors="replace") as f:
                    backup_content = f.read()
            except OSError as e:
                logger.warning(
                    "Could not read backup '%s' during session.md repair: %s", h["backup_name"], e
                )
                continue
            if "# Session State" in backup_content and "next_agent_role:" in backup_content:
                lines = [
                    line
                    for line in backup_content.splitlines()
                    if line.startswith(SESSION_MD_HEADER_PREFIXES)
                ]
                if lines:
                    return "\n".join(lines) + "\n\n"
        return None


# Self-registers on import.
ArtifactIntegrityRegistry.register("session.md", SessionMdIntegrityHook())
