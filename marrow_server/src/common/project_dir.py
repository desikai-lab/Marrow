import logging
import os

from .file_accessor import Accessor, FileAccessor
from .project_file_error import ProjectFileError
from .project_path import ProjectPath

log = logging.getLogger(__name__)

_DEFAULT_ACCESSOR = FileAccessor()


class ProjectDir:
    """Immutable reference to a project-relative directory resource.

    `__absolute_path` is never exposed via any accessor method.
    """

    __slots__ = ("relative_path", "__absolute_path", "__writable", "__kind")

    def __init__(
        self,
        relative_path: str,
        absolute_path: str,
        *,
        writable: bool = True,
        kind: str = "artifacts",
    ):
        self.relative_path = relative_path
        self.__absolute_path = absolute_path
        self.__writable = writable
        self.__kind = kind

    def exists(self, accessor: Accessor | None = None) -> bool:
        accessor = accessor or _DEFAULT_ACCESSOR
        return accessor.exists(self.__absolute_path) and accessor.isdir(self.__absolute_path)

    def list_entries(self, accessor: Accessor | None = None) -> list[str]:
        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            return accessor.listdir(self.__absolute_path)
        except Exception as ex:
            log.error("ProjectDir.list_entries failed for %s", self.relative_path, exc_info=ex)
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def get_child_path(self, name: str) -> ProjectPath:
        if "/" in name or "\\" in name or ".." in name:
            raise ProjectFileError(os.path.join(self.relative_path, name))
        rel = (
            os.path.join(self.relative_path, name).replace("\\", "/")
            if self.relative_path
            else name
        )
        abs_p = os.path.normpath(os.path.join(self.__absolute_path, name))
        if not abs_p.startswith(self.__absolute_path):
            raise ProjectFileError(rel)
        return ProjectPath(rel, abs_p, writable=self.__writable)

    def get_child_dir(self, name: str) -> "ProjectDir":
        if "/" in name or "\\" in name or ".." in name:
            raise ProjectFileError(os.path.join(self.relative_path, name))
        rel = (
            os.path.join(self.relative_path, name).replace("\\", "/")
            if self.relative_path
            else name
        )
        abs_p = os.path.normpath(os.path.join(self.__absolute_path, name))
        if not abs_p.startswith(self.__absolute_path):
            raise ProjectFileError(rel)
        return ProjectDir(rel, abs_p, writable=self.__writable, kind=self.__kind)

    # Async primitive twins (ADR-0045)
    async def exists_async(self, accessor: Accessor | None = None) -> bool:
        import asyncio

        return await asyncio.to_thread(self.exists, accessor)

    async def list_entries_async(self, accessor: Accessor | None = None) -> list[str]:
        import asyncio

        return await asyncio.to_thread(self.list_entries, accessor)
