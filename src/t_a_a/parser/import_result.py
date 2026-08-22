"""
Import result data structure for Telegram Archive Analysis.

This module provides the ImportResult class that captures the outcome
of an import operation, including statistics and metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ImportResult:
    """
    Result of a Telegram export import operation.

    Attributes:
        input_path: The original input path provided by the user.
        files_processed: Number of HTML files processed.
        messages_parsed: Number of successfully parsed messages.
        messages_skipped: Number of messages that failed to parse.
        participants_discovered: Number of unique participants found.
        service_messages: Number of service/system messages.
        attachments_found: Total number of attachments across all messages.
        links_found: Total number of links extracted.
        warnings_count: Number of warnings generated during import.
        errors_count: Number of errors encountered.
        earliest_timestamp: Earliest message timestamp if available.
        latest_timestamp: Latest message timestamp if available.
        import_timestamp: When the import was performed.
    """

    input_path: str
    files_processed: int = 0
    messages_parsed: int = 0
    messages_skipped: int = 0
    participants_discovered: int = 0
    service_messages: int = 0
    attachments_found: int = 0
    links_found: int = 0
    warnings_count: int = 0
    errors_count: int = 0
    earliest_timestamp: datetime | None = None
    latest_timestamp: datetime | None = None
    import_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        """Whether the import completed without fatal errors."""
        return self.errors_count == 0 and self.messages_parsed > 0

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "input_path": self.input_path,
            "files_processed": self.files_processed,
            "messages_parsed": self.messages_parsed,
            "messages_skipped": self.messages_skipped,
            "participants_discovered": self.participants_discovered,
            "service_messages": self.service_messages,
            "attachments_found": self.attachments_found,
            "links_found": self.links_found,
            "warnings_count": self.warnings_count,
            "errors_count": self.errors_count,
            "earliest_timestamp": self.earliest_timestamp.isoformat() if self.earliest_timestamp else None,
            "latest_timestamp": self.latest_timestamp.isoformat() if self.latest_timestamp else None,
            "import_timestamp": self.import_timestamp.isoformat(),
            "success": self.success,
        }
