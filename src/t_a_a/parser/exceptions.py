"""Custom exceptions for the parser module."""


class ParserError(Exception):
    """Base exception for parser-related errors."""
    pass


class InvalidExportFormatError(ParserError):
    """Raised when an export file has an invalid or unsupported format."""
    pass


class InvalidInputError(ParserError):
    """Raised when input path is invalid or inaccessible."""
    pass


class UnsupportedFormatError(ParserError):
    """Raised when the export format is not supported."""
    pass


class MalformedHTMLError(ParserError):
    """Raised when HTML structure is malformed or unreadable."""
    pass


class MessageParseError(ParserError):
    """Raised when a specific message fails to parse."""
    pass


class ParseWarning(UserWarning):
    """Warning issued during parsing when encountering recoverable issues."""
    pass
