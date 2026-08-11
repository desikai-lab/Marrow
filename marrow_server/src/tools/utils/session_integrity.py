import logging
import os
import re
from datetime import date

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

_NEXT_AGENT_ROLE_RE = re.compile(r"^\*\*next_agent_role:\*\*\s*(.+?)\s*$", re.MULTILINE)
_CURRENT_TASK_RE = re.compile(r"^\*\*Current Task:\*\*.*$", re.MULTILINE)
_HANDOVER_NOTE_RE = re.compile(r"^## Handover Note\n(.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)


class SessionMdIntegrityHook(IntegrityHook):
    async def validate_and_repair(
        self, project: str, rel_path: str, content: str, mode: str, **kwargs
    ) -> str:
        if mode == "patch":
            old_str = kwargs.get("old_str", "")
            await self._maybe_append_history(project, rel_path, old_str, content)
            return content

        if mode != "replace_file":
            return content

        await self._maybe_append_history(project, rel_path, "", content)

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
        return content

    async def _maybe_append_history(
        self, project: str, rel_path: str, old_str: str, new_content: str
    ) -> None:
        """Stateless, per-call check: if next_agent_role differs between the OLD live
        session.md content and the NEW content being written, mechanically extract
        Current Task + Handover Note and prepend an entry to sessions/history.md.
        Never raises -- any failure is logged and swallowed (REQ-03).
        """
        try:
            target_path = validate_artifact_path(project, rel_path)
        except ValueError:
            return
        if not os.path.exists(target_path):
            return  # REQ-04: first-ever write

        try:
            with open(target_path, encoding="utf-8-sig", errors="replace", newline="") as f:
                old_content = f.read()
        except OSError:
            return

        if not old_content:
            return  # REQ-04

        old_role = self._extract_next_agent_role(old_content)
        new_role = self._extract_next_agent_role(new_content)
        if old_role is None or new_role is None or old_role == new_role:
            return  # HARD STOP save or unparseable content: no-op

        entry = self._build_history_entry(old_content, old_role, new_role)
        if entry is None:
            return

        try:
            from services.artifact_command_service import save_project_artifacts_logic

            history_path = validate_artifact_path(project, "sessions/history.md")
            existing_first_line = ""
            if os.path.exists(history_path):
                with open(history_path, encoding="utf-8-sig", errors="replace", newline="") as f:
                    existing_first_line = f.read()

            await save_project_artifacts_logic(
                project,
                [
                    {
                        "path": "sessions/history.md",
                        "mode": "patch",
                        "old_str": existing_first_line,
                        "content": entry + "\n\n" + existing_first_line,
                    }
                ],
            )
        except Exception as e:
            logger.warning(
                "Failed to append history entry for project '%s' on genuine role "
                "transition (%s -> %s): %s",
                project,
                old_role,
                new_role,
                e,
            )

    def _extract_next_agent_role(self, content: str) -> str | None:
        match = _NEXT_AGENT_ROLE_RE.search(content)
        return match.group(1) if match else None

    def _build_history_entry(
        self, old_content: str, old_role: str, new_role: str
    ) -> str | None:
        task_match = _CURRENT_TASK_RE.search(old_content)
        handover_match = _HANDOVER_NOTE_RE.search(old_content)
        if not task_match and not handover_match:
            return None

        # --- heading: ## Date — Task Title ---
        today = date.today().isoformat()  # e.g. "2026-08-11"
        if task_match:
            # **Current Task:** F4000189 — Some Title  →  extract "F4000189 — Some Title"
            raw = task_match.group(0)  # full line
            task_title = re.sub(r"^\*\*Current Task:\*\*\s*", "", raw).strip()
        else:
            task_title = "Session Handoff"
        heading = f"## {today} — {task_title}"

        lines = [heading]
        lines.append(f"**next_agent_role:** {old_role}")
        if handover_match:
            lines.append("")
            lines.append("## Handover Note")
            lines.append(handover_match.group(1).strip())
        return "\n".join(lines)

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
