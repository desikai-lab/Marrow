from common.file_accessor import FileAccessor


def test_write_missing_parent_directory_creates_parents_and_writes_file(tmp_path):
    target = tmp_path / "a" / "b" / "c.txt"
    FileAccessor.write(str(target), "hello world")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello world"


def test_write_existing_parent_directory_writes_file_without_error(tmp_path):
    target = tmp_path / "c.txt"
    FileAccessor.write(str(target), "hello standard")
    assert FileAccessor.read(str(target)) == "hello standard"


def test_read_existing_file_returns_content(tmp_path):
    target = tmp_path / "read_test.txt"
    target.write_text("sample content", encoding="utf-8")
    assert FileAccessor.read(str(target)) == "sample content"


def test_exists_missing_file_returns_false(tmp_path):
    target = tmp_path / "nonexistent.txt"
    assert FileAccessor.exists(str(target)) is False


def test_exists_existing_file_returns_true(tmp_path):
    target = tmp_path / "existent.txt"
    target.write_text("data", encoding="utf-8")
    assert FileAccessor.exists(str(target)) is True


def test_write_custom_encoding_and_newline_preserves_bytes_exactly(tmp_path):
    target = tmp_path / "binary_exact.txt"
    content = "Line1\r\nLine2\r\n"
    FileAccessor.write(str(target), content, encoding="utf-8", newline="")
    with open(target, "rb") as f:
        raw_bytes = f.read()
    assert raw_bytes == b"Line1\r\nLine2\r\n"
