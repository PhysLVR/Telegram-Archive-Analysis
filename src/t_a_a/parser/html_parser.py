"""HTML parser for Telegram export files.

This module implements a streaming parser for Telegram Desktop HTML exports.
It uses Python's built-in HTMLParser to process large files incrementally,
avoiding loading the entire document into memory or building a DOM.

Public API:
    parse_telegram_html: parse a single export file, yielding
        ``(message, chat, participants)`` tuples as messages complete.
    parse_telegram_html_stream: genuinely streaming variant that yields
        only completed ``Message`` objects, releasing parser state as it
        goes and never retaining the full message list.
    parse_export_files: parse several export files (e.g. a multi-part
        export) in sequence, yielding the same tuples as
        ``parse_telegram_html``.
"""

from __future__ import annotations

import re
import warnings
from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Deque, Iterable, Iterator, Optional

from t_a_a.models.domain import (
    Chat,
    Message,
    MessageAttachment,
    MessageLink,
    MessageReaction,
    Participant,
)
from t_a_a.parser.exceptions import InvalidExportFormatError, ParseWarning

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# Real Telegram Desktop timestamp, e.g. "13.02.2025 01:04:32 UTC+03:30"
_TZ_TIMESTAMP_RE = re.compile(
    r"^(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\s+"
    r"UTC(?P<sign>[+-])(?P<tz_h>\d{2}):(?P<tz_m>\d{2})$"
)

# Legacy/alternate formats retained for backward compatibility with the
# existing fixtures and tests (naive datetimes, no timezone information).
_US_TIMESTAMP_RE = re.compile(
    r"^(?P<month>\w+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4}),\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>AM|PM)?$",
    re.IGNORECASE,
)
_EUROPEAN_TIMESTAMP_RE = re.compile(
    r"^(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?$"
)
_EUROPEAN_SHORT_YEAR_RE = re.compile(
    r"^(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2})$"
)
_ISO_TIMESTAMP_RE = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[T ]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Reply targets: real exports use href="#go_to_message52"; some exports
# (and our own basic fixtures) link to "other_file.html#message100".
_REPLY_ID_RE = re.compile(r"go_to_message(\d+)")
_REPLY_ID_FALLBACK_RE = re.compile(r"#message(\d+)")

# "edited Jul 10, 2024, 3:05 PM" / "edited at 3:15 PM"
_EDITED_PREFIX_RE = re.compile(r"^edited\s+(?:at\s+)?(.+)$", re.IGNORECASE)

# A bare time with no date, e.g. "3:15 PM" -- used when an "edited at ..."
# marker gives only a time, which real Telegram Desktop exports do when
# the edit happened the same day as the original message.
_BARE_TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>AM|PM)?$", re.IGNORECASE
)

_LINK_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _extract_domain(url: str) -> Optional[str]:
    """Best-effort domain extraction without pulling in urllib for a one-liner."""
    match = re.match(r"^https?://([^/]+)", url)
    if not match:
        return None
    host = match.group(1)
    # Strip credentials/port if present.
    host = host.split("@")[-1].split(":")[0]
    return host or None


def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse a Telegram timestamp string.

    Always returns a **timezone-aware** ``datetime`` so callers can safely
    compare / sort timestamps across files.

    * Real Telegram Desktop format
      (``title="DD.MM.YYYY HH:MM:SS UTC±HH:MM"``) keeps the explicit offset.
    * Legacy formats without timezone information (fixtures and older
      exports) are treated as UTC. No conversion to the machine's local
      timezone is ever performed.
    """
    if not timestamp_str:
        return None

    text = timestamp_str.strip()

    match = _TZ_TIMESTAMP_RE.match(text)
    if match:
        g = match.groupdict()
        offset = timedelta(hours=int(g["tz_h"]), minutes=int(g["tz_m"]))
        if g["sign"] == "-":
            offset = -offset
        tz = timezone(offset)
        return datetime(
            int(g["year"]), int(g["month"]), int(g["day"]),
            int(g["hour"]), int(g["minute"]), int(g["second"]),
            tzinfo=tz,
        )

    # All legacy / fallback paths below attach UTC so every returned value
    # is timezone-aware and comparable.
    match = _US_TIMESTAMP_RE.match(text)
    if match:
        g = match.groupdict()
        month = _MONTHS.get(g["month"].lower()[:3])
        if month is None:
            return None
        hour = int(g["hour"])
        if g["ampm"]:
            if g["ampm"].upper() == "PM" and hour != 12:
                hour += 12
            elif g["ampm"].upper() == "AM" and hour == 12:
                hour = 0
        return datetime(
            int(g["year"]), month, int(g["day"]), hour, int(g["minute"]),
            tzinfo=timezone.utc,
        )

    match = _ISO_TIMESTAMP_RE.match(text)
    if match:
        g = match.groupdict()
        return datetime(
            int(g["year"]), int(g["month"]), int(g["day"]),
            int(g["hour"]), int(g["minute"]), int(g["second"] or 0),
            tzinfo=timezone.utc,
        )

    match = _EUROPEAN_TIMESTAMP_RE.match(text)
    if match:
        g = match.groupdict()
        return datetime(
            int(g["year"]), int(g["month"]), int(g["day"]),
            int(g["hour"]), int(g["minute"]), int(g["second"] or 0),
            tzinfo=timezone.utc,
        )

    match = _EUROPEAN_SHORT_YEAR_RE.match(text)
    if match:
        g = match.groupdict()
        year = int(g["year"])
        year = 2000 + year if year < 50 else 1900 + year
        return datetime(
            year, int(g["month"]), int(g["day"]), int(g["hour"]), int(g["minute"]),
            tzinfo=timezone.utc,
        )

    return None


def _extract_links_from_html(html_content: str) -> list[MessageLink]:
    """Extract links from a raw HTML snippet (legacy helper retained for tests).

    Parses ``<a href="...">text</a>`` tags without building a DOM.
    """
    links: list[MessageLink] = []
    seen: set[str] = set()
    for match in re.finditer(
        r'<a\s+[^>]*href=["\'](?P<url>[^"\']+)["\'][^>]*>(?P<text>.*?)</a>',
        html_content,
        re.IGNORECASE | re.DOTALL,
    ):
        url = match.group("url")
        if not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        text = re.sub(r"<[^>]+>", "", match.group("text")).strip()
        links.append(MessageLink(url=url, text=text or None, domain=_extract_domain(url)))
    return links


# ---------------------------------------------------------------------------
# Parse context stack
# ---------------------------------------------------------------------------

class _Frame:
    """A single open-element frame on the parser's context stack.

    Using a stack (rather than a handful of independent booleans) means
    nested structures can never corrupt unrelated parent state: entering
    a nested ``<div>`` pushes a new frame, and only popping that exact
    frame on its matching close tag can change what "context" we are in.
    """

    __slots__ = ("tag", "kind", "is_message_root")

    def __init__(self, tag: str, kind: Optional[str], is_message_root: bool = False) -> None:
        self.tag = tag
        self.kind = kind  # e.g. "message", "text", "reply", "forwarded", "media", "reaction", "from_name", "date", "edited"
        self.is_message_root = is_message_root


class TelegramHTMLStreamParser(HTMLParser):
    """Streaming HTML parser for Telegram Desktop exports.

    Correctness properties this parser maintains:
      * A message is finalized only when its own root ``.message`` element
        closes -- nested ``<div>`` elements never trigger finalization.
        "joined" messages are still separate messages (they get their own
        root ``.message`` element and are handled identically).
      * Context (text / reply / forwarded / media / reaction / ...) is
        tracked via a stack of frames, not independent booleans, so nested
        structures (e.g. a reaction block inside a message, or a nested
        div inside forwarded content) cannot leak into unrelated state.
      * No DOM is built; only a bounded stack and small per-message
        buffers are kept in memory.
    """

    def __init__(self, *, source_file: Optional[str] = None) -> None:
        super().__init__(convert_charrefs=True)

        self.is_valid_export = False
        self._title_text = ""
        self._chat_title: Optional[str] = None
        self._saw_message_element = False

        self.chat_info = Chat(chat_id="unknown", title="Unknown Chat", chat_type="group")

        self.participants: dict[str, Participant] = {}
        # Bounded queue of completed messages ready to be handed to the
        # caller; using a deque (not list.pop(0)) keeps release O(1).
        self.completed_messages: Deque[Optional[Message]] = deque()

        self._source_file = source_file

        # Context stack. Each entry is a _Frame.
        self._stack: list[_Frame] = []

        # State for the message currently being built (only meaningful
        # while a message frame is on the stack).
        self._reset_message_state()

    # -- lifecycle -----------------------------------------------------

    def close(self) -> None:
        super().close()
        # Safety net: if the stream ended with an unclosed <title> (e.g. a
        # truncated file), still check whatever title text was captured
        # rather than leaving validity permanently unresolved.
        self._update_validity()
        # If the stream ended mid-message (truncated/malformed export),
        # do not silently fabricate a message from partial state.
        if self._in_message():
            warnings.warn(
                "Telegram export ended with an unclosed message element; "
                "discarding incomplete message.",
                ParseWarning,
                stacklevel=2,
            )
        self._stack.clear()

    # -- helpers ---------------------------------------------------------

    def _in_message(self) -> bool:
        return any(f.is_message_root for f in self._stack)

    def _top_kind(self) -> Optional[str]:
        return self._stack[-1].kind if self._stack else None

    def _nearest_kind(self) -> Optional[str]:
        """The nearest enclosing meaningful frame kind, skipping plain
        inline formatting tags (e.g. <b>, <i>, <code>, unclassed <span>)
        that carry no kind of their own. This lets text nested inside
        inline formatting still be attributed to its actual context
        (message text, from_name, etc.) without those tags needing to be
        special-cased individually.
        """
        for frame in reversed(self._stack):
            if frame.kind is not None:
                return frame.kind
        return None

    def _has_kind(self, kind: str) -> bool:
        """True if `kind` is anywhere on the current context stack."""
        return any(f.kind == kind for f in self._stack)

    def _update_validity(self) -> None:
        # Require real Telegram-specific structural evidence rather than
        # the mere presence of a <title> element, which is true of
        # virtually any HTML document. Either signal alone is sufficient:
        # the page title Telegram Desktop writes ("Telegram Chat Export" /
        # "Telegram Web"), or an actual .message element having been seen.
        title_says_telegram = "telegram" in self._title_text.lower()
        if title_says_telegram or self._saw_message_element:
            self.is_valid_export = True

    def _update_chat_info(self) -> None:
        title = self._chat_title
        if not title:
            return
        # Telegram's HTML export never embeds a numeric chat id in the
        # markup itself (only the companion result.json does, which this
        # parser does not read). Derive a stable id from the title so
        # repeated parses of the same export are consistent, rather than
        # leaving the placeholder "unknown" or inventing a random one.
        chat_id = self.chat_info.chat_id
        if chat_id == "unknown":
            chat_id = title
        self.chat_info = Chat(
            chat_id=chat_id,
            title=title,
            chat_type=self.chat_info.chat_type,
            source_files=self.chat_info.source_files,
        )

    def _reset_message_state(self) -> None:
        self._msg_id: Optional[str] = None
        self._msg_is_service = False
        self._msg_timestamp_str: str = ""
        self._msg_from_name: str = ""
        self._msg_text_parts: list[str] = []
        self._msg_reply_id: Optional[str] = None
        self._msg_forwarded_from: Optional[str] = None
        self._msg_attachments: list[MessageAttachment] = []
        self._msg_links: list[MessageLink] = []
        self._msg_reactions: list[MessageReaction] = []
        self._msg_edited_str: Optional[str] = None
        self._msg_had_media_container = False
        # Per-reaction-item scratch state, reset whenever a new
        # .reaction/.reaction_item element opens.
        self._reaction_emoji: str = ""
        self._reaction_count_str: str = ""

    # -- HTMLParser overrides --------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_dict: dict[str, str] = {k: v for k, v in attrs if v is not None}
        classes = attrs_dict.get("class", "").split()

        kind: Optional[str] = None
        is_message_root = False

        if tag == "title":
            kind = "title"
        elif tag == "meta" and attrs_dict.get("name") == "title":
            content = attrs_dict.get("content")
            if content:
                self._chat_title = content
                self._update_chat_info()
        elif tag == "h1" and self._chat_title is None:
            kind = "h1"

        # Media wrapper classes appear on different tags depending on
        # export version: some Telegram Desktop builds render
        # sticker_wrap/animated_wrap/photo_wrap/video_file_wrap as a plain
        # <div>, others as an <a href="..."> pointing at the original file
        # (with a thumbnail <img> nested inside). Detect these by class
        # regardless of tag so both variants are handled identically, and
        # capture the wrapper's own href as the *original* media reference
        # (never confused with the nested thumbnail image).
        if tag in ("div", "a") and "sticker_wrap" in classes:
            kind = "media"
            self._msg_had_media_container = True
            if not self._has_kind("reaction"):
                href = attrs_dict.get("href")
                self._msg_attachments.append(
                    MessageAttachment(type="sticker", file_path=href or None)
                )
        elif tag in ("div", "a") and "animated_wrap" in classes:
            kind = "media"
            self._msg_had_media_container = True
            if not self._has_kind("reaction"):
                href = attrs_dict.get("href")
                self._msg_attachments.append(
                    MessageAttachment(type="animated", file_path=href or None)
                )
        elif tag in ("div", "a") and "video_file_wrap" in classes:
            kind = "media"
            self._msg_had_media_container = True
            if not self._has_kind("reaction"):
                href = attrs_dict.get("href")
                self._msg_attachments.append(
                    MessageAttachment(type="video", file_path=href or None)
                )
        elif tag in ("div", "a") and "photo_wrap" in classes:
            kind = "media"
            self._msg_had_media_container = True
            if not self._has_kind("reaction"):
                href = attrs_dict.get("href")
                self._msg_attachments.append(
                    MessageAttachment(type="photo", file_path=href or None)
                )
        elif tag == "div":
            if "message" in classes:
                # A new root .message element -- together with the page
                # title this is the strongest evidence we're looking at a
                # real Telegram export, not merely any HTML document with
                # a <title> tag.
                self._saw_message_element = True
                self._update_validity()
                # If we somehow see this while already inside a message
                # (malformed nesting), finalize/discard the prior one
                # defensively rather than corrupting state, then start fresh.
                if self._in_message():
                    warnings.warn(
                        "Encountered a nested .message root before the "
                        "previous message closed; finalizing the previous "
                        "message early.",
                        ParseWarning,
                        stacklevel=2,
                    )
                    self._finalize_current_message()
                self._reset_message_state()
                self._msg_is_service = "service" in classes
                msg_id = attrs_dict.get("id")
                self._msg_id = msg_id if msg_id else None
                kind = "message"
                is_message_root = True
            elif "from_name" in classes:
                kind = "from_name"
            elif "date" in classes:
                title = attrs_dict.get("title")
                if title:
                    # The title attribute carries the authoritative,
                    # full-precision, timezone-qualified timestamp. Use it
                    # as-is and do not treat this element's visible text
                    # (e.g. "01:04") as further timestamp content.
                    self._msg_timestamp_str = title
                    kind = None
                else:
                    kind = "date"
            elif "reply_to" in classes or classes == ["reply"] or "reply" in classes:
                kind = "reply"
            elif "forwarded" in classes and "body" in classes:
                kind = "forwarded"
            elif "media_wrap" in classes:
                kind = "media"
                self._msg_had_media_container = True
            elif "reactions" in classes:
                kind = "reaction"
            elif "reaction" in classes:
                kind = "reaction_item"
                self._reaction_emoji = ""
                self._reaction_count_str = ""
            elif "text" in classes and not self._has_kind("reaction"):
                kind = "text"
            elif "edited" in classes:
                kind = "edited"

        elif tag == "span":
            if "reactions" in classes:
                kind = "reaction"
            elif "reaction" in classes:
                kind = "reaction_item"
                self._reaction_emoji = ""
                self._reaction_count_str = ""
            elif "emoji" in classes and self._has_kind("reaction"):
                kind = "reaction_emoji"
            elif "count" in classes and self._has_kind("reaction"):
                kind = "reaction_count"
            elif "date" in classes and self._has_kind("forwarded"):
                # Forwarded-block date, e.g. inline <span class="date details">
                # inside .forwarded.body -- not the current message's own date.
                title = attrs_dict.get("title")
                if title:
                    pass  # forwarded date not currently surfaced by the domain model
            elif "edited" in classes:
                kind = "edited"

        elif tag == "a":
            href = attrs_dict.get("href", "")
            if self._has_kind("reaction"):
                pass  # reaction/button links never contribute text or links
            elif self._has_kind("reply"):
                self._extract_reply_id(href)
            elif self._has_kind("forwarded"):
                pass  # forwarded-subtree links are not the current message's links
            elif self._has_kind("media"):
                if href and not href.startswith("#"):
                    self._add_link_attachment(href)
            elif self._in_message() and href.startswith(("http://", "https://")):
                self._msg_links.append(
                    MessageLink(url=href, text=None, domain=_extract_domain(href))
                )
            elif self._in_message() and not self._has_kind("text") and href and not href.startswith("#"):
                # A bare local file link directly under the message body
                # (not inside .text, not an external link): treat as a
                # generic file/document attachment.
                self._add_link_attachment(href)

        elif tag == "img":
            if self._has_kind("reaction") or self._has_kind("forwarded"):
                pass
            elif self._has_kind("media"):
                src = attrs_dict.get("src")
                if src and self._msg_attachments:
                    # The wrapper (sticker/animated/photo/video/media_wrap)
                    # already recorded the attachment with its href as the
                    # original file; this <img> is the thumbnail, not a
                    # second original. Attach it to the existing entry
                    # rather than creating a duplicate.
                    last = self._msg_attachments[-1]
                    metadata = dict(last.metadata)
                    metadata.setdefault("thumbnail_path", src)
                    self._msg_attachments[-1] = replace(last, metadata=metadata)
                elif src and self._in_message():
                    # A bare <img> with no wrapper at all.
                    self._msg_attachments.append(
                        MessageAttachment(type="photo", file_path=src)
                    )

        elif tag == "video":
            if self._in_message() and not self._has_kind("reaction") and not self._has_kind("forwarded"):
                src = attrs_dict.get("src")
                if src:
                    self._msg_attachments.append(
                        MessageAttachment(type="video", file_path=src)
                    )

        elif tag == "br":
            if self._has_kind("text") and not self._has_kind("reaction") and not self._has_kind("forwarded"):
                self._msg_text_parts.append("\n")
            # <br> inside the forwarded subtree is intentionally ignored:
            # forwarded body text is not captured (see handle_data).

        self._stack.append(_Frame(tag=tag, kind=kind, is_message_root=is_message_root))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        # Self-closing tags (e.g. <br/>, <img .../>) never get a matching
        # handle_endtag, so route them through start-tag handling and then
        # immediately pop -- this keeps the stack balanced without ever
        # treating them as containers that could swallow later content.
        self.handle_starttag(tag, attrs)
        if self._stack:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        # Pop the innermost matching frame. HTML from real exports is not
        # always perfectly balanced; scan from the top for the nearest
        # frame with this tag rather than assuming stack[-1] matches, so a
        # stray/unexpected closing tag can't desynchronize tracking of
        # unrelated ancestors.
        idx = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                idx = i
                break
        if idx is None:
            return  # unmatched closing tag; ignore rather than corrupt state

        frame = self._stack[idx]
        del self._stack[idx:]

        if frame.kind == "reaction_item":
            self._finalize_reaction_item()
        elif frame.kind == "title":
            self._update_validity()
        elif frame.kind == "h1":
            self._update_chat_info()

        if frame.is_message_root:
            self._finalize_current_message()

    def handle_data(self, data: str) -> None:
        if not data:
            return

        nearest = self._nearest_kind()

        if self._has_kind("reaction"):
            # Only the specific emoji/count sub-elements of a reaction are
            # meaningful; any other text inside .reactions (e.g. userpic
            # tooltips) is discarded and never leaks into message text.
            if nearest == "reaction_emoji":
                self._reaction_emoji += data
            elif nearest == "reaction_count":
                self._reaction_count_str += data
            return

        if self._has_kind("forwarded"):
            if nearest == "from_name":
                self._msg_forwarded_from = ((self._msg_forwarded_from or "") + data)
            # Forwarded body text is intentionally not captured: the
            # domain model's forwarded_from field represents forwarded
            # *origin* (sender), not forwarded content, and the current
            # message's own .text (outside the forwarded subtree) is
            # captured normally below.
            return

        if nearest == "from_name":
            self._msg_from_name += data
        elif nearest == "date":
            self._msg_timestamp_str += data
        elif nearest == "text":
            self._msg_text_parts.append(data)
        elif nearest == "edited":
            self._msg_edited_str = (self._msg_edited_str or "") + data
        elif nearest == "reply":
            pass  # reply link text (e.g. quoted sender name) is not message text
        elif nearest == "title":
            self._title_text += data
        elif nearest == "h1":
            self._chat_title = (self._chat_title or "") + data

    # -- extraction helpers -----------------------------------------------

    def _extract_reply_id(self, href: str) -> None:
        match = _REPLY_ID_RE.search(href)
        if not match:
            match = _REPLY_ID_FALLBACK_RE.search(href)
        if match:
            self._msg_reply_id = match.group(1)

    def _add_link_attachment(self, href: str) -> None:
        # A generic file link inside a media wrapper (e.g. a document).
        self._msg_attachments.append(
            MessageAttachment(type="file", file_name=href.rsplit("/", 1)[-1], file_path=href)
        )

    def _finalize_reaction_item(self) -> None:
        emoji = self._reaction_emoji.strip()
        if not emoji:
            # Not a real reaction pill (e.g. a custom-emoji placeholder we
            # couldn't read, or an unrelated element that happened to match
            # class "reaction"); nothing usable to record.
            self._reaction_emoji = ""
            self._reaction_count_str = ""
            return
        count_str = self._reaction_count_str.strip()
        try:
            count = int(count_str) if count_str else 1
        except ValueError:
            count = 1
        self._msg_reactions.append(MessageReaction(emoji=emoji, count=count))
        self._reaction_emoji = ""
        self._reaction_count_str = ""

    # -- message finalization ----------------------------------------------

    def _finalize_current_message(self) -> None:
        msg_id = self._msg_id
        if not msg_id:
            warnings.warn(
                "Skipping message with no usable id attribute.",
                ParseWarning,
                stacklevel=2,
            )
            self.completed_messages.append(None)
            self._reset_message_state()
            return

        timestamp = _parse_timestamp(self._msg_timestamp_str)
        if timestamp is None:
            warnings.warn(
                f"Skipping message {msg_id!r} with missing or unparsable timestamp.",
                ParseWarning,
                stacklevel=2,
            )
            self.completed_messages.append(None)
            self._reset_message_state()
            return

        sender_name = self._msg_from_name.strip()
        sender_id: Optional[str] = None
        sender_display_name: Optional[str] = None
        if sender_name:
            sender_display_name = sender_name
            sender_id = sender_name  # deterministic, repository-consistent: name is the stable key
            if sender_name not in self.participants:
                self.participants[sender_name] = Participant(
                    id=sender_id, display_name=sender_name
                )

        text_content = "".join(self._msg_text_parts)
        text_content = text_content.strip("\n") if text_content else text_content
        if text_content == "":
            text_content = None

        forwarded_from = self._msg_forwarded_from.strip() if self._msg_forwarded_from else None

        edited_at = (
            self._resolve_edited_timestamp(
                self._strip_edited_prefix(self._msg_edited_str), timestamp
            )
            if self._msg_edited_str
            else None
        )

        if self._msg_is_service:
            msg_type = "service"
        elif self._msg_attachments:
            msg_type = "media"
        else:
            msg_type = "text"

        try:
            message = Message(
                message_id=msg_id,
                timestamp=timestamp,
                sender_id=sender_id,
                sender_display_name=sender_display_name,
                message_type=msg_type,
                text_content=text_content,
                reply_to_id=self._msg_reply_id,
                forwarded_from=forwarded_from,
                edited_at=edited_at,
                reactions=list(self._msg_reactions),
                attachments=list(self._msg_attachments),
                links=list(self._msg_links),
                source_file=self._source_file,
            )
        except ValueError as exc:
            warnings.warn(
                f"Skipping malformed message {msg_id!r}: {exc}",
                ParseWarning,
                stacklevel=2,
            )
            self.completed_messages.append(None)
            self._reset_message_state()
            return

        self.completed_messages.append(message)
        self._reset_message_state()

    @staticmethod
    def _strip_edited_prefix(raw: Optional[str]) -> str:
        if not raw:
            return ""
        text = raw.strip()
        match = _EDITED_PREFIX_RE.match(text)
        return match.group(1).strip() if match else text

    @staticmethod
    def _resolve_edited_timestamp(
        edited_str: str, message_timestamp: Optional[datetime]
    ) -> Optional[datetime]:
        """Parse an edit marker's timestamp text. Handles both a full
        date+time ("Jul 10, 2024, 3:05 PM") and a bare time-only marker
        ("3:15 PM", which real exports use for a same-day edit) by
        inheriting the date from the message's own already-parsed
        timestamp in the latter case.
        """
        parsed = _parse_timestamp(edited_str)
        if parsed is not None:
            return parsed

        if message_timestamp is None:
            return None

        match = _BARE_TIME_RE.match(edited_str)
        if not match:
            return None

        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        ampm = match.group("ampm")
        if ampm:
            if ampm.upper() == "PM" and hour != 12:
                hour += 12
            elif ampm.upper() == "AM" and hour == 12:
                hour = 0

        return message_timestamp.replace(hour=hour, minute=minute, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Public functional API
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 8192


def _iter_parse(
    file_path: Path | str,
) -> Iterator[tuple[Optional[Message], Chat, list[Participant]]]:
    """Shared driving loop for a single file: feed chunks, drain completed
    messages as they're produced. Genuinely streams -- never reads or
    buffers the whole file, and releases each message as soon as it is
    available rather than accumulating them all before yielding.
    """
    path = Path(file_path)
    source_file = str(path)
    parser = TelegramHTMLStreamParser(source_file=source_file)

    with open(path, "r", encoding="utf-8") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            parser.feed(chunk)
            while parser.completed_messages:
                message = parser.completed_messages.popleft()
                yield message, parser.chat_info, list(parser.participants.values())

    parser.close()
    while parser.completed_messages:
        message = parser.completed_messages.popleft()
        yield message, parser.chat_info, list(parser.participants.values())

    if not parser.is_valid_export:
        raise InvalidExportFormatError(
            f"File {file_path} does not appear to be a valid Telegram export"
        )


def parse_telegram_html(
    file_path: Path | str,
) -> Iterator[tuple[Optional[Message], Chat, list[Participant]]]:
    """Parse a Telegram HTML export file.

    Streams the file in chunks (never loading it fully into memory or
    building a DOM) and yields ``(message, chat, participants)`` for every
    completed message. ``message`` is ``None`` for a message that could
    not be parsed (a ``ParseWarning`` is emitted in that case); this lets
    one malformed message get skipped without aborting the whole export.

    Args:
        file_path: Path to the HTML export file.

    Yields:
        Tuples of (message or None, chat info so far, participants so far).

    Raises:
        InvalidExportFormatError: If the file does not look like a valid
            Telegram export (no ``<title>`` element was found).
    """
    yield from _iter_parse(file_path)


def parse_telegram_html_stream(file_path: Path | str) -> Iterator[Message]:
    """Stream only the successfully parsed messages from an export file.

    Unlike :func:`parse_telegram_html`, this does not report per-message
    parse failures via ``None`` entries or return chat/participant
    snapshots -- it is meant for callers that only need the message
    stream itself and want the leanest possible memory footprint.
    """
    for message, _chat, _participants in _iter_parse(file_path):
        if message is not None:
            yield message


def parse_export_files(
    file_paths: Iterable[Path | str],
) -> Iterator[tuple[Optional[Message], Chat, list[Participant]]]:
    """Parse multiple Telegram export files (e.g. a multi-part export).

    Files are parsed in the given order. Each file gets its own parser
    instance (so per-file chat metadata such as the source title is
    correctly scoped), but participants are merged across files by
    display name and the running merged set is yielded alongside each
    message, along with a ``Chat`` whose ``source_files`` accumulates
    every file processed so far.

    Args:
        file_paths: Paths to the HTML export files, in the order they
            should be parsed.

    Yields:
        Tuples of (message or None, chat info so far, participants so far).
    """
    merged_participants: dict[str, Participant] = {}
    source_files: list[str] = []
    chat_title: Optional[str] = None
    chat_id = "unknown"
    chat_type = "group"

    for file_path in file_paths:
        path = Path(file_path)
        source_files.append(str(path))
        for message, chat_info, _file_participants in _iter_parse(path):
            if chat_title is None and chat_info.title != "Unknown Chat":
                chat_title = chat_info.title
                chat_id = chat_info.chat_id
                chat_type = chat_info.chat_type

            if message is not None and message.sender_display_name:
                if message.sender_display_name not in merged_participants:
                    merged_participants[message.sender_display_name] = Participant(
                        id=message.sender_id, display_name=message.sender_display_name
                    )

            merged_chat = Chat(
                chat_id=chat_id,
                title=chat_title or "Unknown Chat",
                chat_type=chat_type,
                source_files=list(source_files),
            )
            yield message, merged_chat, list(merged_participants.values())
