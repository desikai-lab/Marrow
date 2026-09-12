from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MigrationStepReport:
    subsystem: str
    from_version: int
    to_version: int
    moved: int = 0
    skipped: int = 0
    collisions: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MigrationReport:
    project: str
    subsystem: str
    starting_version: int
    ending_version: int
    steps: list[MigrationStepReport] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


class Migration(ABC):
    """Contract for a single ordered schema-migration step within one subsystem."""

    subsystem: str
    from_version: int
    to_version: int

    @abstractmethod
    def apply(self, project_root: str, dry_run: bool = False) -> MigrationStepReport:
        """Apply this migration step. `project_root` is an ABSOLUTE path
        (PROJECTS_ROOT/<project_name>), not a bare project name -- see
        implementation_plan.md's Handover note on why path_resolver calls
        inside apply() still work correctly with this. When dry_run=True,
        must not write to disk or bump any version -- report counts should
        reflect what WOULD be moved/skipped/collided."""
        raise NotImplementedError
