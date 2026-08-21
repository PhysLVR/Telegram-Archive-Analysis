"""
Exceptions for the Telegram Archive Analysis parser module.
"""


class ParserError(Exception):
    """Base exception for parser-related errors."""

    pass


class InvalidInputError(ParserError):
    """Raised when the input path is invalid or inaccessible."""

    pass


class UnsupportedFormatError(ParserError):
    """Raised when the export format is not supported."""

    def __init__(self, message: str, detected_format: str | None = None) -> None:
        super().__init__(message)
        self.detected_format = detected_format


class MalformedHTMLError(ParserError):
    """Raised when HTML parsing encounters malformed structure."""

    def __init__(
        self, message: str, file_path: str | None = None, line_number: int | None = None
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.line_number = line_number


class ParseWarning(Warning):
    """Warning for recoverable parsing issues."""

    pass


class MessageParseError(ParserError):
    """Raised when a specific message fails to parse."""

    def __init__(
        self,
        message: str,
        message_id: str | None = None,
        file_path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message_id = message_id
        self.file_path = file_path
