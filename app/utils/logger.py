# app/utils/logger.py
import logging
import sys
import json
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Any

from app.config import Config

config = Config()

class JsonFormatter(logging.Formatter):
    """Formats logs into JSON structure."""
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


class ColorFormatter(logging.Formatter):
    """Human readable & colored output (for Docker console)."""

    COLORS = {
        "DEBUG": "\033[36m",   # Cyan
        "INFO": "\033[32m",    # Green
        "WARNING": "\033[33m", # Yellow
        "ERROR": "\033[31m",   # Red
        "CRITICAL": "\033[41m" # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        log_line = (
            f"{color}{timestamp}{self.RESET} "
            f"| {color}{record.levelname}{self.RESET} "
            f"| {record.name} "
            f"| {record.getMessage()}"
        )
        return log_line


def get_logger(service_name: str) -> logging.Logger:
    """
    Configure logger with:
    - JSON logs to stdout (for Docker)
    - Daily rotated log files (for Promtail)
    - Colorful logs for debugging
    """

    logger = logging.getLogger(service_name)

    if logger.handlers:
        # Ensure file handler exists even if logger was created elsewhere
        has_file_handler = any(
            isinstance(h, TimedRotatingFileHandler)
            for h in logger.handlers
        )
        if has_file_handler:
            return logger

    logger.setLevel(logging.INFO)

    # -----------------------
    # 1️⃣ JSON CONSOLE HANDLER (for Docker + Loki later)
    # -----------------------
    json_handler = logging.StreamHandler(sys.stdout)
    json_handler.setFormatter(JsonFormatter())
    json_handler.setLevel(logging.INFO)
    logger.addHandler(json_handler)

    # -----------------------
    # 2️⃣ COLOR HUMAN-FRIENDLY CONSOLE (optional for local)
    # -----------------------
    color_handler = logging.StreamHandler(sys.stderr)
    color_handler.setFormatter(ColorFormatter())
    color_handler.setLevel(logging.INFO)
    logger.addHandler(color_handler)

    # -----------------------
    # 3️⃣ ROTATING FILE LOGS (day-wise)
    # -----------------------
    BASE_LOG_DIR = os.getenv("LOG_DIR", "logs") 
    LOG_DIR = os.path.join(BASE_LOG_DIR, service_name)

    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=f"{LOG_DIR}/{service_name}.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    return logger


# ----------------------------
# HOW to use logger 
# ---------------------------


# from logger_config import get_logger
# =========
# Service 1 
# =========
# logger = get_logger("api-service")

# logger.info("API started")
# logger.warning("Slow response detected")
# logger.error("Something went wrong!", exc_info=True)
# =========
# Service 2
# =========
# logger = get_logger("worker-service")
# logger.info("Task executed")
