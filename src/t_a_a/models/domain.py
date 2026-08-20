"""
Domain models for Telegram chat data.

These models represent the core domain entities and are independent
of any persistence mechanism. They use dataclasses for clarity and
immutability where appropriate.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Participant:
    """
    Represents a participant in a Telegram chat.

    Attributes:
        id: Stable identifier for the participant if available.
        display_name: The name shown in the chat.
        username: Telegram username if available.
        is_bot: Whether this participant is a bot.
        metadata: Additional metadata about the participant.
    """
    id: str | None = None
    display_name: str = ""
    username: str | None = None
    is_bot: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id and not self.display_name:
            raise ValueError("Participant must have either id or display_name")


@dataclass(frozen=True)
class MessageAttachment:
    """
    Represents an attachment in a message.

    Attributes:
        type: Type of attachment (photo, video, audio, file, sticker, etc.).
        file_name: Original file name if available.
        file_path: Path to the file within the export.
        mime_type: MIME type if available.
        size_bytes: File size in bytes if available.
        metadata: Additional metadata about the attachment.
    """
    type: str
    file_name: str | None = None
    file_path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageReaction:
    """
    Represents a reaction on a message.

    Attributes:
        emoji: The emoji used in the reaction.
        count: Number of times this reaction was given.
        sender_ids: IDs of participants who gave this reaction (if available).
    """
    emoji: str
    count: int = 1
    sender_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MessageLink:
    """
    Represents a link found in a message.

    Attributes:
        url: The full URL.
        text: Display text for the link if available.
        domain: Extracted domain from the URL.
    """
    url: str
    text: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class Message:
    """
    Represents a single message in a Telegram chat.

    This is the core domain model for messages. All fields are optional
    except message_id and timestamp, as Telegram exports may not guarantee
    all fields for every message.

    Attributes:
        message_id: Unique identifier for the message within its chat.
        timestamp: When the message was sent.
        sender_id: ID of the message sender if available.
        sender_display_name: Display name of the sender.
        message_type: Type of message (text, photo, video, service, etc.).
        text_content: Textual content of the message.
        reply_to_id: ID of the message being replied to, if any.
        forwarded_from: Information about forwarded message origin.
        edited_at: Timestamp when the message was last edited.
        reactions: List of reactions on the message.
        attachments: List of media/file attachments.
        links: List of links found in the message.
        raw_metadata: Original/raw metadata from the source.
        source_file: Path to the source file this message was parsed from.
    """
    message_id: str
    timestamp: datetime
    sender_id: str | None = None
    sender_display_name: str | None = None
    message_type: str = "text"
    text_content: str | None = None
    reply_to_id: str | None = None
    forwarded_from: str | None = None
    edited_at: datetime | None = None
    reactions: list[MessageReaction] = field(default_factory=list)
    attachments: list[MessageAttachment] = field(default_factory=list)
    links: list[MessageLink] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    source_file: str | None = None

    def __post_init__(self) -> None:
        if not self.message_id:
            raise ValueError("Message must have a message_id")
        if not self.timestamp:
            raise ValueError("Message must have a timestamp")


@dataclass(frozen=True)
class Chat:
    """
    Represents a Telegram chat.

    Attributes:
        chat_id: Unique identifier for the chat.
        title: Chat title/name.
        chat_type: Type of chat (private, group, supergroup, channel).
        participants: List of participants in the chat.
        source_files: List of source files this chat was imported from.
        created_at: Chat creation timestamp if available.
        metadata: Additional metadata about the chat.
    """
    chat_id: str
    title: str
    chat_type: str = "unknown"
    participants: list[Participant] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chat_id:
            raise ValueError("Chat must have a chat_id")
        if not self.title:
            raise ValueError("Chat must have a title")
