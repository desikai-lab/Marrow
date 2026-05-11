import logging
from pathlib import Path

from tools.utils.project_settings import get_source_root
from utils.exceptions import (
    ArtifactNotFoundError,
    InvalidPathError,
    SourceFileError,
    ValidationError,
)

logger = logging.getLogger(__name__)

BINARY_DETECTION_CHUNK = 8192  # bytes sampled for binary detection
MAX_FILE_SIZE_BYTES = 3 * 1024 * 1024  # 3 MB hard limit


def _check_traversal(path: str) -> None:
    """Reject any path containing traversal sequences before filesystem access."""
    if "../" in path or "..\\" in path or path.startswith(".."):
        logger.warning("Path traversal attempt detected in view_file_source: '%s'", path)
        raise InvalidPathError("Path traversal detected in requested path.")


def _check_sandbox(resolved: Path, source_root: Path) -> None:
    """Verify the resolved path is strictly inside source_root (symlinks already followed)."""
    try:
        resolved.relative_to(source_root)
    except ValueError:
        logger.warning(
            "Sandbox violation in view_file_source: resolved path is outside SOURCE_ROOT."
        )
        raise InvalidPathError("Requested path is outside the permitted source root.")


def _is_binary(file_path: Path) -> bool:
    """Sample the first 8 KB; return True if null bytes are present."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(BINARY_DETECTION_CHUNK)
        return b"\x00" in chunk
    except Exception:
        return False


def _read_line_range(file_path: Path, start_line: int, end_line: int) -> list[str]:
    """Read only the requested line range. Does not load the entire file into memory."""
    lines: list[str] = []
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            for current, line in enumerate(f, start=1):
                if current < start_line:
                    continue
                if current > end_line:
                    break
                lines.append(line.rstrip("\n"))
    except Exception as exc:
        logger.error("Error reading file %s: %s", file_path, exc)
        raise SourceFileError(f"Failed to read source file: {exc}")
    return lines


def view_file_source_logic(
    project: str,
    path: str,
    start_line: int,
    end_line: int,
) -> str:
    """
    Read a precise line range from the live source repository.

    Pipeline:
      1. Resolve SOURCE_ROOT (None → graceful "no access" message)
      2. Validate line numbers
      3. Traversal check
      4. Resolve absolute path + sandbox check
      5. Existence check
      6. Size + binary check
      7. Read line range
      8. Return formatted response
    """
    # 1. SOURCE_ROOT
    source_root = get_source_root(project)
    if source_root is None:
        return "Project does not provide access to code files."

    # 2. Line number validation
    if start_line < 1 or end_line < start_line:
        raise ValidationError("start_line must be >= 1 and end_line must be >= start_line.")

    # 3. Traversal check (string-level, before any Path ops)
    _check_traversal(path)

    # 4. Resolve and sandbox
    # Ensure project name isn't spoofed into the path either
    resolved = (source_root / path).resolve()
    _check_sandbox(resolved, source_root)

    # 5. Existence
    if not resolved.exists() or not resolved.is_file():
        raise ArtifactNotFoundError(f"File not found: {path}")

    # 6. Size + binary
    file_size = resolved.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES or _is_binary(resolved):
        raise SourceFileError(f"Unsupported file type: {path} (binary or exceeds 3 MB limit)")

    # 7. Read
    lines = _read_line_range(resolved, start_line, end_line)

    if not lines:
        return f"# File: {path} | Lines {start_line}–{end_line}\n\n(No content in requested range.)"

    # 8. Format response
    body = "\n".join(lines)
    return f"# File: {path} | Lines {start_line}–{end_line}\n\n{body}"
