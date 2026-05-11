import re
from typing import List, Optional
from tools.utils.cleaner_presets import PRESETS

class ContentCleaner:
    """
    Utility for preparing text for vectorization.
    Strips noise (ChangeLog entries, HTML comments) to improve semantic search quality.
    """
    
    @staticmethod
    def clean(content: str, use_presets: Optional[List[str]] = None) -> str:
        """Applies cleaning rules to the given text."""
        if not content:
            return ""
            
        result = content
        presets_to_apply = use_presets or ["change_log", "comments"]
        
        for preset_name in presets_to_apply:
            if preset_name in PRESETS:
                pattern = PRESETS[preset_name]
                # Use MULTILINE and DOTALL for correct handling of multi-line blocks
                result = re.sub(pattern, "", result, flags=re.MULTILINE | re.DOTALL)
                
        # Basic normalization: collapse excessive blank lines
        result = re.sub(r'\n{3,}', '\n\n', result).strip()
        
        return result
