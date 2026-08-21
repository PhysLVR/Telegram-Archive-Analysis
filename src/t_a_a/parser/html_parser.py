"""HTML parser for Telegram export files.

This module implements a streaming parser for Telegram Desktop HTML exports.
It uses Python's built-in HTMLParser to process large files incrementally,
avoiding loading the entire document into memory.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Iterator, Tuple, Any
from html.parser import HTMLParser

from t_a_a.parser.import_result import ImportResult, Message, Chat, Participant
from t_a_a.parser.exceptions import InvalidExportFormatError, ParseWarning


def parse_telegram_html(file_path: Path) -> ImportResult:
    """
    Parse a Telegram HTML export file and extract messages, participants, and chat info.

    Uses streaming parsing to handle large files efficiently.

    Args:
        file_path: Path to the HTML export file

    Returns:
        ImportResult containing parsed data

    Raises:
        InvalidExportFormatError: If the file format is not recognized as a Telegram export
    """
    parser = TelegramHTMLStreamParser()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # Process in chunks to avoid loading entire file
        while chunk := f.read(8192):
            parser.feed(chunk)
    
    parser.close()
    
    if not parser.is_valid_export:
        raise InvalidExportFormatError(f"File {file_path} does not appear to be a valid Telegram export")
    
    return ImportResult(
        chat=parser.chat_info,
        participants=set(parser.participants.values()),
        messages=parser.messages
    )


def parse_telegram_html_stream(file_path: Path) -> Iterator[Message]:
    """
    Stream messages from a Telegram HTML export file.
    
    This generator yields messages one by one without loading the entire file.
    
    Args:
        file_path: Path to the HTML export file
        
    Yields:
        Message objects
        
    Raises:
        InvalidExportFormatError: If the file format is not recognized
    """
    parser = TelegramHTMLStreamParser()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        while chunk := f.read(8192):
            parser.feed(chunk)
            # Yield messages as they are completed
            while parser.completed_messages:
                yield parser.completed_messages.pop(0)
    
    parser.close()
    
    # Yield any remaining messages
    while parser.completed_messages:
        yield parser.completed_messages.pop(0)
    
    if not parser.is_valid_export:
        raise InvalidExportFormatError(f"File {file_path} does not appear to be a valid Telegram export")


class TelegramHTMLStreamParser(HTMLParser):
    """Streaming HTML parser for Telegram Desktop exports."""
    
    def __init__(self):
        super().__init__()
        
        # State tracking
        self.is_valid_export = False
        self.chat_info = Chat(name="Unknown Chat", description="", type="group")
        self.participants: Dict[str, Participant] = {}
        self.messages: List[Message] = []
        self.completed_messages: List[Message] = []
        
        # Current parsing context
        self._in_message = False
        self._message_depth = 0
        self._current_message_data: Dict[str, Any] = {}
        self._tag_stack: List[str] = []
        self._text_buffer: List[str] = []
        
        # Specific element tracking
        self._in_from_name = False
        self._in_date = False
        self._in_text = False
        self._in_reply_to = False
        self._in_forwarded = False
        self._in_media_wrap = False
        self._in_reaction = False
        
        # Temporary storage for current element
        self._current_from_name = ""
        self._current_timestamp_str = ""
        self._current_reply_id: Optional[int] = None
        self._current_media_urls: List[str] = []
        self._current_links: List[str] = []
        self._forwarded_from_name: Optional[str] = None
        
        # Store text for current message separately
        self._current_text_parts: List[str] = []
        
    def feed(self, data: str) -> None:
        """Feed data to the parser."""
        super().feed(data)
    
    def close(self) -> None:
        """Finish parsing and finalize any pending message."""
        super().close()
        self._finalize_current_message()
    
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Handle start tags."""
        self._tag_stack.append(tag)
        attrs_dict = {k: v for k, v in attrs}
        
        # Check for Telegram export validation
        if tag == 'title':
            self.is_valid_export = True
        
        # Message container detection
        if tag == 'div':
            class_attr = attrs_dict.get('class', '')
            classes = class_attr.split()
            
            # Check for message start (supports both "message" and "message default" formats)
            if 'message' in classes:
                self._start_message(attrs_dict, classes)
                self._message_depth += 1
            
            # Service message detection
            if 'service' in classes:
                self._in_service_message = True
            
            # From name detection (supports both "from_name" and legacy formats)
            if 'from_name' in classes:
                self._in_from_name = True
                self._current_from_name = ""
            
            # Date/time detection (supports both "date pull_right" and simple "date")
            if 'date' in classes:
                # Check for title attribute with full timestamp
                if 'title' in attrs_dict:
                    self._current_timestamp_str = attrs_dict['title']
                else:
                    self._in_date = True
                    self._current_timestamp_str = ""
            
            # Reply detection
            if 'reply_to' in classes:
                self._in_reply_to = True
            
            # Forwarded message detection
            if 'forwarded' in classes and 'body' in classes:
                self._in_forwarded = True
            
            # Media wrap detection
            if 'media_wrap' in classes:
                self._in_media_wrap = True
            
            # Text content detection
            if 'text' in classes and not self._in_reaction:
                self._in_text = True
        
        # Link detection
        elif tag == 'a':
            href = attrs_dict.get('href', '')
            
            # Reply link extraction
            if self._in_reply_to and 'go_to_message' in href:
                # Extract message ID from href like "#go_to_message52"
                match = re.search(r'go_to_message(\d+)', href)
                if match:
                    self._current_reply_id = int(match.group(1))
            
            # Media link extraction
            if self._in_media_wrap:
                if href and not href.startswith('#'):
                    self._current_media_urls.append(href)
            
            # Regular link extraction (only if not in media/reply context)
            elif href.startswith(('http://', 'https://')) and not self._in_reply_to:
                self._current_links.append(href)
        
        # Image detection for media
        elif tag == 'img':
            if self._in_media_wrap:
                src = attrs_dict.get('src', '')
                if src:
                    # Store thumbnail or media reference
                    if not any(src in url for url in self._current_media_urls):
                        self._current_media_urls.append(src)
        
        # Reaction detection to avoid contaminating text
        elif tag == 'span':
            class_attr = attrs_dict.get('class', '')
            if 'reaction' in class_attr.split() or 'reactions' in class_attr.split():
                self._in_reaction = True
    
    def handle_endtag(self, tag: str) -> None:
        """Handle end tags."""
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        
        # Finalize message on closing div if we were in a message
        if tag == 'div':
            if self._in_from_name:
                self._in_from_name = False
            
            if self._in_text:
                self._in_text = False
            
            if self._in_media_wrap:
                self._in_media_wrap = False
            
            if self._in_reply_to:
                self._in_reply_to = False
            
            if self._in_forwarded:
                self._in_forwarded = False
            
            if self._in_reaction:
                self._in_reaction = False
            
            # Check if we're closing a message container
            if self._in_message and self._message_depth > 0:
                self._message_depth -= 1
                if self._message_depth == 0:
                    self._finalize_current_message()
    
    def handle_data(self, data: str) -> None:
        """Handle text data."""
        if self._in_from_name:
            self._current_from_name += data
        
        if self._in_date:
            self._current_timestamp_str += data
        
        if self._in_text and not self._in_reaction:
            self._current_text_parts.append(data)
        
        # Handle text in forwarded section
        if self._in_forwarded and self._in_from_name:
            self._forwarded_from_name = data.strip()
    
    def _start_message(self, attrs_dict: Dict[str, str], classes: List[str]) -> None:
        """Initialize parsing of a new message."""
        self._in_message = True
        self._current_message_data = {
            'id': None,
            'timestamp': None,
            'sender_name': None,
            'text': '',
            'media': [],
            'links': [],
            'reply_to_id': None,
            'is_service': False,
            'forwarded_from': None
        }
        self._current_text_parts = []
        self._current_media_urls = []
        self._current_links = []
        self._current_reply_id = None
        self._forwarded_from_name = None
        self._current_timestamp_str = ""
        self._current_from_name = ""
        
        # Extract message ID
        msg_id = attrs_dict.get('id', '')
        if msg_id:
            # Handle both "message6" and "message-999844480" formats
            match = re.search(r'message-?(\d+)', msg_id)
            if match:
                self._current_message_data['id'] = int(match.group(1))
        
        # Check if service message
        if 'service' in classes:
            self._current_message_data['is_service'] = True
    
    def _finalize_current_message(self) -> None:
        """Finalize the current message and add to results."""
        if not self._in_message:
            return
        
        # Get or create participant
        sender_name = self._current_from_name.strip() if self._current_from_name else "Unknown"
        if not sender_name:
            sender_name = "Unknown"
        
        if sender_name not in self.participants:
            # Use hash of name as ID for stability
            participant_id = abs(hash(sender_name)) % (10**9)
            self.participants[sender_name] = Participant(
                id=participant_id,
                name=sender_name
            )
        
        sender = self.participants[sender_name]
        
        # Parse timestamp
        timestamp = self._parse_timestamp(self._current_timestamp_str)
        
        # Extract text content
        text_content = ''.join(self._current_text_parts).strip()
        
        # Determine message type
        msg_type = 'text'
        if self._current_message_data.get('is_service'):
            msg_type = 'service'
        elif self._current_media_urls:
            msg_type = 'media'
        
        # Create message object
        message = Message(
            id=self._current_message_data.get('id') or abs(hash(text_content)) % (10**8),
            timestamp=timestamp,
            sender=sender,
            type=msg_type,
            text=text_content,
            media=self._current_media_urls.copy(),
            links=self._current_links.copy(),
            reply_to_id=self._current_reply_id,
            edited_at=None,  # TODO: Implement edit timestamp parsing
            service_info={'forwarded_from': self._forwarded_from_name} if self._forwarded_from_name else None
        )
        
        self.messages.append(message)
        self.completed_messages.append(message)
        
        # Reset state
        self._in_message = False
        self._in_service_message = False
        self._current_message_data = {}
        self._current_text_parts = []
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse Telegram timestamp string with timezone support."""
        if not timestamp_str:
            return None
        
        # Telegram format: "13.02.2025 01:04:32 UTC+03:30"
        # Extract components using regex
        pattern = r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s+UTC([+-])(\d{2}):(\d{2})'
        match = re.match(pattern, timestamp_str)
        
        if not match:
            # Try alternative formats without timezone
            # Format: "Jan 15, 2024, 10:30 AM"
            alt_pattern = r'(\w+)\s+(\d+),\s+(\d{4}),\s+(\d+):(\d+)\s*(AM|PM)?'
            alt_match = re.match(alt_pattern, timestamp_str, re.IGNORECASE)
            if alt_match:
                month_str, day, year, hour, minute, ampm = alt_match.groups()
                months = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                         'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
                month = months.get(month_str.lower()[:3], 1)
                hour_int = int(hour)
                if ampm:
                    if ampm.upper() == 'PM' and hour_int != 12:
                        hour_int += 12
                    elif ampm.upper() == 'AM' and hour_int == 12:
                        hour_int = 0
                return datetime(int(year), month, int(day), hour_int, int(minute))
            
            # Try DD.MM.YY HH:MM format
            alt_pattern2 = r'(\d{2})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})'
            alt_match2 = re.match(alt_pattern2, timestamp_str)
            if alt_match2:
                day, month, year, hour, minute = map(int, alt_match2.groups())
                # Assume 20xx for two-digit years
                year = 2000 + year if year < 50 else 1900 + year
                return datetime(year, month, day, hour, minute)
            
            return None
        
        day, month, year, hour, minute, second, tz_sign, tz_hours, tz_mins = match.groups()
        
        # Create naive datetime
        dt = datetime(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second)
        )
        
        # Apply timezone offset to convert to UTC
        offset_minutes = int(tz_hours) * 60 + int(tz_mins)
        if tz_sign == '+':
            dt = dt - timedelta(minutes=offset_minutes)
        else:
            dt = dt + timedelta(minutes=offset_minutes)
        
        return dt


# Legacy functions for backward compatibility
def _extract_links_from_html(html_content: str) -> List[str]:
    """Legacy function - extract links from HTML content."""
    links = []
    pattern = r'href=["\'](https?://[^"\']+)["\']'
    matches = re.findall(pattern, html_content)
    return list(set(matches))


def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Legacy function - use TelegramHTMLStreamParser._parse_timestamp instead."""
    parser = TelegramHTMLStreamParser()
    return parser._parse_timestamp(timestamp_str)
