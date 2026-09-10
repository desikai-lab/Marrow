from dataclasses import dataclass

from common import path_resolver
from common.path_resolver import ResourceKind
from common.project_file_error import ProjectFileError
from common.project_path import ProjectPath


@dataclass(frozen=True)
class HistoryItem:
    backup_name: str
    live_path: ProjectPath


class ArtifactHistory:
    def __init__(self, project: str, rel_path: str, items: list[HistoryItem]):
        self.project = project
        self.rel_path = rel_path
        self._items = list(items)

    @property
    def items(self) -> list[HistoryItem]:
        return list(self._items)

    def latest(self) -> HistoryItem | None:
        return self._items[0] if self._items else None

    def find(self, backup_name: str) -> HistoryItem | None:
        for item in self._items:
            if item.backup_name == backup_name:
                return item
        return None

    def backup_path(self, item: HistoryItem) -> ProjectPath:
        backup_rel = path_resolver.os.path.join(
            path_resolver.NAMESPACE_ARTIFACTS, self.rel_path, item.backup_name
        )
        try:
            pp = path_resolver.get_path(self.project, backup_rel, ResourceKind.HISTORY)
        except ProjectFileError:
            raise ProjectFileError(backup_rel) from None

        # Containment check
        item_history_dir = path_resolver.get_history_raw_dir(
            self.project, self.rel_path, path_resolver.NAMESPACE_ARTIFACTS
        )
        if not path_resolver.os.path.normpath(pp._ProjectPath__absolute_path).startswith(
            path_resolver.os.path.normpath(item_history_dir) + path_resolver.os.sep
        ):
            raise ProjectFileError(backup_rel)
        return pp
