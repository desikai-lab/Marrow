from config import check_startup_config
from app import app
from utils.logger_setup import setup_logging
import uvicorn
import os
import logging

# Ensure UTF-8 for console output on Windows
if os.name == 'nt':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if __name__ == "__main__":
    # Initialize persistent file logging
    _log_level = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO").upper())
    if not isinstance(_log_level, int):
        _log_level = logging.INFO
    setup_logging(level=_log_level)
    
    # Check config before running
    check_startup_config()
    uvicorn.run(app, host="127.0.0.1", port=8000, proxy_headers=True, forwarded_allow_ips="*")
