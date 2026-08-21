"""
Telegram HTML export parser.

This module parses Telegram Desktop HTML exports and converts them
into domain models (Message, Chat, Participant).
"""

import logging
import re
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from t_a_a.models.domain import (
    Chat,
    Message,
    MessageAttachment,
    MessageLink,
    MessageReaction,
    Participant,
)

from .exceptions import MalformedHTMLError, MessageParseError, ParseWarning

logger = logging.getLogger(__name__)


# Telegram timestamp format patterns
TIMESTAMP_PATTERNS = [
    # "Jan 15, 2024, 10:30 PM"
    r"%b %d, %Y, %I:%M %p",
    # "15.01.2024 22:30:00"
    r"%d.%m.%Y %H:%M:%S",
    # "2024-01-15T22:30:00"
    r"%Y-%m-%dT%H:%M:%S",
    # "Jan 15, 2024 at 10:30 PM"
    r"%b %d, %Y at %I:%M %p",
]


def _parse_timestamp(timestamp_str: str) -> datetime | None:
    """
    Parse a timestamp string from Telegram export.

    Tries multiple common timestamp formats used by Telegram Desktop.

    Args:
        timestamp_str: Timestamp string to parse.

    Returns:
        Parsed datetime object or None if parsing fails.
    """
    timestamp_str = timestamp_str.strip()

    for pattern in TIMESTAMP_PATTERNS:
        try:
            return datetime.strptime(timestamp_str, pattern)
        except ValueError:
            continue

    # Try ISO format as fallback
    try:
        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    logger.warning(f"Could not parse timestamp: {timestamp_str}")
    return None


def _extract_text_from_tag(tag: Tag) -> str:
    """
    Extract text content from a BeautifulSoup tag, preserving formatting.

    Args:
        tag: BeautifulSoup tag to extract text from.

    Returns:
        Extracted text content.
    """
    text_parts = []

    for child in tag.children:
        if isinstance(child, str):
            text_parts.append(child)
        elif hasattr(child, "get_text"):
            text_parts.append(child.get_text())

    return "".join(text_parts).strip()


def _extract_links_from_html(html_content: str) -> list[MessageLink]:
    """
    Extract links from HTML content.

    Args:
        html_content: HTML string to extract links from.

    Returns:
        List of MessageLink objects.
    """
    links = []
    soup = BeautifulSoup(html_content, "html.parser")

    for a_tag in soup.find_all("a", href=True):
        url = a_tag.get("href", "").strip()
        if url:
            text = a_tag.get_text(strip=True) or url
            # Extract domain
            domain = None
            if url.startswith("http://") or url.startswith("https://"):
                try:
                    domain = url.split("//")[1].split("/")[0].split(":")[0]
                except IndexError:
                    pass

            links.append(MessageLink(url=url, text=text if text != url else None, domain=domain))

    return links


def _parse_message_element(
    message_div: Tag,
    source_file: str,
) -> Message | None:
    """
    Parse a single message element from Telegram HTML export.

    Args:
        message_div: BeautifulSoup tag representing a message.
        source_file: Path to the source file this message came from.

    Returns:
        Message object or None if parsing fails.

    Raises:
        MessageParseError: If critical message data is missing.
    """
    try:
        # Extract message ID
        message_id = message_div.get("id", "")
        if not message_id:
            # Try to extract from class or other attributes
            classes = message_div.get("class", [])
            for cls in classes:
                if cls.startswith("message-"):
                    message_id = cls.replace("message-", "")
                    break

        if not message_id:
            raise MessageParseError(
                "Cannot determine message ID",
                file_path=source_file,
            )

        # Extract timestamp - look for date div/span
        timestamp_elem = message_div.find(
            ["div", "span"],
            class_=lambda x: x and ("date" in x.lower() if isinstance(x, str) else False),
        )

        timestamp = None
        if timestamp_elem:
            timestamp_str = timestamp_elem.get("datetime", "") or _extract_text_from_tag(timestamp_elem)
            timestamp = _parse_timestamp(timestamp_str)

        if not timestamp:
            # Try to find any time-like element
            time_elem = message_div.find("time")
            if time_elem:
                timestamp_str = time_elem.get("datetime", "") or _extract_text_from_tag(time_elem)
                timestamp = _parse_timestamp(timestamp_str)

        if not timestamp:
            raise MessageParseError(
                f"Cannot parse timestamp for message {message_id}",
                message_id=message_id,
                file_path=source_file,
            )

        # Extract sender information
        sender_name_elem = message_div.find(
            ["div", "span"],
            class_=lambda x: x and ("from" in x.lower() or "sender" in x.lower() if isinstance(x, str) else False),
        )

        sender_display_name = None
        if sender_name_elem:
            sender_display_name = _extract_text_from_tag(sender_name_elem)

        # Extract message text/content
        text_content = None
        body_elem = message_div.find(
            ["div"],
            class_=lambda x: x and ("text" in x.lower() or "body" in x.lower() if isinstance(x, str) else False),
        )

        if body_elem:
            text_content = _extract_text_from_tag(body_elem)
        else:
            # Try to get text from message content directly
            text_elems = message_div.find_all(
                ["p", "div"],
                recursive=False,
            )
            if text_elems:
                text_content = "\n".join(_extract_text_from_tag(elem) for elem in text_elems)

        # Determine message type
        message_type = "text"
        classes = message_div.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        
        # Check for service class
        if any("service" in cls.lower() for cls in classes):
            message_type = "service"
        elif message_div.find(["img", "video", "audio"]):
            message_type = "media"

        # Extract attachments
        attachments = []
        for img in message_div.find_all("img", src=True):
            src = img.get("src", "")
            if src:
                attachments.append(
                    MessageAttachment(
                        type="photo",
                        file_name=Path(src).name if src else None,
                        file_path=src,
                    )
                )

        # Extract links
        links = []
        if text_content:
            links = _extract_links_from_html(str(message_div))

        # Extract reply-to information
        reply_to_id = None
        reply_elem = message_div.find(
            class_=lambda x: x and ("reply" in x.lower() if isinstance(x, str) else False),
        )
        if reply_elem:
            # Try to extract replied message ID
            reply_link = reply_elem.find("a", href=True)
            if reply_link:
                href = reply_link.get("href", "")
                # Extract message ID from link using multiple patterns
                for pattern in [r"#message(\d+)", r"message(\d+)", r"#msg(\d+)", r"msg(\d+)"]:
                    match = re.search(pattern, href)
                    if match:
                        reply_to_id = match.group(1)
                        break

        # Extract forwarded-from information
        forwarded_from = None
        fwd_elem = message_div.find(
            class_=lambda x: x and ("forward" in x.lower() if isinstance(x, str) else False),
        )
        if fwd_elem:
            forwarded_from = _extract_text_from_tag(fwd_elem)

        # Extract edit timestamp
        edited_at = None
        edit_elem = message_div.find(
            class_=lambda x: x and ("edited" in x.lower() if isinstance(x, str) else False),
        )
        if edit_elem:
            edit_str = _extract_text_from_tag(edit_elem)
            # Remove "edited" prefix if present
            edit_str = re.sub(r"edited\s*", "", edit_str, flags=re.IGNORECASE)
            edited_at = _parse_timestamp(edit_str)

        # Extract reactions (if present in export)
        reactions = []
        reaction_elems = message_div.find_all(
            class_=lambda x: x and ("reaction" in x.lower() if isinstance(x, str) else False),
        )
        for reaction_elem in reaction_elems:
            emoji = reaction_elem.get("data-emoji", "") or _extract_text_from_tag(reaction_elem)
            if emoji:
                count_str = reaction_elem.get("data-count", "1")
                try:
                    count = int(count_str)
                except ValueError:
                    count = 1
                reactions.append(MessageReaction(emoji=emoji, count=count))

        return Message(
            message_id=message_id,
            timestamp=timestamp,
            sender_id=None,  # Not reliably available in HTML exports
            sender_display_name=sender_display_name,
            message_type=message_type,
            text_content=text_content,
            reply_to_id=reply_to_id,
            forwarded_from=forwarded_from,
            edited_at=edited_at,
            reactions=reactions,
            attachments=attachments,
            links=links,
            raw_metadata={},
            source_file=source_file,
        )

    except MessageParseError:
        raise
    except Exception as e:
        raise MessageParseError(
            f"Failed to parse message: {e}",
            file_path=source_file,
        ) from e


def _extract_chat_info(soup: BeautifulSoup, source_file: str) -> dict[str, Any]:
    """
    Extract chat-level information from the HTML document.

    Args:
        soup: Parsed BeautifulSoup document.
        source_file: Source file path.

    Returns:
        Dictionary with chat information.
    """
    chat_info = {"title": "Unknown Chat", "chat_type": "unknown"}

    # Try to find chat title in various locations
    title_elem = soup.find(["h1", "h2", "h3"])
    if title_elem:
        chat_info["title"] = _extract_text_from_tag(title_elem)

    # Try to find in meta tags
    meta_title = soup.find("meta", attrs={"name": "title"})
    if meta_title and meta_title.get("content"):
        chat_info["title"] = meta_title.get("content", "")

    # Try to determine chat type from context
    if soup.find(class_=lambda x: x and "channel" in str(x).lower() if x else False):
        chat_info["chat_type"] = "channel"
    elif soup.find(class_=lambda x: x and "group" in str(x).lower() if x else False):
        chat_info["chat_type"] = "group"

    return chat_info


def parse_telegram_html(
    file_path: str,
) -> Generator[tuple[Message | None, dict[str, Any], list[Participant]], None, None]:
    """
    Parse a Telegram HTML export file and yield parsed data.

    This is a generator function that yields tuples of:
    - Message object (or None for non-message elements)
    - Chat info dictionary
    - List of participants discovered so far

    Args:
        file_path: Path to the Telegram HTML export file.

    Yields:
        Tuples of (Message, chat_info, participants).

    Raises:
        MalformedHTMLError: If the HTML is severely malformed.
    """
    path = Path(file_path)

    if not path.exists():
        raise MalformedHTMLError(f"File not found: {file_path}", file_path=file_path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        raise MalformedHTMLError(
            f"Failed to read file with UTF-8 encoding: {e}",
            file_path=file_path,
        ) from e

    try:
        soup = BeautifulSoup(content, "html.parser")
    except Exception as e:
        raise MalformedHTMLError(
            f"Failed to parse HTML: {e}",
            file_path=file_path,
        ) from e

    # Extract chat info once
    chat_info = _extract_chat_info(soup, file_path)
    participants: dict[str, Participant] = {}

    # Find all message elements
    # Telegram typically uses div elements with message-related classes
    message_elements = soup.find_all(
        ["div"],
        class_=lambda x: x and (
            "message" in str(x).lower() or
            "msg" in str(x).lower()
        ) if x else False,
    )

    if not message_elements:
        # Try alternative selectors
        message_elements = soup.find_all(id=lambda x: x and x.startswith("message") if x else False)

    for msg_elem in message_elements:
        try:
            message = _parse_message_element(msg_elem, file_path)
            if message:
                # Track participant
                if message.sender_display_name:
                    if message.sender_display_name not in participants:
                        participants[message.sender_display_name] = Participant(
                            display_name=message.sender_display_name,
                        )

                yield (message, chat_info, list(participants.values()))
        except MessageParseError as e:
            logger.warning(f"Skipping malformed message: {e}")
            yield (None, chat_info, list(participants.values()))
        except Exception as e:
            logger.warning(f"Unexpected error parsing message: {e}")
            yield (None, chat_info, list(participants.values()))


def parse_export_files(
    file_paths: list[str],
) -> Generator[tuple[Message | None, dict[str, Any], list[Participant]], None, None]:
    """
    Parse multiple Telegram export files.

    Args:
        file_paths: List of paths to Telegram HTML export files.

    Yields:
        Tuples of (Message, chat_info, participants).
    """
    for file_path in file_paths:
        logger.info(f"Parsing file: {file_path}")
        yield from parse_telegram_html(file_path)
