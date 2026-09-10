from common.project_file_error import ProjectFileError


def test_ProjectFileError_relative_path_only_str_does_not_contain_absolute_segment():
    rel_path = "docs/spec.md"
    err = ProjectFileError(rel_path)
    assert err.relative_path == rel_path
    assert "File operation failed: docs/spec.md" in str(err)
    assert "/etc/" not in str(err)
    assert "C:\\" not in str(err)
    assert err.args == (f"File operation failed: {rel_path}",)
