import asyncio
import logging
import re
from datetime import date

from common.path_resolver import NAMESPACE_ARTIFACTS, ResourceKind, get_history, get_path
from common.project_file_error import ProjectFileError
from common.project_path import ProjectPath
from tools.pipeline_base import PersistPipeline
from tools.utils.artifact_strategies import ArtifactStrategyFactory, find_unknown_fields
from tools.utils.filesystem_utils import create_artifact_backup, resolve_artifact_project_path

logger = logging.getLogger("tools.session_pipeline")

SESSION_MD_HEADER_PREFIXES = (
    "# Session State",
    "## SESSION STATE",
    "**Current Task:**",
    "**next_agent_role:**",
    "next_agent_role:",
)

_NEXT_AGENT_ROLE_RE = re.compile(r"^\*\*next_agent_role:\*\*\s*(.+?)\s*$", re.MULTILINE)
_CURRENT_TASK_RE = re.compile(r"^\*\*Current Task:\*\*.*$", re.MULTILINE)
_HEADING_LIKE_HANDOVER_RE = re.compile(r"^[\s#*]*handover\b", re.IGNORECASE)

_SESSION_STATE_BLOCK_RE = re.compile(
    r"^#{1,2}[ \t]*SESSION STATE[ \t]*$(.*?)(?=^#{1,2}[ \t]+\S|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_SESSION_HEADING_RE = re.compile(r"^#{1,2}[ \t]*session state\b", re.MULTILINE | re.IGNORECASE)


class SessionPipeline(PersistPipeline):
    """Dedicated, unconditional persist pipeline for session.md (ADR-0047).

    Every step below runs for every write, regardless of mode -- there is no
    per-mode branch, unlike the SessionMdIntegrityHook it replaces. `run()`
    is a short orchestrator over this class's private step methods.
    """

    async def run(self, ctx, path: str, group: list[tuple]) -> None:
        """Orchestrator only -- mirrors architecture.md §2.2's five numbered steps."""
        project_path = resolve_artifact_project_path(ctx.project, path)
        old_content = await self._read_old_content(ctx.project, project_path)

        final_content, applied_successfully = await self._apply_updates(
            ctx, path, group, old_content
        )
        if not applied_successfully:
            return

        final_content = self._validate_and_repair(ctx.project, final_content)

        try:
            await self._save_content(project_path, final_content)
        except Exception as e:
            for original_idx, _ in group:
                if (
                    not ctx.results[original_idx]
                    or ctx.results[original_idx].get("status") != "error"
                ):
                    ctx.results[original_idx] = {
                        "path": project_path.relative_path,
                        "status": "error",
                        "message": f"File save failed: {str(e)}",
                    }
            return

        for idx in applied_successfully:
            ctx.results[idx]["message"] += " File saved."

        await self._decide_and_append_history(ctx.project, old_content, final_content)

    async def _read_old_content(self, project: str, project_path: ProjectPath) -> str:
        """Step 1: read the live on-disk session.md once, before this request."""
        if not await project_path.exists_async():
            return ""
        old_content = await project_path.read_async()
        await asyncio.to_thread(create_artifact_backup, project, project_path)
        return old_content

    async def _apply_updates(
        self, ctx, path: str, group: list[tuple], old_content: str
    ) -> tuple[str, list[int]]:
        """Step 2: apply every update in this request in-memory, in GroupingHandler's
        existing order -- produces final_content, the fully-resolved result of the
        WHOLE request, never an intermediate state."""
        current_content = old_content
        applied_successfully: list[int] = []
        for original_idx, update in group:
            try:
                mode = update["mode"]
                strategy = ArtifactStrategyFactory.get_save_strategy(mode)
                params = update.copy()
                explicit_fields = params.pop("_explicit_fields", None)
                if explicit_fields is None:
                    explicit_fields = set(params.keys())
                new_val = params.pop("content", "")
                current_content = strategy.transform(current_content, new_val, **params)

                warning = find_unknown_fields(strategy, explicit_fields)
                result_entry = {
                    "path": path,
                    "status": "success",
                    "message": f"Applied {mode} to memory successfully.",
                }
                if warning is not None:
                    result_entry["warning"] = warning
                ctx.results[original_idx] = result_entry
                applied_successfully.append(original_idx)
            except Exception as e:
                ctx.results[original_idx] = {"path": path, "status": "error", "message": str(e)}
        return current_content, applied_successfully

    def _validate_and_repair(self, project: str, final_content: str) -> str:
        """Step 3: ONE call, after all updates are applied, never per-update."""
        if self._has_session_header(final_content):
            return final_content
        logger.warning(
            "session.md write for project '%s' is missing required header -- repairing.", project
        )
        header_block = self._extract_header_block(project, "session.md")
        return header_block + final_content if header_block else final_content

    async def _save_content(self, project_path: ProjectPath, content: str) -> None:
        """Step 4: the actual write. If this raises, step 5 never runs (caller's job)."""
        await project_path.write_async(content)

    async def _decide_and_append_history(
        self, project: str, old_content: str, new_content: str
    ) -> None:
        """Step 5: only reached by run() after _save_content succeeded."""
        if not old_content:
            return
        old_role = self._extract_next_agent_role(old_content)
        new_role = self._extract_next_agent_role(new_content)
        if old_role is None or new_role is None or old_role == new_role:
            return

        entry = self._build_history_entry(old_content, old_role, new_role)
        if entry is None:
            return

        try:
            from services.artifact_command_service import save_project_artifacts_logic

            existing_first_line = ""
            try:
                hist_pp = get_path(project, "sessions/history.md", ResourceKind.ARTIFACTS)
                if hist_pp.exists():
                    existing_first_line = hist_pp.read()
            except ProjectFileError:
                pass

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
                "Failed to append history entry for project '%s' on genuine role transition (%s -> %s): %s",
                project,
                old_role,
                new_role,
                e,
            )

    def _extract_next_agent_role(self, content: str) -> str | None:
        block_match = _SESSION_STATE_BLOCK_RE.search(content)
        scope = block_match.group(1) if block_match else content
        if block_match is None:
            logger.warning(
                "No '## SESSION STATE' block found; falling back to whole-document scan."
            )
        match = _NEXT_AGENT_ROLE_RE.search(scope)
        return match.group(1) if match else None

    def _has_session_header(self, content: str) -> bool:
        return bool(_SESSION_HEADING_RE.search(content)) and "next_agent_role:" in content

    def _extract_handover_body(self, old_content: str) -> tuple[str, bool]:
        lines = old_content.splitlines()
        heading_idx = None
        mention_idx = None
        for i, line in enumerate(lines):
            if "handover" not in line.lower():
                continue
            if heading_idx is None and _HEADING_LIKE_HANDOVER_RE.match(line):
                heading_idx = i
                break
            if mention_idx is None:
                mention_idx = i

        start_idx = heading_idx if heading_idx is not None else mention_idx

        if start_idx is not None:
            body_start = start_idx + 1
            end_idx = next(
                (j for j in range(body_start, len(lines)) if lines[j].startswith(("## ", "### "))),
                len(lines),
            )
            body = "\n".join(lines[body_start:end_idx]).strip()
            if body:
                return body, False

        fallback_start = next(
            (
                i + 1
                for i, line in enumerate(lines)
                if line.strip() in ("# Session State", "## SESSION STATE")
            ),
            0,
        )
        body = "\n".join(lines[fallback_start:]).strip()
        return body, True

    def _build_history_entry(self, old_content: str, old_role: str, new_role: str) -> str | None:
        task_match = _CURRENT_TASK_RE.search(old_content)
        handover_body, used_fallback = self._extract_handover_body(old_content)
        if not task_match and used_fallback:
            return None

        if used_fallback:
            logger.warning(
                "Could not locate handover section in session.md; falling back to whole-body handover."
            )

        today = date.today().isoformat()
        if task_match:
            raw = task_match.group(0)
            task_title = re.sub(r"^\*\*Current Task:\*\*\s*", "", raw).strip()
        else:
            task_title = "Session Handoff"
        heading = f"## {today} — {task_title}"

        lines = [heading, f"**next_agent_role:** {old_role}"]
        if handover_body:
            lines.append("")
            lines.append("### Handover Note")
            lines.append(handover_body)
        return "\n".join(lines)

    def _extract_header_block(self, project: str, rel_path: str) -> str | None:
        live_block = self._extract_from_live_file(project, rel_path)
        if live_block:
            return live_block
        return self._extract_from_history(project, rel_path)

    def _extract_from_live_file(self, project: str, rel_path: str) -> str | None:
        try:
            pp = get_path(project, rel_path, ResourceKind.ARTIFACTS)
            if not pp.exists():
                return None
            live_content = pp.read()
        except ProjectFileError as e:
            logger.warning(
                "Could not read live file '%s' during session.md repair: %s", rel_path, e
            )
            return None
        if self._has_session_header(live_content):
            lines = [
                line
                for line in live_content.splitlines()
                if line.startswith(SESSION_MD_HEADER_PREFIXES)
            ]
            if lines:
                return "\n".join(lines) + "\n\n"
        return None

    def _extract_from_history(self, project: str, rel_path: str) -> str | None:
        history = get_history(project, rel_path, NAMESPACE_ARTIFACTS)
        for item in history.items:
            try:
                backup_pp = history.backup_path(item)
            except ProjectFileError:
                logger.warning("Backup path '%s' outside item history dir", item.backup_name)
                continue
            try:
                backup_content = backup_pp.read()
            except ProjectFileError as e:
                logger.warning(
                    "Could not read backup '%s' during session.md repair: %s", item.backup_name, e
                )
                continue
            if self._has_session_header(backup_content):
                lines = [
                    line
                    for line in backup_content.splitlines()
                    if line.startswith(SESSION_MD_HEADER_PREFIXES)
                ]
                if lines:
                    return "\n".join(lines) + "\n\n"
        return None
