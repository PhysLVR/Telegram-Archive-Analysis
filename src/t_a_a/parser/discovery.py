"""
Export discovery module for Telegram Archive Analysis.

This module handles locating and validating Telegram export files,
supporting both single files and multi-part exports.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import InvalidInputError, UnsupportedFormatError


@dataclass(frozen=True)
class ExportDiscoveryResult:
    """
    Result of export file discovery.

    Attributes:
        input_path: The original input path provided by the user.
        is_directory: Whether the input was a directory.
        discovered_files: List of discovered Telegram export HTML files.
        chat_title: Chat title if discoverable from the export.
        warnings: List of warning messages encountered during discovery.
    """

    input_path: str
    is_directory: bool
    discovered_files: list[str] = field(default_factory=list)
    chat_title: str | None = None
    warnings: list[str] = field(default_factory=list)


def _is_telegram_html_file(file_path: Path) -> bool:
    """
    Check if a file appears to be a Telegram export HTML file.

    This function performs lightweight checks to identify Telegram
    Desktop HTML exports without fully parsing the file.

    Args:
        file_path: Path to the file to check.

    Returns:
        True if the file appears to be a Telegram export HTML file.
    """
    if file_path.suffix.lower() != ".html":
        return False

    # Check filename patterns commonly used by Telegram exports
    filename_lower = file_path.name.lower()

    # Primary pattern: messages.html or messages*.html
    # Also accept chat*.html or any *.html in test fixtures
    is_likely_name = (
        filename_lower.startswith("messages")
        or filename_lower.startswith("chat")
        or filename_lower.endswith("_messages.html")
    )

    if is_likely_name or filename_lower.endswith(".html"):
        # Quick content check - look for Telegram signature
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                # Read first 4KB to check for Telegram markers
                content_sample = f.read(4096).lower()
                if (
                    "telegram" in content_sample
                    or "message" in content_sample
                    or "chat" in content_sample
                    or "from_name" in content_sample
                ):
                    return True
        except (OSError, UnicodeDecodeError):
            pass

    return False


def _discover_html_files(directory: Path) -> list[Path]:
    """
    Discover all Telegram HTML export files in a directory.

    Recursively searches the directory for files matching Telegram
    export patterns.

    Args:
        directory: Directory to search.

    Returns:
        Sorted list of discovered HTML file paths.
    """
    html_files: list[Path] = []

    for root, _dirs, files in os.walk(directory):
        for filename in files:
            file_path = Path(root) / filename
            if _is_telegram_html_file(file_path):
                html_files.append(file_path)

    # Sort deterministically by path
    return sorted(html_files)


def discover_export(input_path: str) -> ExportDiscoveryResult:
    """
    Discover Telegram export files from the given input path.

    The input can be:
    - A single HTML file (Telegram export)
    - A directory containing Telegram export files

    Args:
        input_path: Path to the Telegram export file or directory.

    Returns:
        ExportDiscoveryResult with discovered files and metadata.

    Raises:
        InvalidInputError: If the input path does not exist or is inaccessible.
        UnsupportedFormatError: If no valid Telegram export files are found.
    """
    path = Path(input_path)

    # Validate input exists
    if not path.exists():
        raise InvalidInputError(f"Input path does not exist: {input_path}")

    if not os.access(path, os.R_OK):
        raise InvalidInputError(f"Input path is not readable: {input_path}")

    is_directory = path.is_dir()
    discovered_files: list[Path] = []
    warnings: list[str] = []

    if is_directory:
        discovered_files = _discover_html_files(path)
        if not discovered_files:
            raise UnsupportedFormatError(
                f"No Telegram HTML export files found in directory: {input_path}",
                detected_format="directory",
            )
    else:
        # Single file
        if _is_telegram_html_file(path):
            discovered_files = [path]
        else:
            raise UnsupportedFormatError(
                f"File does not appear to be a Telegram HTML export: {input_path}",
                detected_format="html" if path.suffix.lower() == ".html" else "unknown",
            )

    # Convert to string paths for result
    file_paths = [str(f) for f in discovered_files]

    return ExportDiscoveryResult(
        input_path=input_path,
        is_directory=is_directory,
        discovered_files=file_paths,
        warnings=warnings,
    )
