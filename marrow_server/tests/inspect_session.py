import io
import os
import re
import sys

# Ensure UTF-8 output for terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Decouple path: Try to find session_current.md in a project artifact directory
# Default to a relative path or environment variable
TASKS_DIR = os.getenv("TASKS_DIR", "")
project = "marrow_server"
path = os.path.join(TASKS_DIR, "projects", project, "artifacts", "memory", "session_current.md")

if not os.path.exists(path):
    print(f"File not found: {path}")
    print("Please set TASKS_DIR env variable or update the 'project' variable.")
    exit(1)

content = open(path, encoding="utf-8").read()
# Localized header (English)
section_header = "✅ Completed This Session"

clean_header = section_header.lstrip("#").strip()
# Logic matching markdown_utils.py implementation
header_regex = re.escape(clean_header).replace(r"\ ", r"\s+").replace(r" ", r"\s+")
header_pattern = re.compile(rf"^(#+)\s*{header_regex}\s*$", re.MULTILINE | re.IGNORECASE)

print(f"Generated Regex: {header_pattern.pattern}")
matches = list(header_pattern.finditer(content))

print(f"--- Found via regex: {len(matches)} ---")
for i, m in enumerate(matches, 1):
    print(f"Match {i}: Line {content[: m.start()].count('\n') + 1}")
