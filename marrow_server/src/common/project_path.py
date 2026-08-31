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
    ):
        self.relative_path = relative_path
        self.__absolute_path = absolute_path
        self.__writable = writable
        self.__encoding = encoding
        self.__errors = errors
        self.__write_newline = write_newline

    def read(self, accessor: Accessor | None = None) -> str:
        accessor = accessor or _DEFAULT_ACCESSOR
        failed = False
        try:
            return accessor.read(
                self.__absolute_path, encoding=self.__encoding, errors=self.__errors
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
