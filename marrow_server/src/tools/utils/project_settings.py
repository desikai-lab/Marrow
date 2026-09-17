import logging
from dataclasses import dataclass
from pathlib import Path

from config import DEFAULT_CHUNK_OVERLAP_PCT, PROJECTS_ROOT  # noqa: F401

logger = logging.getLogger(__name__)

# Module-level session cache: keyed by project name
_settings_cache: dict[str, "ProjectSettings"] = {}


@dataclass
class ProjectSettings:
    source_root: Path | None = None
    source_tools_available: bool = False
    chunk_overlap_pct: float | None = None


def _parse_settings_file(settings_path: Path) -> dict[str, str]:
    """
    Parse a .settings file into a raw key->value dict.
    Skips blank lines and lines starting with '#'.
    Splits on the first '=' only.
    """
    result: dict[str, str] = {}
    try:
        for line in settings_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    except Exception as exc:
        logger.warning("Failed to read .settings file at %s: %s", settings_path, exc)
    return result


def _parse_overlap_pct(raw_value: str | None) -> float | None:
    """Parses and range-validates CHUNK_OVERLAP_PCT. Returns None (caller falls
    back to config.DEFAULT_CHUNK_OVERLAP_PCT) if missing, non-numeric, or
    outside [0, 0.5)."""
    if raw_value is None or not raw_value.strip():
        return None
    try:
        pct = float(raw_value)
    except ValueError:
        logger.warning("Invalid CHUNK_OVERLAP_PCT %r: not a number, using default.", raw_value)
        return None
    if not (0 <= pct < 0.5):
        logger.warning("CHUNK_OVERLAP_PCT %r out of range [0, 0.5), using default.", raw_value)
        return None
    return pct


def load_project_settings(project: str) -> ProjectSettings:
    """
    Load and cache settings for a project.
    Locates PROJECTS_ROOT/project/.settings, parses SOURCE_ROOT,
    resolves and validates the path. Results are cached for the session.
    """
    if project in _settings_cache:
        return _settings_cache[project]

    settings = ProjectSettings()
    settings_path = Path(PROJECTS_ROOT) / project / ".settings"

    if not settings_path.exists():
        logger.debug(
            "No .settings file found for project '%s' — source tools unavailable.", project
        )
        settings.chunk_overlap_pct = _parse_overlap_pct(None)
        _settings_cache[project] = settings
        return settings

    raw = _parse_settings_file(settings_path)
    settings.chunk_overlap_pct = _parse_overlap_pct(raw.get("CHUNK_OVERLAP_PCT"))
    raw_root = raw.get("SOURCE_ROOT", "").strip()

    if not raw_root:
        logger.debug(".settings exists for project '%s' but SOURCE_ROOT is not set.", project)
        _settings_cache[project] = settings
        return settings

    resolved = Path(raw_root).resolve()
    if not resolved.exists() or not resolved.is_dir():
        logger.critical(
            "SOURCE_ROOT '%s' for project '%s' does not exist or is not a directory. "
            "Source tools disabled.",
            resolved,
            project,
        )
        _settings_cache[project] = settings
        return settings

    settings.source_root = resolved
    settings.source_tools_available = True
    logger.info("SOURCE_ROOT for project '%s' resolved to: %s", project, resolved)
    _settings_cache[project] = settings
    return settings



def get_source_root(project: str) -> Path | None:
    """
    Public API. Returns the validated SOURCE_ROOT Path for the project,
    or None if not configured or invalid.
    """
    return load_project_settings(project).source_root
