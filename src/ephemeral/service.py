# Copyright (c) 2026 gatekeyp contributors

"""Ephemeral ("lite") events: short-lived flyer pages that wipe themselves.

A lite event is a regular ``event`` row flagged ``mode='ephemeral'`` with an
``expires_at`` deadline. Content is stored with the usual encrypted-at-rest
machinery; once the deadline passes, a sweep wipes the entire event (keys,
content, media, bulletins) and leaves only a tombstone.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.core.content_manager import (
    ALLOWED_MIME_TYPES,
    MAX_FILENAME_LENGTH,
    MAX_MEDIA_SIZE_BYTES,
    ContentAccessError,
    ContentValidationError,
)
from src.core.event_lifecycle import EventLifecycleError
from src.db.database_handler import DecryptionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.core.content_manager import ContentManager
    from src.core.event_lifecycle import EventLifecycleManager
    from src.db.database_handler import DatabaseHandler

logger = logging.getLogger("ephemeral")

# TTL bounds for ephemeral events: 1 hour .. 14 days.
MIN_TTL_HOURS = 1
MAX_TTL_HOURS = 336
DEFAULT_TTL_HOURS = 48

# Field length limits (mirroring API-level validation)
MAX_TITLE_LENGTH = 256
MAX_DESCRIPTION_LENGTH = 65536
MAX_TEXT_LENGTH = 256  # when / where free-text fields


class LiteValidationError(ValueError):
    """Raised when lite event input fails validation."""


class LiteNotFoundError(LookupError):
    """Raised when a requested event does not exist (or is not ephemeral)."""


class LiteGoneError(LookupError):
    """Raised when a requested event has expired or been wiped."""


class LiteRateLimitError(RuntimeError):
    """Raised when a client exceeds the lite creation rate limit."""


class LiteRateLimiter:
    """
    Fixed-window, per-client rate limiter for lite event creation.

    Deliberately separate from the gateway's failure-driven RateLimiter:
    lite creation is an unauthenticated write endpoint, so a plain fixed
    window is the right tool. The clock is injectable for tests.
    """

    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: float = 600.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Configure the window and (optionally) inject a clock for tests."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._hits: dict[str, list[float]] = {}

    def allow(self, client_id: str) -> bool:
        """Return True and record a hit when client_id is under the limit."""
        now = self._clock()
        window_start = now - self.window_seconds
        hits = [hit for hit in self._hits.get(client_id, []) if hit > window_start]
        if len(hits) >= self.max_requests:
            self._hits[client_id] = hits
            return False
        hits.append(now)
        self._hits[client_id] = hits
        return True


class EphemeralService:
    """
    Creates and serves ephemeral lite events.

    Reuses the standard stack (EventLifecycleManager for events and keys,
    ContentManager for encrypted media and content blocks); only the expiry
    and wipe bookkeeping is new.
    """

    def __init__(
        self,
        db: DatabaseHandler,
        lifecycle: EventLifecycleManager,
        content_manager: ContentManager,
        *,
        rate_limiter: LiteRateLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Store shared services; the rate limiter and clock are injectable."""
        self.db = db
        self.lifecycle = lifecycle
        self.content_manager = content_manager
        self.rate_limiter = rate_limiter or LiteRateLimiter()
        self._clock = clock or (lambda: datetime.now(UTC))

    # -- Validation ----------------------------------------------------

    @staticmethod
    def _validate_text(
        value: str | None, field: str, max_length: int, *, required: bool = False
    ) -> str | None:
        """Validate an optional free-text field; empty optional values -> None."""
        if value is None or not value.strip():
            if required:
                message = f"{field} is required"
                raise LiteValidationError(message)
            return None
        if len(value) > max_length:
            message = f"{field} exceeds maximum length of {max_length} characters"
            raise LiteValidationError(message)
        return value

    @staticmethod
    def _validate_ttl(ttl_hours: int) -> int:
        """Bound-check the event TTL."""
        if ttl_hours < MIN_TTL_HOURS or ttl_hours > MAX_TTL_HOURS:
            message = f"ttl_hours must be between {MIN_TTL_HOURS} and {MAX_TTL_HOURS}"
            raise LiteValidationError(message)
        return ttl_hours

    @staticmethod
    def _parse_event_time(when: str | None) -> datetime | None:
        """Parse a machine-readable event time; free text (or empty) -> None."""
        if not when:
            return None
        try:
            event_time = datetime.fromisoformat(when)
        except ValueError:
            return None
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)
        return event_time

    @staticmethod
    def _validate_flyer(flyer: dict[str, Any] | None) -> dict[str, Any] | None:
        """Pre-validate the flyer payload against ContentManager's limits."""
        if flyer is None:
            return None
        if flyer["mime_type"] not in ALLOWED_MIME_TYPES:
            message = f"Unsupported MIME type: {flyer['mime_type']}"
            raise LiteValidationError(message)
        if len(flyer["filename"]) > MAX_FILENAME_LENGTH:
            message = f"filename exceeds maximum length of {MAX_FILENAME_LENGTH} characters"
            raise LiteValidationError(message)
        if len(flyer["data"]) > MAX_MEDIA_SIZE_BYTES:
            message = f"flyer exceeds maximum size of {MAX_MEDIA_SIZE_BYTES} bytes"
            raise LiteValidationError(message)
        return flyer

    # -- Creation ------------------------------------------------------

    def create_lite_event(
        self,
        title: str,
        *,
        description: str | None = None,
        when: str | None = None,
        where: str | None = None,
        flyer: dict[str, Any] | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict:
        """
        Create an ephemeral event and return its ids and secrets.

        Args:
            title: Event title (shown publicly on the flyer page).
            description: Optional description; defaults to the title when
                omitted (lifecycle requires a non-empty description).
            when: Optional schedule, stored as a gated content block. An
                ISO-8601 timestamp also anchors the wipe deadline — the event
                is wiped ttl_hours after the event time, not after creation;
                free text keeps the creation-anchored deadline.
            where: Optional free-text location, stored as a gated content block.
            flyer: Optional flyer payload (filename, mime_type, data bytes),
                stored encrypted-at-rest but served publicly.
            ttl_hours: Event lifetime in hours — counted from the event time
                when `when` parses as a timestamp, else from creation; all
                data is wiped after expiry.

        Returns:
            Payload with event_id, master_key (shown once), expiry timestamps
            and the flyer asset id.
        """
        self._validate_text(title, "title", MAX_TITLE_LENGTH, required=True)
        self._validate_text(description, "description", MAX_DESCRIPTION_LENGTH)
        self._validate_text(when, "when", MAX_TEXT_LENGTH)
        self._validate_text(where, "where", MAX_TEXT_LENGTH)
        self._validate_ttl(ttl_hours)
        self._validate_flyer(flyer)

        now = self._clock()
        event_time = self._parse_event_time(when)
        expiry_dt = (event_time or now) + timedelta(hours=ttl_hours)
        if event_time is not None and expiry_dt <= now:
            message = "The event time has already passed — pick a time in the future"
            raise LiteValidationError(message)
        expires_at = expiry_dt.isoformat()
        # The master key must outlive the event (plus one day of grace)
        master_key_days = max(1, math.ceil((expiry_dt - now).total_seconds() / 86400) + 1)

        try:
            created = self.lifecycle.create_event(
                title=title,
                description=description or title,
                organizer_id="lite:ephemeral",
                master_key_days=master_key_days,
            )
        except EventLifecycleError as err:
            message = f"Could not create lite event: {err}"
            raise LiteValidationError(message) from err

        event_id = created["event_id"]
        master_key = created["master_key"]
        self.db.set_event_mode(event_id, "ephemeral", expires_at)

        flyer_asset_id = None
        if flyer is not None:
            try:
                uploaded = self.content_manager.upload_media(
                    input_key=master_key,
                    event_id=event_id,
                    filename=flyer["filename"],
                    mime_type=flyer["mime_type"],
                    data=flyer["data"],
                )
            except (
                ContentValidationError,
                ContentAccessError,
                DecryptionError,
                sqlite3.Error,
            ) as err:
                # Roll back the half-created event; never leave debris behind
                self.db.wipe_event(event_id, tombstone=False)
                message = f"Flyer upload failed: {err}"
                raise LiteValidationError(message) from err
            flyer_asset_id = uploaded["id"]

        if when:
            self.lifecycle.add_content_block(
                master_key=master_key,
                event_id=event_id,
                content_type="schedule",
                payload=when,
            )
        if where:
            self.lifecycle.add_content_block(
                master_key=master_key,
                event_id=event_id,
                content_type="location",
                payload=where,
            )

        return {
            "event_id": event_id,
            "title": title,
            "master_key": master_key,
            "master_key_expires_at": created["expires_at"],
            "event_expires_at": expires_at,
            "flyer_asset_id": flyer_asset_id,
        }

    # -- Reads ---------------------------------------------------------

    def _is_expired(self, expires_at: str | None) -> bool:
        """Fail-closed expiry check: unparseable timestamps count as expired."""
        if not expires_at:
            return False
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return True
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=UTC)
        return self._clock() > expires_dt

    def get_public_view(self, event_id: str) -> dict:
        """
        Return the public view state for an event (no key required).

        Raises LiteNotFoundError when the event is unknown or not ephemeral;
        returns status='ended'/'expired' instead of raising for gone events
        so routes can render honest tombstone pages.
        """
        ended = self.db.get_tombstone(event_id)
        if ended is not None:
            return {"status": "ended", "ended_at": ended["ended_at"]}
        event = self.db.get_event(event_id)
        if event is None or event.get("mode") != "ephemeral":
            message = f"Event not found: {event_id}"
            raise LiteNotFoundError(message)
        if self._is_expired(event.get("expires_at")):
            return {"status": "expired"}
        media = self.db.list_media_assets(event_id)
        return {
            "status": "live",
            "event": event,
            "flyer_asset_id": media[0]["id"] if media else None,
        }

    def get_keyed_view(self, *, key: str, event_id: str) -> dict:
        """
        Return title, description and decrypted when/where for a key holder.

        The key may be the master key or any access key linked to the event;
        access is verified through ContentManager's event-scope fallback.
        """
        ended = self.db.get_tombstone(event_id)
        if ended is not None:
            message = f"Event ended at {ended['ended_at']}"
            raise LiteGoneError(message)
        event = self.db.get_event(event_id)
        if event is None or event.get("mode") != "ephemeral":
            message = f"Event not found: {event_id}"
            raise LiteNotFoundError(message)
        if self._is_expired(event.get("expires_at")):
            message = f"Event expired at {event.get('expires_at')}"
            raise LiteGoneError(message)

        try:
            self.content_manager.verify_event_access(key, event_id)
        except (ContentValidationError, ContentAccessError) as err:
            message = "Key does not grant access to this event"
            raise LiteValidationError(message) from err

        blocks = self.db.list_content_blocks_for_event(event_id)
        when = next((b["payload"] for b in blocks if b["content_type"] == "schedule"), None)
        where = next((b["payload"] for b in blocks if b["content_type"] == "location"), None)
        media = self.db.list_media_assets(event_id)
        return {
            "event": {
                "id": event["id"],
                "title": event["title"],
                "description": event["description"],
            },
            "when": when,
            "where": where,
            "flyer_asset_id": media[0]["id"] if media else None,
            "expires_at": event.get("expires_at"),
        }

    # -- Expiry ----------------------------------------------------------

    def sweep_expired(self) -> list[str]:
        """Wipe every expired ephemeral event, leaving tombstones behind."""
        now_iso = self._clock().isoformat()
        swept = []
        for event_id in self.db.get_expired_event_ids(now_iso):
            try:
                self.db.wipe_event(event_id)
            except (sqlite3.Error, DecryptionError):
                logger.exception("Failed to wipe expired event %s", event_id)
            else:
                swept.append(event_id)
                logger.info("Wiped expired ephemeral event %s", event_id)
        return swept
