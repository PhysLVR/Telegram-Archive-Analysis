"""
Tests for domain models.
"""

from datetime import datetime

import pytest

from t_a_a.models.domain import (
    Chat,
    Message,
    MessageAttachment,
    MessageLink,
    MessageReaction,
    Participant,
)


class TestParticipant:
    """Tests for the Participant model."""

    def test_create_participant_with_id(self) -> None:
        """Test creating a participant with an ID."""
        participant = Participant(id="user123", display_name="Test User")
        assert participant.id == "user123"
        assert participant.display_name == "Test User"
        assert participant.username is None
        assert participant.is_bot is False
        assert participant.metadata == {}

    def test_create_participant_with_username(self) -> None:
        """Test creating a participant with a username."""
        participant = Participant(
            id="user456",
            display_name="Alice",
            username="alice_official",
        )
        assert participant.username == "alice_official"

    def test_create_participant_bot(self) -> None:
        """Test creating a bot participant."""
        participant = Participant(
            id="bot789",
            display_name="Helper Bot",
            is_bot=True,
        )
        assert participant.is_bot is True

    def test_create_participant_with_metadata(self) -> None:
        """Test creating a participant with metadata."""
        metadata = {"joined_at": "2024-01-01", "role": "admin"}
        participant = Participant(
            id="admin001",
            display_name="Admin",
            metadata=metadata,
        )
        assert participant.metadata == metadata

    def test_participant_requires_id_or_display_name(self) -> None:
        """Test that participant requires at least id or display_name."""
        with pytest.raises(ValueError, match="must have either id or display_name"):
            Participant()

    def test_participant_frozen(self) -> None:
        """Test that participant is immutable."""
        participant = Participant(id="user1", display_name="User One")
        with pytest.raises(AttributeError):
            participant.display_name = "Changed"  # type: ignore[misc]


class TestMessageAttachment:
    """Tests for the MessageAttachment model."""

    def test_create_attachment_minimal(self) -> None:
        """Test creating an attachment with minimal fields."""
        attachment = MessageAttachment(type="photo")
        assert attachment.type == "photo"
        assert attachment.file_name is None
        assert attachment.file_path is None

    def test_create_attachment_full(self) -> None:
        """Test creating an attachment with all fields."""
        attachment = MessageAttachment(
            type="file",
            file_name="document.pdf",
            file_path="files/document.pdf",
            mime_type="application/pdf",
            size_bytes=102400,
            metadata={"pages": 5},
        )
        assert attachment.file_name == "document.pdf"
        assert attachment.size_bytes == 102400


class TestMessageReaction:
    """Tests for the MessageReaction model."""

    def test_create_reaction_minimal(self) -> None:
        """Test creating a reaction with minimal fields."""
        reaction = MessageReaction(emoji="👍")
        assert reaction.emoji == "👍"
        assert reaction.count == 1
        assert reaction.sender_ids == []

    def test_create_reaction_with_count(self) -> None:
        """Test creating a reaction with count."""
        reaction = MessageReaction(emoji="❤️", count=5)
        assert reaction.count == 5

    def test_create_reaction_with_senders(self) -> None:
        """Test creating a reaction with sender IDs."""
        reaction = MessageReaction(
            emoji="🔥",
            count=3,
            sender_ids=["user1", "user2", "user3"],
        )
        assert len(reaction.sender_ids) == 3


class TestMessageLink:
    """Tests for the MessageLink model."""

    def test_create_link_minimal(self) -> None:
        """Test creating a link with minimal fields."""
        link = MessageLink(url="https://example.com")
        assert link.url == "https://example.com"
        assert link.text is None
        assert link.domain is None

    def test_create_link_full(self) -> None:
        """Test creating a link with all fields."""
        link = MessageLink(
            url="https://github.com/example/repo",
            text="Check this repo",
            domain="github.com",
        )
        assert link.text == "Check this repo"
        assert link.domain == "github.com"


class TestMessage:
    """Tests for the Message model."""

    def test_create_message_minimal(self) -> None:
        """Test creating a message with minimal required fields."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        message = Message(
            message_id="msg001",
            timestamp=timestamp,
        )
        assert message.message_id == "msg001"
        assert message.timestamp == timestamp
        assert message.message_type == "text"
        assert message.text_content is None
        assert message.reactions == []
        assert message.attachments == []

    def test_create_message_full(self) -> None:
        """Test creating a message with all fields."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        edited = datetime(2024, 1, 15, 11, 0, 0)
        message = Message(
            message_id="msg002",
            timestamp=timestamp,
            sender_id="user123",
            sender_display_name="John Doe",
            message_type="text",
            text_content="Hello, world!",
            reply_to_id="msg001",
            forwarded_from="Another Chat",
            edited_at=edited,
            source_file="result.json",
        )
        assert message.sender_id == "user123"
        assert message.text_content == "Hello, world!"
        assert message.reply_to_id == "msg001"
        assert message.edited_at == edited

    def test_create_message_with_reactions(self) -> None:
        """Test creating a message with reactions."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        reactions = [
            MessageReaction(emoji="👍", count=3),
            MessageReaction(emoji="❤️", count=2),
        ]
        message = Message(
            message_id="msg003",
            timestamp=timestamp,
            reactions=reactions,
        )
        assert len(message.reactions) == 2

    def test_create_message_with_attachments(self) -> None:
        """Test creating a message with attachments."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        attachments = [
            MessageAttachment(type="photo", file_name="image.jpg"),
            MessageAttachment(type="video", file_name="clip.mp4"),
        ]
        message = Message(
            message_id="msg004",
            timestamp=timestamp,
            attachments=attachments,
        )
        assert len(message.attachments) == 2

    def test_message_requires_message_id(self) -> None:
        """Test that message requires message_id."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        with pytest.raises(ValueError, match="must have a message_id"):
            Message(
                message_id="",
                timestamp=timestamp,
            )

    def test_message_requires_timestamp(self) -> None:
        """Test that message requires timestamp."""
        with pytest.raises(ValueError, match="must have a timestamp"):
            Message(
                message_id="msg005",
                timestamp=None,  # type: ignore[arg-type]
            )

    def test_message_frozen(self) -> None:
        """Test that message is immutable."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        message = Message(
            message_id="msg006",
            timestamp=timestamp,
            text_content="Original",
        )
        with pytest.raises(AttributeError):
            message.text_content = "Modified"  # type: ignore[misc]


class TestChat:
    """Tests for the Chat model."""

    def test_create_chat_minimal(self) -> None:
        """Test creating a chat with minimal required fields."""
        chat = Chat(
            chat_id="chat001",
            title="Test Chat",
        )
        assert chat.chat_id == "chat001"
        assert chat.title == "Test Chat"
        assert chat.chat_type == "unknown"
        assert chat.participants == []
        assert chat.source_files == []

    def test_create_chat_full(self) -> None:
        """Test creating a chat with all fields."""
        participants = [
            Participant(id="user1", display_name="Alice"),
            Participant(id="user2", display_name="Bob"),
        ]
        created = datetime(2023, 6, 1, 0, 0, 0)
        chat = Chat(
            chat_id="chat002",
            title="Group Chat",
            chat_type="supergroup",
            participants=participants,
            source_files=["result.json", "result1.html"],
            created_at=created,
            metadata={"member_count": 150},
        )
        assert chat.chat_type == "supergroup"
        assert len(chat.participants) == 2
        assert len(chat.source_files) == 2
        assert chat.metadata["member_count"] == 150

    def test_chat_requires_chat_id(self) -> None:
        """Test that chat requires chat_id."""
        with pytest.raises(ValueError, match="must have a chat_id"):
            Chat(
                chat_id="",
                title="Test",
            )

    def test_chat_requires_title(self) -> None:
        """Test that chat requires title."""
        with pytest.raises(ValueError, match="must have a title"):
            Chat(
                chat_id="chat003",
                title="",
            )

    def test_chat_frozen(self) -> None:
        """Test that chat is immutable."""
        chat = Chat(chat_id="chat004", title="Original Title")
        with pytest.raises(AttributeError):
            chat.title = "New Title"  # type: ignore[misc]
