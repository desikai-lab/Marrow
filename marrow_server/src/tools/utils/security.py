import os
import re

from config import PROJECTS_ROOT


def sanitize_error_message(message: str) -> str:
    """
    Strips sensitive information from error messages:
    - Absolute paths (replaced with [PATH])
    - Windows drive letters
    - Paths containing PROJECTS_ROOT
    """
    if not message:
        return ""

    result = message
    
    # 1. First, replace the most specific path (PROJECTS_ROOT)
    # Use normalized paths for reliable comparison
    norm_root = os.path.abspath(PROJECTS_ROOT).lower()
    norm_msg = result.lower()
    
    # If the projects root appears in the message, redact it
    if norm_root in norm_msg:
        # Preserve original casing where possible; otherwise replace directly
        # Find the index of the match case-insensitively
        idx = norm_msg.find(norm_root)
        while idx != -1:
            # Replace the corresponding slice of the original string
            original_part = result[idx:idx+len(PROJECTS_ROOT)]
            result = result.replace(original_part, "[PROJECTS_ROOT]")
            norm_msg = result.lower()
            idx = norm_msg.find(norm_root)

    # 2. Regex to detect Windows-style paths (D:\..., C:\...)
    # and Unix-style paths (/home/user/...) as a defensive fallback
    win_path_pattern = r'[a-zA-Z]:\\[^"\'\s,<>|]+'
    result = re.sub(win_path_pattern, "[PATH]", result)
    
    # 3. Additional guard: catch any remaining drive-letter slash patterns
    result = re.sub(r'[a-zA-Z]:/', "[PATH]/", result)
    
    return result

def safe_error(e: Exception, prefix: str = "Error") -> str:
    """Formats an exception into a sanitized string safe for display to the user."""
    return f"{prefix}: {sanitize_error_message(str(e))}"
