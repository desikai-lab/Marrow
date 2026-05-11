import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging(log_file: str = "logs/server.log", level: int = logging.INFO) -> None:
    """
    Configures the root logger to output to both the console and a daily rotating log file.
    Files rotate at midnight; each past day is kept as <base>.YYYY-MM-DD (30 days retained).
    The minimum log level is controlled by the `level` parameter (read from LOG_LEVEL env-var
    by the caller).
    """
    # Ensure logs directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to avoid duplicates on re-init
    if root.hasHandlers():
        root.handlers.clear()

    # Formatter: [Timestamp] [LoggerName] [Level] Message
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Daily Rotating File Handler (rotates at midnight, keeps 30 days)
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=30, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.info(
        "Logging initialized. File target: %s | Level: %s", log_file, logging.getLevelName(level)
    )
