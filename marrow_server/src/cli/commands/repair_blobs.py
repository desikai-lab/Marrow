"""One-time migration: re-serialize corrupted Python-tagged YAML blobs."""

import re
from pathlib import Path

PYTHON_OBJ_BLOCK = re.compile(
    r"^([\w_]+): !!python/object/apply:[^\n]+\n- (.+)$",
    re.MULTILINE,
)


def repair_blob(path: Path) -> bool:
    """Fix one blob file. Returns True if changes were made."""
    content = path.read_text(encoding="utf-8")
    if "!!python/object/apply" not in content:
        return False
    fixed = PYTHON_OBJ_BLOCK.sub(r"\1: \2", content)
    if fixed == content:
        return False  # tag was outside frontmatter, nothing changed
    path.write_text(fixed, encoding="utf-8")
    return True


def repair_all(project_root: str) -> None:
    """Scan all blobs under project_root/.db/blobs and repair corrupted ones."""
    blobs_dir = Path(project_root) / ".db" / "blobs"
    if not blobs_dir.exists():
        print(f"Blobs directory not found: {blobs_dir}")
        return
    fixed = 0
    for blob in blobs_dir.rglob("*.md"):
        if repair_blob(blob):
            fixed += 1
            print(f"Repaired: {blob}")
    print(f"Done. {fixed} blob(s) repaired.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python repair_blobs.py <project_root>")
        sys.exit(1)
    repair_all(sys.argv[1])
