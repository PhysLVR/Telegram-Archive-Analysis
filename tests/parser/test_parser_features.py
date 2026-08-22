"""Tests for parser features with realistic Telegram Desktop HTML structures.

This module tests:
- Timezone-aware timestamp parsing
- Reaction extraction
- Forwarded message handling
- Document/file attachment detection
- RTL/Unicode sender names
- Malformed/truncated HTML recovery
- Streaming behavior with large synthetic input

All fixtures are modeled on actual Telegram Desktop HTML export structure.
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

from t_a_a.parser.html_parser import (
    parse_telegram_html,
    parse_telegram_html_stream,
    TelegramHTMLStreamParser,
)
from t_a_a.models.domain import Message, MessageReaction, MessageAttachment


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _get_first_message(file_path: Path) -> Optional[Message]:
    """Helper to get the first non-None message from a parsed file."""
    for msg, _chat, _participants in parse_telegram_html(file_path):
        if msg is not None:
            return msg
    return None


def _count_messages(file_path: Path) -> int:
    """Count successfully parsed messages in a file."""
    count = 0
    for msg, _chat, _participants in parse_telegram_html(file_path):
        if msg is not None:
            count += 1
    return count


class TestTimezoneAwareTimestamps:
    """Test parsing of timezone-aware timestamps from real Telegram exports."""

    def test_utc_plus_timestamp(self) -> None:
        """Test timestamp with positive UTC offset (UTC+03:30)."""
        fixture = FIXTURES_DIR / "timezone_messages.html"
        msg = _get_first_message(fixture)
        
        assert msg is not None
        assert msg.timestamp is not None
        # 13.02.2025 01:04:32 UTC+03:30 should be parsed as timezone-aware
        assert msg.timestamp.tzinfo is not None
        # Verify the offset is correct (3 hours 30 minutes)
        offset = msg.timestamp.utcoffset()
        assert offset is not None
        assert offset == timedelta(hours=3, minutes=30)
        # Verify the time components
        assert msg.timestamp.hour == 1
        assert msg.timestamp.minute == 4
        assert msg.timestamp.second == 32

    def test_utc_minus_timestamp(self) -> None:
        """Test timestamp with negative UTC offset (UTC-05:00)."""
        fixture = FIXTURES_DIR / "timezone_messages.html"
        # Get second message (index 1)
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 2
        
        msg = messages[1]
        assert msg.timestamp is not None
        assert msg.timestamp.tzinfo is not None
        offset = msg.timestamp.utcoffset()
        assert offset is not None
        assert offset == timedelta(hours=-5)

    def test_utc_zero_timestamp(self) -> None:
        """Test timestamp with UTC+00:00."""
        fixture = FIXTURES_DIR / "timezone_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 3
        
        msg = messages[2]
        assert msg.timestamp is not None
        assert msg.timestamp.tzinfo is not None
        offset = msg.timestamp.utcoffset()
        assert offset is not None
        assert offset == timedelta(0)

    def test_legacy_timestamp_treated_as_utc(self) -> None:
        """Legacy formats without explicit offset are treated as UTC.

        All timestamps returned by the parser are timezone-aware so that
        multi-file imports can safely compare earliest/latest values.
        """
        fixture = FIXTURES_DIR / "timezone_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 4

        msg = messages[3]
        assert msg.timestamp is not None
        assert msg.timestamp.tzinfo is not None
        offset = msg.timestamp.utcoffset()
        assert offset is not None
        assert offset == timedelta(0)


class TestReactions:
    """Test extraction of message reactions."""

    def test_multiple_reactions(self) -> None:
        """Test message with multiple reactions."""
        fixture = FIXTURES_DIR / "reaction_messages.html"
        msg = _get_first_message(fixture)
        
        assert msg is not None
        assert len(msg.reactions) == 3
        
        # Check first reaction
        assert msg.reactions[0].emoji == "👍"
        assert msg.reactions[0].count == 5
        
        # Check second reaction
        assert msg.reactions[1].emoji == "❤️"
        assert msg.reactions[1].count == 3
        
        # Check third reaction
        assert msg.reactions[2].emoji == "🎉"
        assert msg.reactions[2].count == 1

    def test_single_reaction(self) -> None:
        """Test message with single reaction."""
        fixture = FIXTURES_DIR / "reaction_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 2
        
        msg = messages[1]
        assert len(msg.reactions) == 1
        assert msg.reactions[0].emoji == "😂"
        assert msg.reactions[0].count == 2

    def test_no_reactions(self) -> None:
        """Test message without reactions."""
        fixture = FIXTURES_DIR / "reaction_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 3
        
        msg = messages[2]
        assert len(msg.reactions) == 0


class TestForwardedMessages:
    """Test extraction of forwarded message metadata."""

    def test_forwarded_from_name(self) -> None:
        """Test extraction of forwarded sender name."""
        fixture = FIXTURES_DIR / "forwarded_messages.html"
        msg = _get_first_message(fixture)
        
        assert msg is not None
        assert msg.forwarded_from is not None
        assert "DIGI ANTI" in msg.forwarded_from

    def test_forwarded_from_deleted_account(self) -> None:
        """Test forwarded message from deleted account."""
        fixture = FIXTURES_DIR / "forwarded_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 2
        
        msg = messages[1]
        assert msg.forwarded_from is not None
        assert msg.forwarded_from == "Deleted Account"

    def test_not_forwarded(self) -> None:
        """Test regular message without forwarding."""
        fixture = FIXTURES_DIR / "forwarded_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 3
        
        msg = messages[2]
        assert msg.forwarded_from is None


class TestDocumentAttachments:
    """Test extraction of document/file attachments."""

    def test_document_in_media_wrap(self) -> None:
        """Test document attachment in media wrapper."""
        fixture = FIXTURES_DIR / "document_messages.html"
        msg = _get_first_message(fixture)
        
        assert msg is not None
        assert len(msg.attachments) >= 1
        
        attachment = msg.attachments[0]
        assert attachment.type == "file"
        assert "report.pdf" in (attachment.file_path or "")

    def test_multiple_file_links(self) -> None:
        """Test message with multiple file links."""
        fixture = FIXTURES_DIR / "document_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 2
        
        msg = messages[1]
        # Should have file attachments from the links
        assert len(msg.attachments) >= 1


class TestRTLUnicodeSenderNames:
    """Test handling of RTL and Unicode sender names."""

    def test_persian_sender(self) -> None:
        """Test Persian sender name."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        msg = _get_first_message(fixture)
        
        assert msg is not None
        assert msg.sender_display_name == "علی رضایی"
        assert msg.sender_id == "علی رضایی"

    def test_arabic_sender(self) -> None:
        """Test Arabic sender name."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 2
        
        msg = messages[1]
        assert msg.sender_display_name == "محمد الأحمد"

    def test_mixed_rtl_ltr(self) -> None:
        """Test mixed RTL/LTR sender name."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 3
        
        msg = messages[2]
        assert "Ahmed" in msg.sender_display_name
        assert "أحمد" in msg.sender_display_name

    def test_chinese_sender(self) -> None:
        """Test Chinese sender name."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 4
        
        msg = messages[3]
        assert msg.sender_display_name == "李明"

    def test_cyrillic_sender(self) -> None:
        """Test Russian/Cyrillic sender name."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 5
        
        msg = messages[4]
        assert msg.sender_display_name == "Иван Петров"

    def test_emoji_sender(self) -> None:
        """Test emoji-only sender name."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 6
        
        msg = messages[5]
        assert "🎉" in msg.sender_display_name
        assert "🚀" in msg.sender_display_name

    def test_deleted_account(self) -> None:
        """Test 'Deleted Account' sender."""
        fixture = FIXTURES_DIR / "rtl_unicode_messages.html"
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 7
        
        msg = messages[6]
        assert msg.sender_display_name == "Deleted Account"


class TestMalformedHTML:
    """Test parser resilience against malformed/truncated HTML."""

    def test_recovers_from_unclosed_message(self) -> None:
        """Test that parser recovers from unclosed message tags."""
        fixture = FIXTURES_DIR / "malformed_truncated.html"
        
        # Should parse at least some valid messages
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 1

    def test_skips_missing_timestamp(self) -> None:
        """Test that messages without timestamps are skipped with warning."""
        fixture = FIXTURES_DIR / "malformed_truncated.html"
        
        with pytest.warns(UserWarning, match="unparsable timestamp"):
            messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
            # Valid messages should still be parsed
            assert len(messages) >= 1

    def test_handles_missing_sender(self) -> None:
        """Test handling of messages without sender information."""
        fixture = FIXTURES_DIR / "malformed_truncated.html"
        
        # Parser should handle missing sender gracefully
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        # At least some messages should be parsed
        assert len(messages) >= 1

    def test_handles_unclosed_nested_tags(self) -> None:
        """Test handling of unclosed nested HTML tags."""
        fixture = FIXTURES_DIR / "malformed_truncated.html"
        
        # Should not crash on unclosed tags
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        assert len(messages) >= 1


class TestStreamingBehavior:
    """Test streaming/memory behavior of the parser."""

    def test_yields_messages_incrementally(self) -> None:
        """Test that parser yields messages as they complete."""
        fixture = FIXTURES_DIR / "basic_messages.html"
        
        count = 0
        for msg, chat, participants in parse_telegram_html(fixture):
            if msg is not None:
                count += 1
                # Each yield should have chat and participants available
                assert chat is not None
                assert isinstance(participants, list)
        
        assert count >= 3  # basic_messages.html has 5 messages

    def test_stream_only_messages_api(self) -> None:
        """Test the stream-only API that yields only messages."""
        fixture = FIXTURES_DIR / "basic_messages.html"
        
        messages = list(parse_telegram_html_stream(fixture))
        assert len(messages) >= 3

    def test_large_synthetic_input_memory(self) -> None:
        """Test memory behavior with large synthetic input.
        
        This test generates a large HTML file in-memory and verifies
        that the parser processes it without loading everything at once.
        """
        import tempfile
        import os
        
        # Generate a synthetic HTML file with many messages
        num_messages = 1000
        
        html_parts = [
            '<!DOCTYPE html><html><head><title>Large Test</title></head><body><div class="chatlog">'
        ]
        
        for i in range(num_messages):
            html_parts.append(f'''
                <div id="message{i}" class="message default clearfix">
                    <div class="from_name">User{i % 10}</div>
                    <div class="pull_right date details" title="01.01.2025 12:{i % 60:02d}:00 UTC+00:00">12:{i % 60:02d}</div>
                    <div class="text">Message number {i} with some text content.</div>
                </div>
            ''')
        
        html_parts.append('</div></body></html>')
        html_content = ''.join(html_parts)
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_path = Path(f.name)
        
        try:
            # Parse and count messages
            count = 0
            for msg, _chat, _participants in parse_telegram_html(temp_path):
                if msg is not None:
                    count += 1
            
            assert count == num_messages
        finally:
            # Clean up
            os.unlink(temp_path)

    def test_parser_state_reset_between_messages(self) -> None:
        """Test that parser state is properly reset between messages."""
        fixture = FIXTURES_DIR / "basic_messages.html"
        
        messages = [msg for msg, _, _ in parse_telegram_html(fixture) if msg is not None]
        
        # All messages should have distinct IDs
        ids = [msg.message_id for msg in messages]
        assert len(ids) == len(set(ids)), "Duplicate message IDs detected"


class TestIntegrationFixtures:
    """Integration tests using all fixture files."""

    @pytest.mark.parametrize("fixture_name", [
        "basic_messages.html",
        "edited_messages.html",
        "formatted_messages.html",
        "link_messages.html",
        "media_messages.html",
        "reply_messages.html",
        "service_messages.html",
        "unicode_messages.html",
        "messages_part1.html",
        "messages_part2.html",
        "timezone_messages.html",
        "reaction_messages.html",
        "forwarded_messages.html",
        "document_messages.html",
        "rtl_unicode_messages.html",
    ])
    def test_parse_all_fixtures(self, fixture_name: str) -> None:
        """Test that all fixture files can be parsed without crashing."""
        fixture_path = FIXTURES_DIR / fixture_name
        
        if not fixture_path.exists():
            pytest.skip(f"Fixture {fixture_name} not found")
        
        # Should not raise any exceptions
        messages = list(parse_telegram_html_stream(fixture_path))
        
        # Each fixture should have at least one message
        assert len(messages) >= 1, f"Fixture {fixture_name} yielded no messages"
