import re
from typing import Tuple, Optional, List

def extract_markdown_section(content: str, section_header: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Searches for a Markdown section by its header.
    Returns (section_text_with_header, start_index, end_index).
    """
    clean_header = section_header.lstrip("#").strip()
    # B29++: Make whitespace matching flexible (supports NBSP etc.)
    header_regex = re.escape(clean_header).replace(r"\ ", r"\s+").replace(r" ", r"\s+")
    header_pattern = re.compile(rf"^(#+)\s*{header_regex}\s*$", re.MULTILINE | re.IGNORECASE)
    
    match = header_pattern.search(content)
    if not match:
        return None, None, None
    
    level = len(match.group(1))
    start_pos = match.start()
    
    # Search for the next header at the same or higher level
    next_header_pattern = re.compile(rf"^#{{1,{level}}}\s+", re.MULTILINE)
    next_match = next_header_pattern.search(content, match.end())
    
    end_pos = next_match.start() if next_match else len(content)
    
    section_content = content[start_pos:end_pos].strip("\n")
    return section_content, start_pos, end_pos

def find_all_sections(content: str, section_header: str) -> List[Tuple[int, int]]:
    """Finds all occurrences of a section by header. Returns a list of (start, end) ranges."""
    clean_header = section_header.lstrip("#").strip()
    header_regex = re.escape(clean_header).replace(r"\ ", r"\s+").replace(r" ", r"\s+")
    header_pattern = re.compile(rf"^(#+)\s*{header_regex}\s*$", re.MULTILINE | re.IGNORECASE)
    
    ranges = []
    for match in header_pattern.finditer(content):
        level = len(match.group(1))
        start_pos = match.start()
        
        # Search for the next header at the same or higher level
        next_header_pattern = re.compile(rf"^#{{1,{level}}}\s+", re.MULTILINE)
        next_match = next_header_pattern.search(content, match.end())
        
        end_pos = next_match.start() if next_match else len(content)
        ranges.append((start_pos, end_pos))
        
    return ranges

def update_markdown_table_row(content: str, row_identifier: str, cell_updates: dict) -> str:
    """
    Finds a table row by identifier (e.g. '| T35 |') and updates its cells.
    cell_updates: dict mapping {column_index_1_based: "new value"}.
    """
    row_pattern = re.compile(rf"^\s*\|\s*{re.escape(row_identifier.strip('|').strip())}\s*\|.*$", re.MULTILINE | re.IGNORECASE)
    
    match = row_pattern.search(content)
    if not match:
        return content
    
    line = match.group(0)
    parts = [p.strip() for p in line.split("|")]
    
    for idx, new_val in cell_updates.items():
        if 0 <= idx < len(parts):
            parts[idx] = str(new_val)
            
    new_line = "| " + " | ".join(parts[1:-1]) + " |"
    return content[:match.start()] + new_line + content[match.end():]

def insert_text_at_marker(content: str, marker: str, text: str, mode: str = "before") -> str:
    """Inserts text before or after a marker (e.g. '<!-- TASKS_END -->')."""
    if marker not in content:
        return content + "\n" + text
    
    if mode == "before":
        return content.replace(marker, text + marker)
    return content.replace(marker, marker + text)

def extract_metadata_value(content: str, label: str) -> Optional[str]:
    """Finds a Label: Value in the content, accounting for possible prefixes (blockquotes, bold)."""
    # Regex matches the label even when embedded inside markdown markup (> 📌 **Label: Value**)
    match = re.search(rf"^[^\r\n]*?{re.escape(label)}\s*:\s*(.*)$", content, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().strip("*") if match else None

def update_metadata_value(content: str, label: str, new_value: str) -> str:
    """Updates a numeric Label: Value in the content, preserving the line's prefix and suffix."""
    # Replace only the digits after the label to preserve any surrounding markup (e.g. **Label: 123**)
    pattern = re.compile(rf"(^[^\r\n]*?{re.escape(label)}\s*:\s*)(\d+)", re.MULTILINE | re.IGNORECASE)
    if pattern.search(content):
        return pattern.sub(rf"\g<1>{new_value}", content)
    
    # Fallback for non-numeric values (legacy behaviour)
    pattern_fallback = re.compile(rf"(^[^\r\n]*?{re.escape(label)}\s*:\s*)(.*)$", re.MULTILINE | re.IGNORECASE)
    return pattern_fallback.sub(rf"\g<1>{new_value}", content)

def clean_section_name(name: str) -> str:
    """Strips leading # characters and whitespace from a section title."""
    return name.lstrip("#").strip()

def strip_duplicated_header(content: str, clean_name: str) -> str:
    """
    Removes a leading header from content if it matches clean_name.
    """
    clean_content = content.lstrip()
    header_regex = re.escape(clean_name).replace(r"\ ", r"\s+").replace(r" ", r"\s+")
    header_pattern = re.compile(rf"^(#+)\s*{header_regex}\s*$", re.MULTILINE | re.IGNORECASE)
    
    match = header_pattern.match(clean_content)
    if match:
        remaining = clean_content[match.end():].lstrip("\n")
        return remaining
    return content

def get_markdown_lines(content: str, start_line: int, end_line: int) -> str:
    """
    Extracts a line range from text (1-indexed).
    """
    lines = content.splitlines()
    # Adjust indices (1-based -> 0-based)
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    
    return "\n".join(lines[start_idx:end_idx])
