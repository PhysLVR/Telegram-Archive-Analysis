"""
Tests for Telegram HTML parser.
"""

from datetime import datetime
from pathlib import Path

import pytest

from t_a_a.models.domain import Message, Participant
from t_a_a.parser.html_parser import (
    _extract_links_from_html,
    _parse_timestamp,
    parse_telegram_html,
)


class TestTimestampParsing:
    """Tests for timestamp parsing functionality."""

    def test_parse_us_format(self) -> None:
        """Test parsing US-style timestamps."""
        result = _parse_timestamp("Jan 15, 2024, 10:30 PM")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 22
        assert result.minute == 30

    def test_parse_european_format(self) -> None:
        """Test parsing European-style timestamps."""
        result = _parse_timestamp("15.01.2024 22:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 22
        assert result.minute == 30

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO format timestamps."""
        result = _parse_timestamp("2024-01-15T22:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 22
        assert result.minute == 30

    def test_parse_invalid_timestamp(self) -> None:
        """Test parsing invalid timestamps."""
        result = _parse_timestamp("not a timestamp")
        assert result is None


class TestLinkExtraction:
    """Tests for link extraction functionality."""

    def test_extract_single_link(self) -> None:
        """Test extracting a single link from HTML."""
        html = '<a href="https://example.com">Example</a>'
        links = _extract_links_from_html(html)
        assert len(links) == 1
        assert links[0].url == "https://example.com"
        assert links[0].text == "Example"
        assert links[0].domain == "example.com"

    def test_extract_multiple_links(self) -> None:
        """Test extracting multiple links from HTML."""
        html = """
            <a href="https://github.com">GitHub</a>
            <a href="https://python.org">Python</a>
        """
        links = _extract_links_from_html(html)
        assert len(links) == 2

    def test_extract_link_without_text(self) -> None:
        """Test extracting link when no display text is provided."""
        html = '<a href="https://example.com"></a>'
        links = _extract_links_from_html(html)
        assert len(links) == 1
        # Text should default to URL when empty
        assert links[0].text is None or links[0].text == "https://example.com"


class TestBasicMessageParsing:
    """Tests for basic message parsing from fixtures."""

    @pytest.fixture
    def basic_fixture_path(self) -> str:
        """Path to basic messages fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "basic_messages.html")

    def test_parse_basic_messages(self, basic_fixture_path: str) -> None:
        """Test parsing basic text messages."""
        messages = []
        participants = []

        for message, chat_info, current_participants in parse_telegram_html(
            basic_fixture_path
        ):
            if message:
                messages.append(message)
                participants = current_participants

        assert len(messages) == 3
        assert messages[0].message_id == "message1"
        assert messages[0].sender_display_name == "Alice"
        assert messages[0].text_content == "Hello, this is a test message!"

    def test_parse_message_ids(self, basic_fixture_path: str) -> None:
        """Test that message IDs are preserved correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(basic_fixture_path) if m is not None
        ]
        assert messages[0].message_id == "message1"
        assert messages[1].message_id == "message2"
        assert messages[2].message_id == "message3"

    def test_parse_timestamps(self, basic_fixture_path: str) -> None:
        """Test that timestamps are parsed correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(basic_fixture_path) if m is not None
        ]
        assert messages[0].timestamp is not None
        assert messages[0].timestamp.year == 2024
        assert messages[0].timestamp.month == 1
        assert messages[0].timestamp.day == 15

    def test_extract_participants(self, basic_fixture_path: str) -> None:
        """Test participant extraction."""
        all_participants = []
        for _, _, participants in parse_telegram_html(basic_fixture_path):
            all_participants = participants

        assert len(all_participants) == 2
        participant_names = {p.display_name for p in all_participants}
        assert "Alice" in participant_names
        assert "Bob" in participant_names


class TestFormattedMessages:
    """Tests for formatted message parsing."""

    @pytest.fixture
    def formatted_fixture_path(self) -> str:
        """Path to formatted messages fixture."""
        return str(
            Path(__file__).parent.parent / "fixtures" / "formatted_messages.html"
        )

    def test_parse_formatted_text(self, formatted_fixture_path: str) -> None:
        """Test that formatted text is extracted correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(formatted_fixture_path) if m is not None
        ]
        assert len(messages) >= 1
        # First message should contain "Bold text" and "italic text"
        first_text = messages[0].text_content or ""
        assert "Bold text" in first_text
        assert "italic text" in first_text


class TestMediaMessages:
    """Tests for media message parsing."""

    @pytest.fixture
    def media_fixture_path(self) -> str:
        """Path to media messages fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "media_messages.html")

    def test_parse_media_attachments(self, media_fixture_path: str) -> None:
        """Test that media attachments are detected."""
        messages = [
            m for m, _, _ in parse_telegram_html(media_fixture_path) if m is not None
        ]
        # At least one message should have attachments
        messages_with_attachments = [m for m in messages if m.attachments]
        assert len(messages_with_attachments) >= 1

    def test_media_message_type(self, media_fixture_path: str) -> None:
        """Test that media messages are identified correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(media_fixture_path) if m is not None
        ]
        media_messages = [m for m in messages if m.message_type == "media"]
        assert len(media_messages) >= 1


class TestReplyMessages:
    """Tests for reply relationship parsing."""

    @pytest.fixture
    def reply_fixture_path(self) -> str:
        """Path to reply messages fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "reply_messages.html")

    def test_parse_reply_relationship(self, reply_fixture_path: str) -> None:
        """Test that reply-to relationships are extracted."""
        messages = [
            m for m, _, _ in parse_telegram_html(reply_fixture_path) if m is not None
        ]
        # Find the replying message
        reply_messages = [m for m in messages if m.reply_to_id is not None]
        assert len(reply_messages) >= 1
        assert reply_messages[0].reply_to_id == "100"


class TestLinkMessages:
    """Tests for link extraction from messages."""

    @pytest.fixture
    def link_fixture_path(self) -> str:
        """Path to link messages fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "link_messages.html")

    def test_extract_links(self, link_fixture_path: str) -> None:
        """Test that links are extracted from messages."""
        messages = [
            m for m, _, _ in parse_telegram_html(link_fixture_path) if m is not None
        ]
        messages_with_links = [m for m in messages if m.links]
        assert len(messages_with_links) >= 1

    def test_link_domains(self, link_fixture_path: str) -> None:
        """Test that link domains are extracted correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(link_fixture_path) if m is not None
        ]
        all_links = []
        for m in messages:
            all_links.extend(m.links)

        domains = {link.domain for link in all_links if link.domain}
        assert "example.com" in domains or "github.com" in domains


class TestServiceMessages:
    """Tests for service message handling."""

    @pytest.fixture
    def service_fixture_path(self) -> str:
        """Path to service messages fixture."""
        return str(
            Path(__file__).parent.parent / "fixtures" / "service_messages.html"
        )

    def test_parse_service_messages(self, service_fixture_path: str) -> None:
        """Test that service messages are parsed without crashing."""
        messages = [
            m for m, _, _ in parse_telegram_html(service_fixture_path) if m is not None
        ]
        assert len(messages) >= 1

    def test_service_message_type(self, service_fixture_path: str) -> None:
        """Test that service messages are identified correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(service_fixture_path) if m is not None
        ]
        service_messages = [m for m in messages if m.message_type == "service"]
        # Should have at least some service messages
        assert len(service_messages) >= 1


class TestEditedMessages:
    """Tests for edited message parsing."""

    @pytest.fixture
    def edited_fixture_path(self) -> str:
        """Path to edited messages fixture."""
        return str(
            Path(__file__).parent.parent / "fixtures" / "edited_messages.html"
        )

    def test_parse_edit_timestamp(self, edited_fixture_path: str) -> None:
        """Test that edit timestamps are extracted."""
        messages = [
            m for m, _, _ in parse_telegram_html(edited_fixture_path) if m is not None
        ]
        edited_messages = [m for m in messages if m.edited_at is not None]
        assert len(edited_messages) >= 1


class TestMultiPartExports:
    """Tests for multi-part export handling."""

    @pytest.fixture
    def multipart_fixture_dir(self) -> str:
        """Path to multi-part fixtures directory."""
        return str(Path(__file__).parent.parent / "fixtures")

    def test_discover_multiple_parts(self, multipart_fixture_dir: str) -> None:
        """Test that multiple HTML parts are discovered."""
        from t_a_a.parser.discovery import discover_export

        result = discover_export(multipart_fixture_dir)
        # Should find multiple HTML files
        assert len(result.discovered_files) >= 2

    def test_parse_multiple_files(self, multipart_fixture_dir: str) -> None:
        """Test parsing multiple HTML files."""
        from t_a_a.parser.discovery import discover_export
        from t_a_a.parser.html_parser import parse_export_files

        discovery = discover_export(multipart_fixture_dir)
        # Filter to only our test part files
        test_files = [f for f in discovery.discovered_files if "messages_part" in f]

        messages = []
        for message, _, _ in parse_export_files(test_files):
            if message:
                messages.append(message)

        # Should have messages from both parts
        assert len(messages) >= 4


class TestUnicodeContent:
    """Tests for Unicode and Persian content handling."""

    @pytest.fixture
    def unicode_fixture_path(self) -> str:
        """Path to unicode messages fixture."""
        return str(Path(__file__).parent.parent / "fixtures" / "unicode_messages.html")

    def test_parse_persian_text(self, unicode_fixture_path: str) -> None:
        """Test that Persian text is parsed correctly."""
        messages = [
            m for m, _, _ in parse_telegram_html(unicode_fixture_path) if m is not None
        ]
        assert len(messages) >= 1
        # Check that Persian text is preserved
        first_text = messages[0].text_content or ""
        assert "سلام" in first_text or "فارسی" in first_text

    def test_parse_emoji(self, unicode_fixture_path: str) -> None:
        """Test that emojis are preserved."""
        messages = [
            m for m, _, _ in parse_telegram_html(unicode_fixture_path) if m is not None
        ]
        emoji_messages = [m for m in messages if "🎉" in (m.text_content or "")]
        assert len(emoji_messages) >= 1

    def test_parse_mixed_scripts(self, unicode_fixture_path: str) -> None:
        """Test that mixed language scripts are handled."""
        messages = [
            m for m, _, _ in parse_telegram_html(unicode_fixture_path) if m is not None
        ]
        # At least one message should have mixed content
        has_mixed = any(
            m.text_content and ("English" in m.text_content and "فارسی" in m.text_content)
            for m in messages
        )
        assert has_mixed


class TestMalformedInput:
    """Tests for malformed input handling."""

    @pytest.fixture
    def malformed_fixture_path(self) -> str:
        """Path to malformed messages fixture."""
        return str(
            Path(__file__).parent.parent / "fixtures" / "malformed_messages.html"
        )

    def test_skip_malformed_messages(self, malformed_fixture_path: str) -> None:
        """Test that malformed messages are skipped gracefully."""
        messages = []
        skipped = 0

        for message, _, _ in parse_telegram_html(malformed_fixture_path):
            if message:
                messages.append(message)
            else:
                skipped += 1

        # Should have at least one valid message
        assert len(messages) >= 1
        # Should have skipped some malformed ones
        assert skipped >= 1

    def test_valid_messages_still_parsed(self, malformed_fixture_path: str) -> None:
        """Test that valid messages are still parsed despite malformed ones."""
        messages = [
            m for m, _, _ in parse_telegram_html(malformed_fixture_path) if m is not None
        ]
        valid_user_found = any(m.sender_display_name == "ValidUser" for m in messages)
        assert valid_user_found


class TestDiscovery:
    """Tests for export file discovery."""

    def test_discover_single_file(self) -> None:
        """Test discovering a single HTML file."""
        from t_a_a.parser.discovery import discover_export

        fixture_path = str(
            Path(__file__).parent.parent / "fixtures" / "basic_messages.html"
        )
        result = discover_export(fixture_path)

        assert len(result.discovered_files) == 1
        assert result.is_directory is False

    def test_discover_directory(self) -> None:
        """Test discovering files in a directory."""
        from t_a_a.parser.discovery import discover_export

        fixture_dir = str(Path(__file__).parent.parent / "fixtures")
        result = discover_export(fixture_dir)

        assert result.is_directory is True
        assert len(result.discovered_files) >= 2

    def test_discover_nonexistent_path(self) -> None:
        """Test error handling for nonexistent paths."""
        from t_a_a.parser.discovery import discover_export
        from t_a_a.parser.exceptions import InvalidInputError

        with pytest.raises(InvalidInputError):
            discover_export("/nonexistent/path")

    def test_deterministic_ordering(self) -> None:
        """Test that discovered files are sorted deterministically."""
        from t_a_a.parser.discovery import discover_export

        fixture_dir = str(Path(__file__).parent.parent / "fixtures")
        result1 = discover_export(fixture_dir)
        result2 = discover_export(fixture_dir)

        assert result1.discovered_files == result2.discovered_files
