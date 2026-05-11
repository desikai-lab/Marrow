import os
import sys  # Import sys here

from config import check_startup_config
from mcp_core import mcp

# Ensure UTF-8 for console
if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if __name__ == "__main__":
    # Check project structure
    # Temporarily redirect stdout to stderr during startup check to avoid protocol interference
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        check_startup_config()
    finally:
        sys.stdout = old_stdout
    
    print("\n" + "="*50, file=sys.stderr)    
    print("   [LocalMCP] MARROW (STDIO-MODE)", file=sys.stderr)
    print("="*50, file=sys.stderr)
    
    print("   This mode is designed to be run directly via", file=sys.stderr)
    print("   Claude Desktop or Antigravity (mcp_config.json).", file=sys.stderr)
    print("="*50 + "\n", file=sys.stderr)
    
    # Start server via stdio (standard for local MCPs)
    mcp.run()
