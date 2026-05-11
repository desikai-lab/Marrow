import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import os

from tools.utils.project_settings import get_source_root, _settings_cache
from tools.source import (
    view_file_source_logic, 
    _check_traversal, 
    _check_sandbox, 
    _is_binary,
    MAX_FILE_SIZE_BYTES
)
from utils.exceptions import (
    InvalidPathError,
    ValidationError,
    ArtifactNotFoundError,
    SourceFileError
)

class TestSourceTool(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for PROJECTS_ROOT
        self.test_dir = Path(tempfile.mkdtemp())
        self.projects_root = self.test_dir / "projects"
        self.projects_root.mkdir()
        
        self.project_name = "test_project"
        self.project_path = self.projects_root / self.project_name
        self.project_path.mkdir()
        
        # Patch PROJECTS_ROOT in project_settings
        self.patcher = patch("tools.utils.project_settings.PROJECTS_ROOT", str(self.projects_root))
        self.patcher.start()
        
        # Clear cache before each test
        _settings_cache.clear()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)

    # --- Step 2: Settings Parser Tests ---

    def test_get_source_root_no_settings_file_returns_none(self):
        """get_source_root returns None when .settings is absent."""
        self.assertIsNone(get_source_root(self.project_name))

    def test_get_source_root_valid_settings_returns_resolved_path(self):
        """get_source_root returns resolved Path when SOURCE_ROOT is valid."""
        source_dir = self.test_dir / "actual_source"
        source_dir.mkdir()
        
        settings_file = self.project_path / ".settings"
        settings_file.write_text(f"SOURCE_ROOT={source_dir}\n")
        
        root = get_source_root(self.project_name)
        self.assertEqual(root, source_dir.resolve())

    def test_get_source_root_nonexistent_path_returns_none(self):
        """get_source_root returns None when SOURCE_ROOT path does not exist."""
        settings_file = self.project_path / ".settings"
        settings_file.write_text("SOURCE_ROOT=/non/existent/path\n")
        
        self.assertIsNone(get_source_root(self.project_name))

    def test_get_source_root_second_call_uses_cache(self):
        """Second call to get_source_root uses cache."""
        source_dir = self.test_dir / "actual_source"
        source_dir.mkdir()
        settings_file = self.project_path / ".settings"
        settings_file.write_text(f"SOURCE_ROOT={source_dir}\n")
        
        # First call
        get_source_root(self.project_name)
        
        # Delete the file - if cache works, it should still return the root
        settings_file.unlink()
        
        self.assertEqual(get_source_root(self.project_name), source_dir.resolve())

    # --- Step 3: Scalpel Logic Tests ---

    def test_check_traversal_dotdot_path_raises_invalid_path_error(self):
        """_check_traversal raises InvalidPathError for unsafe paths."""
        with self.assertRaises(InvalidPathError):
            _check_traversal("../etc/passwd")
        with self.assertRaises(InvalidPathError):
            _check_traversal("src/../../etc/passwd")
        with self.assertRaises(InvalidPathError):
            _check_traversal("..\\win.ini")

    def test_check_traversal_safe_path_does_not_raise(self):
        """_check_traversal allows safe paths."""
        _check_traversal("src/main.py")
        _check_traversal("README.md")

    def test_check_sandbox_path_outside_root_raises_invalid_path_error(self):
        """_check_sandbox raises InvalidPathError for paths outside root."""
        source_root = self.test_dir / "source"
        source_root.mkdir()
        outside_path = self.test_dir / "outside.txt"
        
        with self.assertRaises(InvalidPathError):
            _check_sandbox(outside_path, source_root)

    def test_view_file_source_logic_no_source_access_returns_error_message(self):
        """view_file_source_logic returns error message if source access is disabled."""
        res = view_file_source_logic(self.project_name, "test.py", 1, 10)
        self.assertEqual(res, "Project does not provide access to code files.")

    def test_view_file_source_logic_invalid_line_numbers_raises_validation_error(self):
        """view_file_source_logic validates line numbers."""
        # Setup source
        source_dir = self.test_dir / "source"
        source_dir.mkdir()
        (self.project_path / ".settings").write_text(f"SOURCE_ROOT={source_dir}\n")
        
        with self.assertRaises(ValidationError):
            view_file_source_logic(self.project_name, "test.py", 0, 10)
        with self.assertRaises(ValidationError):
            view_file_source_logic(self.project_name, "test.py", 10, 5)

    def test_view_file_source_logic_missing_file_raises_artifact_not_found_error(self):
        """view_file_source_logic raises ArtifactNotFoundError if file missing."""
        source_dir = self.test_dir / "source"
        source_dir.mkdir()
        (self.project_path / ".settings").write_text(f"SOURCE_ROOT={source_dir}\n")
        
        with self.assertRaises(ArtifactNotFoundError):
            view_file_source_logic(self.project_name, "missing.py", 1, 10)

    def test_is_binary_null_bytes_detected_returns_true(self):
        """_is_binary detects null bytes."""
        bin_file = self.test_dir / "bin"
        bin_file.write_bytes(b"hello\x00world")
        self.assertTrue(_is_binary(bin_file))
        
        txt_file = self.test_dir / "txt"
        txt_file.write_text("hello world")
        self.assertFalse(_is_binary(txt_file))

    def test_view_file_source_logic_file_over_limit_raises_source_file_error(self):
        """view_file_source_logic rejects files over 3 MB."""
        source_dir = self.test_dir / "source"
        source_dir.mkdir()
        (self.project_path / ".settings").write_text(f"SOURCE_ROOT={source_dir}\n")
        
        large_file = source_dir / "large.txt"
        with open(large_file, "wb") as f:
            f.seek(MAX_FILE_SIZE_BYTES + 1)
            f.write(b"0")
            
        with self.assertRaises(SourceFileError):
            view_file_source_logic(self.project_name, "large.txt", 1, 10)

    def test_view_file_source_logic_valid_range_returns_content_with_header(self):
        """view_file_source_logic reads correct line ranges."""
        source_dir = self.test_dir / "source"
        source_dir.mkdir()
        (self.project_path / ".settings").write_text(f"SOURCE_ROOT={source_dir}\n")
        
        src_file = source_dir / "app.py"
        src_file.write_text("line1\nline2\nline3\nline4\nline5\n")
        
        # Mid-range
        res = view_file_source_logic(self.project_name, "app.py", 2, 4)
        self.assertIn("line2\nline3\nline4", res)
        self.assertIn("Lines 2–4", res)
        
        # Beyond EOF
        res = view_file_source_logic(self.project_name, "app.py", 4, 10)
        self.assertIn("line4\nline5", res)
        self.assertNotIn("line6", res)
        
        # Empty range
        res = view_file_source_logic(self.project_name, "app.py", 10, 20)
        self.assertIn("(No content in requested range.)", res)

if __name__ == "__main__":
    unittest.main()
