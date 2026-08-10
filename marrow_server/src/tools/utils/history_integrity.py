import os

from utils.exceptions import ValidationError

from tools.utils.artifact_integrity_hooks import ArtifactIntegrityRegistry, IntegrityHook
from tools.utils.filesystem_utils import validate_artifact_path


class HistoryMdIntegrityHook(IntegrityHook):
    """Enforces that sessions/history.md can only ever be modified at
    the very start of the file (position 0). This preserves the file's
    existing reverse-chronological (newest-first) convention and guarantees
    past entries can never be silently edited, truncated, or overwritten.

    Allowed:
      - mode='patch' where old_str exactly matches the current start of the
        file (a true prepend). If the file does not exist yet, it is created
        empty by this hook and an empty old_str is accepted for the very
        first entry -- callers never need a separate creation step.
    Rejected (ValidationError): everything else, including 'replace_file'
    (unconditionally -- never permitted, even for a brand-new file),
    'append_section' (would land at the wrong end), 'replace_section' and
    'delete_section' (history entries are immutable).
    """

    async def validate_and_repair(
        self, project: str, rel_path: str, content: str, mode: str, **kwargs
    ) -> str:
        target_path = validate_artifact_path(project, rel_path)

        if mode == "patch":
            return self._validate_patch(target_path, rel_path, kwargs.get("old_str", ""), content)

        if mode == "replace_file":
            raise ValidationError(
                f"mode 'replace_file' is never permitted for '{rel_path}' -- it is a "
                "prepend-only log and the file is created automatically on first patch. "
                "Use mode='patch'."
            )

        raise ValidationError(
            f"mode '{mode}' is not permitted for '{rel_path}' -- only 'patch' (to prepend "
            "a new entry) is allowed."
        )

    def _validate_patch(self, target_path: str, rel_path: str, old_str: str, content: str) -> str:
        if not os.path.exists(target_path):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            open(target_path, "w", encoding="utf-8-sig").close()

        with open(target_path, encoding="utf-8-sig", errors="replace") as f:
            existing = f.read()

        if existing == "":
            # Freshly created / genuinely empty file: nothing to anchor
            # against yet, so the first entry is accepted verbatim if old_str is empty.
            if old_str:
                raise ValidationError(
                    f"'{rel_path}' does not exist or is empty, but a non-empty 'old_str' was "
                    "provided. The first entry in history must have an empty 'old_str'."
                )
            return content

        if not old_str or not existing.startswith(old_str):
            raise ValidationError(
                f"'{rel_path}' only allows edits anchored at the very start of the file "
                "(prepend-only log, newest entry first). 'old_str' must exactly match the "
                "current first line(s) of the file -- read the top of the file first, then "
                "patch old_str -> new_entry + '\\n\\n' + old_str."
            )
        return content


# Self-registers on import.
ArtifactIntegrityRegistry.register("history.md", HistoryMdIntegrityHook())
