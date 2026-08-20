"""
Logging configuration for T_A_A.

Provides a centralized logging setup with support for different
log levels and formatted output.
"""

import logging
import sys


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: str | None = None,
) -> logging.Logger:
    """
    Get or create a logger with the specified configuration.

    Args:
        name: Logger name (typically __name__ of the calling module).
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional file path to write logs to.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def set_log_level(logger: logging.Logger, level: int) -> None:
    """
    Set the logging level for a logger and all its handlers.

    Args:
        logger: The logger to configure.
        level: The logging level to set.
    """
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
