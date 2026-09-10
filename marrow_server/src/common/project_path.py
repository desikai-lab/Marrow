import logging

from .file_accessor import Accessor, FileAccessor
from .project_file_error import ProjectFileError

log = logging.getLogger(__name__)

_DEFAULT_ACCESSOR = FileAccessor()


class ProjectPath:
    """Immutable reference to a project-relative file. absolute_path is
    never exposed via any accessor — read()/write() are the only ways to
    touch the file, and neither returns the absolute path.

    Construction is resolver-only by convention (see path_resolver.py);
    enforced via the lint rule in Architecture §3, not by the language
    (Python has no true `internal`)."""

    __slots__ = (
        "relative_path",
        "__absolute_path",
        "__writable",
        "__encoding",
        "__errors",
        "__write_newline",
        "__read_newline",
    )

    def __init__(
        self,
        relative_path: str,
        absolute_path: str,
        *,
        writable: bool = True,
        encoding: str = "utf-8",
        errors: str = "strict",
        write_newline: str | None = None,
        read_newline: str | None = None,
    ):
        self.relative_path = relative_path
        self.__absolute_path = absolute_path
        self.__writable = writable
        self.__encoding = encoding
        self.__errors = errors
        self.__write_newline = write_newline
        self.__read_newline = read_newline
    def as_accessor_source(self) -> str:
        """Returns the absolute path for use ONLY as the source argument to a bare
        Accessor call when the destination is a non-project resource (e.g. a build
        output directory) that cannot itself be represented as a ProjectPath."""
        return self.__absolute_path

    def read(self, accessor: Accessor | None = None) -> str:
        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            return accessor.read(
                self.__absolute_path,
                encoding=self.__encoding,
                errors=self.__errors,
                newline=self.__read_newline,
            )
        except Exception as ex:
            log.error("ProjectPath.read failed for %s", self.relative_path, exc_info=ex)
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def write(self, content: str, accessor: Accessor | None = None) -> None:
        if not self.__writable:
            log.error("Rejected write() on read-only ProjectPath: %s", self.relative_path)
            raise ProjectFileError(self.relative_path)

        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            accessor.write(
                self.__absolute_path,
                content,
                encoding=self.__encoding,
                newline=self.__write_newline,
            )
        except Exception as ex:
            log.error("ProjectPath.write failed for %s", self.relative_path, exc_info=ex)
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def exists(self, accessor: Accessor | None = None) -> bool:
        accessor = accessor or _DEFAULT_ACCESSOR
        return accessor.exists(self.__absolute_path)

    def copy(self, destination: "ProjectPath", accessor: Accessor | None = None) -> None:
        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            accessor.copy(self.__absolute_path, destination.__absolute_path)
        except Exception as ex:
            log.error(
                "ProjectPath.copy failed from %s to %s",
                self.relative_path,
                destination.relative_path,
                exc_info=ex,
            )
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def move(self, destination: "ProjectPath", accessor: Accessor | None = None) -> None:
        if not self.__writable:
            log.error("Rejected move() on read-only ProjectPath: %s", self.relative_path)
            raise ProjectFileError(self.relative_path)

        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            accessor.move(self.__absolute_path, destination.__absolute_path)
        except Exception as ex:
            log.error(
                "ProjectPath.move failed from %s to %s",
                self.relative_path,
                destination.relative_path,
                exc_info=ex,
            )
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def delete(self, accessor: Accessor | None = None) -> None:
        if not self.__writable:
            log.error("Rejected delete() on read-only ProjectPath: %s", self.relative_path)
            raise ProjectFileError(self.relative_path)

        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            accessor.delete(self.__absolute_path)
        except Exception as ex:
            log.error("ProjectPath.delete failed for %s", self.relative_path, exc_info=ex)
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def touch(self, accessor: Accessor | None = None) -> None:
        if not self.__writable:
            log.error("Rejected touch() on read-only ProjectPath: %s", self.relative_path)
            raise ProjectFileError(self.relative_path)

        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            accessor.touch(self.__absolute_path)
        except Exception as ex:
            log.error("ProjectPath.touch failed for %s", self.relative_path, exc_info=ex)
            failed = True

        if failed:
            raise ProjectFileError(self.relative_path)

    def read_lines(self, accessor: Accessor | None = None):
        accessor = accessor or _DEFAULT_ACCESSOR
        try:
            yield from accessor.read_lines(
                self.__absolute_path, encoding=self.__encoding, errors=self.__errors
            )
        except Exception as ex:
            log.error("ProjectPath.read_lines failed for %s", self.relative_path, exc_info=ex)
            raise ProjectFileError(self.relative_path) from None

    # Async primitive twins (ADR-0045)
    async def read_async(self, accessor: Accessor | None = None) -> str:
        import asyncio

        return await asyncio.to_thread(self.read, accessor)

    async def write_async(self, content: str, accessor: Accessor | None = None) -> None:
        import asyncio

        await asyncio.to_thread(self.write, content, accessor)

    async def exists_async(self, accessor: Accessor | None = None) -> bool:
        import asyncio

        return await asyncio.to_thread(self.exists, accessor)

    async def copy_async(
        self, destination: "ProjectPath", accessor: Accessor | None = None
    ) -> None:
        import asyncio

        await asyncio.to_thread(self.copy, destination, accessor)

    async def move_async(
        self, destination: "ProjectPath", accessor: Accessor | None = None
    ) -> None:
        import asyncio

        await asyncio.to_thread(self.move, destination, accessor)

    async def delete_async(self, accessor: Accessor | None = None) -> None:
        import asyncio

        await asyncio.to_thread(self.delete, accessor)

    async def touch_async(self, accessor: Accessor | None = None) -> None:
        import asyncio

        await asyncio.to_thread(self.touch, accessor)
