import pytest

from common.project_file_error import ProjectFileError
from common.project_path import ProjectPath


class FakeRaisingAccessor:
    def read(self, absolute_path: str, encoding: str = "utf-8", errors: str = "strict") -> str:
        raise PermissionError("/etc/shadow/secret_file")

    def write(
        self, absolute_path: str, content: str, encoding: str = "utf-8", newline: str | None = None
    ) -> None:
        raise PermissionError("/etc/shadow/secret_file")

    def exists(self, absolute_path: str) -> bool:
        return True


class FakeUnreachableAccessor:
    def read(self, absolute_path: str, encoding: str = "utf-8", errors: str = "strict") -> str:
        pytest.fail("Accessor read should not have been called")

    def write(
        self, absolute_path: str, content: str, encoding: str = "utf-8", newline: str | None = None
    ) -> None:
        pytest.fail("Accessor write should not have been called")

    def exists(self, absolute_path: str) -> bool:
        return False


class FakeMockAccessor:
    def __init__(self):
        self.exists_called = False

    def read(self, absolute_path: str, encoding: str = "utf-8", errors: str = "strict") -> str:
        return "content"

    def write(
        self, absolute_path: str, content: str, encoding: str = "utf-8", newline: str | None = None
    ) -> None:
        pass

    def exists(self, absolute_path: str) -> bool:
        self.exists_called = True
        return True


def test_read_accessor_raises_wraps_in_project_file_error_with_relative_path_only():
    pp = ProjectPath("docs/secret.md", "/var/data/projects/myproj/artifacts/docs/secret.md")
    fake = FakeRaisingAccessor()
    with pytest.raises(ProjectFileError) as exc_info:
        pp.read(accessor=fake)

    exc = exc_info.value
    assert "/etc/shadow/secret_file" not in str(exc)
    assert "/var/data/projects" not in str(exc)
    assert exc.__cause__ is None
    assert exc.__context__ is None
    assert exc.relative_path == "docs/secret.md"


def test_write_accessor_raises_wraps_in_project_file_error_with_relative_path_only():
    pp = ProjectPath("docs/secret.md", "/var/data/projects/myproj/artifacts/docs/secret.md")
    fake = FakeRaisingAccessor()
    with pytest.raises(ProjectFileError) as exc_info:
        pp.write("new content", accessor=fake)

    exc = exc_info.value
    assert "/etc/shadow/secret_file" not in str(exc)
    assert "/var/data/projects" not in str(exc)
    assert exc.__cause__ is None
    assert exc.__context__ is None
    assert exc.relative_path == "docs/secret.md"


def test_write_not_writable_raises_project_file_error_without_calling_accessor():
    pp = ProjectPath("src/main.py", "/var/data/projects/myproj/src/main.py", writable=False)
    fake = FakeUnreachableAccessor()
    with pytest.raises(ProjectFileError) as exc_info:
        pp.write("print('bad')", accessor=fake)

    assert exc_info.value.relative_path == "src/main.py"


def test_write_default_accessor_missing_parent_dir_creates_it(tmp_path):
    abs_file = tmp_path / "sub" / "nested" / "doc.md"
    pp = ProjectPath("sub/nested/doc.md", str(abs_file))
    pp.write("hello from project path")
    assert abs_file.exists()
    assert pp.read() == "hello from project path"


def test_read_write_artifacts_encoding_triple_round_trips_utf8_sig_no_newline_translation(
    tmp_path,
):
    abs_file = tmp_path / "artifact_bom.md"
    pp = ProjectPath(
        "artifact_bom.md",
        str(abs_file),
        encoding="utf-8-sig",
        errors="replace",
        write_newline="",
    )
    content = "Hello \u2764\r\nLine 2\r\n"
    pp.write(content)
    with open(abs_file, "rb") as f:
        raw_bytes = f.read()

    # UTF-8 SIG starts with UTF-8 BOM \xef\xbb\xbf and preserves raw \r\n on disk
    assert raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw_bytes
    assert pp.read() == "Hello \u2764\nLine 2\n"


def test_exists_delegates_to_accessor():
    pp = ProjectPath("file.txt", "/abs/file.txt")
    fake = FakeMockAccessor()
    assert pp.exists(accessor=fake) is True
    assert fake.exists_called is True
