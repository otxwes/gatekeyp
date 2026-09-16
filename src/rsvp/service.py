# Copyright (c) 2026 gatekeyp contributors

"""RSVP funnel: pull-flow invite requests with a server-side approval gate.

An attendee submits an RSVP (a display name, optional free-text contact) at
``#/rsvp/{event_id}``; the service pre-mints an access key for the event and
returns the raw key exactly once — the attendee's browser embeds it in the
opaque invite card it downloads. The key is persisted only as a keyed HMAC
(``keys`` table) and carries no content grants until the organizer approves:
the door sees it as "valid-but-pending". Denying flips the same row and
revokes the key (the door's existing voided treatment). When the event is
wiped, the RSVP rows and every related secret go with it; only a tombstone
remains.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from src.core.event_lifecycle import DEFAULT_ACCESS_KEY_DAYS
from src.core.key_manager import InvalidKeyFormatError

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.core.event_lifecycle import EventLifecycleManager
    from src.core.key_manager import KeyManager
    from src.db.database_handler import DatabaseHandler

logger = logging.getLogger("rsvp")

# Field length limits (mirroring API-level validation)
MAX_DISPLAY_NAME_LENGTH = 64
MAX_CONTACT_LENGTH = 256
# Auto-approve dial bounds: null (manual gate) or an integer N meaning "keep
# up to N RSVPs currently approved" (denying one frees the slot again).
MAX_AUTO_APPROVE = 100000
# Cap on outstanding pending RSVPs per event, so an attacker with rotating IPs
# cannot force unbounded pre-minted key growth in the keys table.
MAX_PENDING_RSVP_PER_EVENT = 500

RSVP_STATUS_PENDING = "pending"
RSVP_STATUS_APPROVED = "approved"
RSVP_STATUS_DENIED = "denied"


class RsvpValidationError(ValueError):
    """Raised when RSVP input fails validation (message is safe to surface)."""


class RsvpNotFoundError(LookupError):
    """Raised when a requested event or RSVP does not exist."""


class RsvpGoneError(LookupError):
    """Raised when the requested event has been wiped (tombstone only)."""


class RsvpRateLimitError(RuntimeError):
    """Raised when a client exceeds the RSVP submission rate limit."""


class RsvpRateLimiter:
    """
    Fixed-window, per-client rate limiter for the unauthenticated RSVP write
    endpoint. Deliberately separate from the gateway's failure-driven
    RateLimiter (same reasoning as the lite funnel's limiter). The clock is
    injectable for tests.
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
        self._clock = clock or (lambda: datetime.now(UTC).timestamp())
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


class RsvpService:
    """
    Submits RSVPs and applies organizer decisions.

    Reuses the standard stack (KeyManager for key material,
    EventLifecycleManager for grants); only the request/approval bookkeeping
    is new.
    """

    def __init__(
        self,
        db: DatabaseHandler,
        key_manager: KeyManager,
        lifecycle: EventLifecycleManager,
        rate_limiter: RsvpRateLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Wire the shared services; the rate limiter and clock are injectable."""
        self.db = db
        self.key_manager = key_manager
        self.lifecycle = lifecycle
        self.rate_limiter = rate_limiter or RsvpRateLimiter()
        self._clock = clock or (lambda: datetime.now(UTC))

    # -- Validation ------------------------------------------------------

    def _validate_text(
        self, value: str | None, name: str, max_length: int, *, required: bool = False
    ) -> str | None:
        """Validate a free-text RSVP field; returns the cleaned value or None."""
        text = value.strip() if isinstance(value, str) else None
        if not text:
            if required:
                message = f"RSVP {name} cannot be empty"
                raise RsvpValidationError(message)
            return None
        if len(text) > max_length:
            message = f"RSVP {name} is too long (max {max_length} characters)"
            raise RsvpValidationError(message)
        return text

    def _verify_event(self, event_id: str) -> dict:
        """Resolve a live standard event, or fail with the right error type."""
        ended = self.db.get_tombstone(event_id)
        if ended is not None:
            message = f"Event ended at {ended['ended_at']}"
            raise RsvpGoneError(message)
        event = self.db.get_event(event_id)
        if event is None or event.get("mode") != "standard":
            message = f"Event not found: {event_id}"
            raise RsvpNotFoundError(message)
        return event

    def _check_passphrase(self, event: dict, passphrase: str | None) -> None:
        """Fail closed when the event's optional RSVP passphrase doesn't match."""
        stored_hash = event.get("rsvp_passphrase_hash")
        if not stored_hash:
            return
        given = self._validate_text(passphrase, "passphrase", MAX_CONTACT_LENGTH)
        if not given:
            message = "This event requires an RSVP passphrase"
            raise RsvpValidationError(message)
        if not hmac.compare_digest(self.key_manager.hash_key(given), stored_hash):
            message = "That RSVP passphrase is not correct"
            raise RsvpValidationError(message)

    # -- Grants ----------------------------------------------------------

    def _grant_event_content(self, key_hash: str, event_id: str) -> int:
        """Grant a key to the event row and all of its current content."""
        self.db.add_key_content_link(key_hash, event_id, "event")
        for block in self.db.list_content_blocks_for_event(event_id):
            self.db.add_key_content_link(key_hash, block["id"], "block")
        for asset in self.db.list_media_assets(event_id):
            self.db.add_key_content_link(key_hash, asset["id"], "media")
        for bulletin in self.db.list_bulletins(event_id):
            self.db.add_key_content_link(key_hash, bulletin["id"], "bulletin")
        return 1

    def _verify_organizer(self, organizer_key: str | None, event_id: str) -> dict:
        """Check the presented key is valid and grants access to this event."""
        if not isinstance(organizer_key, str):
            message = "Invalid organizer key"
            raise RsvpValidationError(message)
        try:
            validation = self.key_manager.validate_key(organizer_key)
        except InvalidKeyFormatError as err:
            message = "Invalid organizer key"
            raise RsvpValidationError(message) from err
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise RsvpValidationError(message)
        content_ids = self.db.get_content_ids_for_key(validation["hash"])
        if not any(content["content_id"] == event_id for content in content_ids):
            message = "Organizer key does not grant access to this event"
            raise RsvpValidationError(message)
        return validation

    # -- Submission ------------------------------------------------------

    def submit_rsvp(
        self,
        event_id: str,
        display_name: str | None = None,
        *,
        contact: str | None = None,
        passphrase: str | None = None,
    ) -> dict:
        """
        Record an RSVP and pre-mint its access key.

        The raw key is returned exactly once (this return value); only the
        keyed HMAC is stored. When the event's auto-approve dial is on and has
        capacity, the RSVP is approved immediately and the key is granted to
        the event's content; otherwise it stays pending with no grants at all.

        Raises:
            RsvpValidationError: On invalid input or a wrong passphrase.
            RsvpNotFoundError: When the event is unknown or not standard.
            RsvpGoneError: When the event has been wiped.
        """
        event = self._verify_event(event_id)
        name = self._validate_text(display_name, "name", MAX_DISPLAY_NAME_LENGTH, required=True)
        if name is None:  # pragma: no cover - required=True guarantees non-None
            message = "RSVP name cannot be empty"
            raise RsvpValidationError(message)
        clean_contact = self._validate_text(contact, "contact", MAX_CONTACT_LENGTH)
        self._check_passphrase(event, passphrase)

        approved_count = 0
        pending_count = 0
        for row in self.db.list_rsvps(event_id):
            if row["status"] == RSVP_STATUS_APPROVED:
                approved_count += 1
            elif row["status"] == RSVP_STATUS_PENDING:
                pending_count += 1
        if pending_count >= MAX_PENDING_RSVP_PER_EVENT:
            message = "This event's RSVP queue is full; try again later"
            raise RsvpValidationError(message)
        dial = event.get("rsvp_auto_approve")
        auto_approved = dial is not None and approved_count < int(dial)
        status = RSVP_STATUS_APPROVED if auto_approved else RSVP_STATUS_PENDING

        rsvp_id = f"rsvp_{secrets.token_hex(16)}"
        access_key = self.key_manager.generate_key()
        access_hash = self.key_manager.hash_key(access_key)
        expires_at = (self._clock() + timedelta(days=DEFAULT_ACCESS_KEY_DAYS)).isoformat()

        self.db.add_rsvp(
            rsvp_id=rsvp_id,
            event_id=event_id,
            display_name=name,
            contact=clean_contact,
            key_hash=access_hash,
            status=status,
        )
        self.db.add_key(
            hash_key=access_hash,
            key_type="access",
            expires_at=expires_at,
            owner_id=None,
            rsvp_id=rsvp_id,
        )
        if auto_approved:
            self._grant_event_content(access_hash, event_id)

        logger.info("RSVP %s submitted for %s (status=%s)", rsvp_id, event_id, status)
        return {
            "rsvp_id": rsvp_id,
            "event_id": event_id,
            "display_name": name,
            "status": status,
            "access_key": f"local:{access_key}",
            "expires_at": expires_at,
        }

    # -- Organizer decisions ----------------------------------------------

    def decide(
        self,
        organizer_key: str | None,
        event_id: str,
        rsvp_id: str,
        decision: str,
    ) -> dict:
        """
        Apply an organizer decision to an RSVP.

        Approve stamps the row and grants the pre-minted key to the event's
        content (idempotent when already approved). Deny stamps the row and
        revokes the key — the door then rejects the card like any voided one.
        Approving after a deny is rejected: the attendee submits a new RSVP
        instead, which mints a fresh key.

        Raises:
            RsvpValidationError: On bad input or an unauthorized key.
            RsvpNotFoundError: When the RSVP is unknown for this event.
        """
        self._verify_organizer(organizer_key, event_id)
        rsvp = self.db.get_rsvp(rsvp_id)
        if rsvp is None or rsvp["event_id"] != event_id:
            message = f"RSVP not found: {rsvp_id}"
            raise RsvpNotFoundError(message)

        if decision == "approve":
            if rsvp["status"] == RSVP_STATUS_DENIED:
                message = "This RSVP was denied; the attendee must submit a new RSVP"
                raise RsvpValidationError(message)
            if rsvp["status"] != RSVP_STATUS_APPROVED:
                self.db.set_rsvp_status(rsvp_id, RSVP_STATUS_APPROVED)
            if rsvp["key_hash"]:
                self._grant_event_content(rsvp["key_hash"], event_id)
        elif decision == "deny":
            self.db.set_rsvp_status(rsvp_id, RSVP_STATUS_DENIED)
            if rsvp["key_hash"]:
                self.db.revoke_key(rsvp["key_hash"])
        else:
            message = "Decision must be 'approve' or 'deny'"
            raise RsvpValidationError(message)

        return {"rsvp_id": rsvp_id, "event_id": event_id, "decision": decision}

    # -- Settings & organizer listing --------------------------------------

    def get_rsvp_settings(self, organizer_key: str | None, event_id: str) -> dict:
        """Return the event's RSVP gate settings (organizer-gated)."""
        self._verify_organizer(organizer_key, event_id)
        event = self.db.get_event(event_id)
        return {
            "passphrase_required": bool(event and event.get("rsvp_passphrase_hash")),
            "auto_approve": event.get("rsvp_auto_approve") if event else None,
        }

    def update_rsvp_settings(
        self,
        organizer_key: str | None,
        event_id: str,
        *,
        passphrase: str | None = None,
        auto_approve: int | None = None,
    ) -> dict:
        """
        Set the event's RSVP gate (organizer-gated).

        ``passphrase``: empty/None clears the gate; a non-empty value is stored
        as a keyed hash only. ``auto_approve``: None disables auto-approval
        (manual gate); an integer N keeps up to N RSVPs currently approved —
        a submission auto-approves while approved_count < N, and denying one
        frees the slot for the next submission.

        Raises:
            RsvpValidationError: On bad input or an unauthorized key.
        """
        self._verify_organizer(organizer_key, event_id)
        clean_passphrase = self._validate_text(passphrase, "passphrase", MAX_CONTACT_LENGTH)
        passphrase_hash = self.key_manager.hash_key(clean_passphrase) if clean_passphrase else None
        if auto_approve is None:
            dial: int | None = None
        elif not isinstance(auto_approve, int) or isinstance(auto_approve, bool):
            message = "auto_approve must be an integer or null"
            raise RsvpValidationError(message)
        elif not 0 <= auto_approve <= MAX_AUTO_APPROVE:
            message = f"auto_approve must be between 0 and {MAX_AUTO_APPROVE}"
            raise RsvpValidationError(message)
        else:
            dial = auto_approve
        self.db.set_rsvp_settings(event_id, passphrase_hash, dial)
        return {
            "event_id": event_id,
            "passphrase_required": bool(passphrase_hash),
            "auto_approve": dial,
        }

    def list_rsvps_for_event(self, organizer_key: str | None, event_id: str) -> list[dict]:
        """List RSVP rows for the organizer tab (contacts decrypted server-side)."""
        self._verify_organizer(organizer_key, event_id)
        return self.db.list_rsvps(event_id)

    # -- Public view -------------------------------------------------------

    def get_public_view(self, event_id: str) -> dict:
        """
        Minimal public data for the attendee RSVP page: title, description and
        whether a passphrase is required. No keys, no RSVP list, no contacts.
        """
        ended = self.db.get_tombstone(event_id)
        if ended is not None:
            return {"status": "ended", "ended_at": ended["ended_at"]}
        event = self.db.get_event(event_id)
        if event is None or event.get("mode") != "standard":
            message = f"Event not found: {event_id}"
            raise RsvpNotFoundError(message)
        return {
            "status": "live",
            "event": {
                "id": event["id"],
                "title": event["title"],
                "description": event["description"],
            },
            "passphrase_required": bool(event.get("rsvp_passphrase_hash")),
        }
