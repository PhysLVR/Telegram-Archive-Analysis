"""
Import result data structure for Telegram Archive Analysis.

This module provides the ImportResult class that captures the outcome
of an import operation, including statistics and metadata.
It also defines the domain models used by the parser.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Set


@dataclass(frozen=True)
class Participant:
    """Represents a chat participant."""
    id: int
    name: str


@dataclass(frozen=True)
class Chat:
    """Represents chat metadata."""
    name: str
    description: str = ""
    type: str = "group"  # 'private', 'group', 'channel'


@dataclass(frozen=True)
class Message:
    """Represents a single message in the chat."""
    id: int
    timestamp: Optional[datetime]
    sender: Participant
    type: str  # 'text', 'media', 'service', 'location'
    text: str
    media: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    reply_to_id: Optional[int] = None
    edited_at: Optional[datetime] = None
    service_info: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class ImportResult:
    """
    Result of a Telegram export import operation.

    Attributes:
        chat: Chat metadata.
        participants: Set of unique participants found.
        messages: List of parsed messages.
    """

    chat: Chat
    participants: Set[Participant]
    messages: List[Message]

    @property
    def success(self) -> bool:
        """Whether the import completed without fatal errors."""
        return len(self.messages) > 0

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "chat_name": self.chat.name,
            "chat_type": self.chat.type,
            "participants_count": len(self.participants),
            "messages_count": len(self.messages),
            "success": self.success,
        }
