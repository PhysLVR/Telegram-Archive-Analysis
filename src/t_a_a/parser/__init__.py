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
    InvalidExportFormatError,
)
from .html_parser import (
    parse_telegram_html,
    parse_telegram_html_stream,
    parse_export_files,
    TelegramHTMLStreamParser,
)
from .import_result import ImportResult
from t_a_a.models.domain import Message, Chat, Participant

__all__ = [
    # Discovery
    "ExportDiscoveryResult",
    "discover_export",
    # Parser
    "parse_telegram_html",
    "parse_telegram_html_stream",
    "parse_export_files",
    "TelegramHTMLStreamParser",
    # Result
    "ImportResult",
    "Message",
    "Chat",
    "Participant",
    # Exceptions
    "ParserError",
    "InvalidInputError",
    "UnsupportedFormatError",
    "MalformedHTMLError",
    "MessageParseError",
    "InvalidExportFormatError",
    "ParseWarning",
]

