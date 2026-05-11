import logging
from dataclasses import dataclass
from pathlib import Path

from config import PROJECTS_ROOT

logger = logging.getLogger(__name__)

# Module-level session cache: keyed by project name
_settings_cache: dict[str, "ProjectSettings"] = {}


@dataclass
class ProjectSettings:
    source_root: Path | None = None
    source_tools_available: bool = False


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
        _settings_cache[project] = settings
        return settings

    raw = _parse_settings_file(settings_path)
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
