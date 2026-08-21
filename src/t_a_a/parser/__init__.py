"""
Parser module for Telegram Archive Analysis.

This module provides functionality for discovering and parsing
Telegram export files.
"""

from .discovery import ExportDiscoveryResult, discover_export
from .exceptions import (
    InvalidInputError,
    MalformedHTMLError,
    MessageParseError,
    ParserError,
    ParseWarning,
    UnsupportedFormatError,
)
from .html_parser import parse_export_files, parse_telegram_html
from .import_result import ImportResult

__all__ = [
    # Discovery
    "ExportDiscoveryResult",
    "discover_export",
    # Parser
    "parse_telegram_html",
    "parse_export_files",
    # Result
    "ImportResult",
    # Exceptions
    "ParserError",
    "InvalidInputError",
    "UnsupportedFormatError",
    "MalformedHTMLError",
    "MessageParseError",
    "ParseWarning",
]
