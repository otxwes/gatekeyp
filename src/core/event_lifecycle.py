# Copyright (c) 2026 gatekeyp contributors

import json
import re
import secrets
from datetime import UTC, datetime, timedelta

from src.core.content_manager import ContentManager
from src.core.geocoding import Geocoder
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# Default key lifetime for access keys (30 days)
DEFAULT_ACCESS_KEY_DAYS = 30
MAX_BULK_KEYS = 100

# Default key lifetime for organizer keys (365 days)
DEFAULT_ORGANIZER_KEY_DAYS = 365

# Error message for organizer key not granting access to an event
_ACCESS_DENIED_MSG = "Organizer key does not grant access to this event"


class EventLifecycleError(ValueError):
    """Raised when an event lifecycle operation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class EventLifecycleManager:
    """
    Orchestrates the full event lifecycle: creation, content upload,
    access management, key distribution, and decommissioning.

    This is the high-level service that the web UI and API server
    will use to manage events end-to-end.
    """

    def __init__(
        self,
        db: DatabaseHandler,
        key_manager: KeyManager,
        content_manager: ContentManager,
        *,
        geocoder: Geocoder | None = None,
        map_style_url: str | None = None,
    ) -> None:
        """
        Initialize the EventLifecycleManager.

        Args:
            db: Shared DatabaseHandler instance.
            key_manager: Shared KeyManager instance.
            content_manager: Shared ContentManager instance.
            geocoder: Optional forward geocoder for the directions map.
            map_style_url: Optional MapLibre style URL; None disables maps.
        """
        self.db = db
        self.key_manager = key_manager
        self.content_manager = content_manager
        self.geocoder = geocoder
        self.map_style_url = map_style_url

    # ------------------------------------------------------------------
    # ID Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_id(prefix: str) -> str:
        """Generate a unique ID with a prefix."""
        return f"{prefix}_{secrets.token_hex(16)}"

    @staticmethod
    def _make_slug(title: str) -> str:
        """A human-readable share slug from a title (lowercase, dashed, with
        a short random suffix so titles never collide)."""
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        base = base[:40].strip("-") or "event"
        return f"{base}-{secrets.token_hex(3)}"

    # ------------------------------------------------------------------
    # Event Creation
    # ------------------------------------------------------------------

    def create_event(
        self,
        title: str,
        description: str,
        organizer_id: str,
        location_data: str | None = None,
        *,
        organizer_key_days: int = DEFAULT_ORGANIZER_KEY_DAYS,
        organizer_name: str = "",
        show_map: bool = True,
    ) -> dict:
        """
        Create a new event with a organizer key.

        The organizer key grants full access to all event content and
        can be used to generate attendee access keys.

        Args:
            title: Event title.
            description: Event description.
            organizer_id: Identifier of the organizer (e.g., @user:instance).
            location_data: Optional location data (e.g., coordinates).
            organizer_key_days: Lifetime of the organizer key in days.
            show_map: Whether the directions map is enabled for this event.

        Returns:
            Event metadata including the organizer key (shown once).
        """
        # Validate inputs
        if not title or not title.strip():
            message = "Event title cannot be empty"
            raise EventLifecycleError(message)
        if not description or not description.strip():
            message = "Event description cannot be empty"
            raise EventLifecycleError(message)
        if not organizer_id or not organizer_id.strip():
            message = "Organizer ID cannot be empty"
            raise EventLifecycleError(message)

        # Generate event ID
        event_id = self._generate_id("event")
        slug = self._make_slug(title)

        # Geocode once, only when the map is enabled. A failure leaves the
        # event usable with links instead of a map.
        location_geo = None
        if show_map and self.geocoder and location_data and location_data.strip():
            point = self.geocoder.geocode(location_data)
            if point is not None:
                location_geo = json.dumps({"lat": point.lat, "lon": point.lon})

        # Create the event record
        self.db.add_event(
            event_id=event_id,
            title=title,
            description=description,
            organizer_id=organizer_id,
            location_data=location_data,
            slug=slug,
            organizer_name=organizer_name,
            location_geo=location_geo,
            show_map=show_map,
        )

        # Generate a organizer key for this event
        organizer_key = self.key_manager.generate_key()
        organizer_hash = self.key_manager.hash_key(organizer_key)
        expires_at = (datetime.now(UTC) + timedelta(days=organizer_key_days)).isoformat()

        self.db.add_key(
            hash_key=organizer_hash,
            key_type="organizer",
            expires_at=expires_at,
            owner_id=organizer_id,
        )

        # Link the organizer key to the event
        self.db.add_key_content_link(organizer_hash, event_id, "event")

        return {
            "event_id": event_id,
            "title": title,
            "description": description,
            "organizer_id": organizer_id,
            "organizer_key": f"local:{organizer_key}",
            "organizer_key_hash": organizer_hash,
            "slug": slug,
            "expires_at": expires_at,
            "show_map": show_map,
            "map_available": bool(location_geo) and bool(self.map_style_url),
        }

    # ------------------------------------------------------------------
    # Content Upload
    # ------------------------------------------------------------------

    def add_content_block(
        self,
        organizer_key: str,
        event_id: str,
        content_type: str,
        payload: str,
    ) -> dict:
        """
        Add a content block (description, location, schedule, etc.) to an event.

        Args:
            organizer_key: The event's organizer key.
            event_id: The event ID.
            content_type: Type of content (e.g., "description", "schedule").
            payload: The content payload.

        Returns:
            The created content block metadata.
        """
        # Verify the organizer key grants access to the event
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Generate a content block ID
        block_id = self._generate_id("block")

        # Store the content block
        self.db.add_content_block(
            block_id=block_id,
            event_id=event_id,
            key_id=key_hash,
            content_type=content_type,
            payload=payload,
        )

        return {
            "id": block_id,
            "event_id": event_id,
            "content_type": content_type,
        }

    def _verify_event_organizer(self, organizer_key: str, event_id: str) -> dict:
        """Verify an organizer key and return the event plus its grants."""
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        event = self.db.get_event(event_id)
        if event is None:
            message = "Event not found"
            raise EventLifecycleError(message)
        return {"event": event, "key_hash": key_hash, "content_ids": content_ids}

    def _event_location_block(self, content_ids: list[dict]) -> str | None:
        """Return the event's location content-block payload, if any.

        Lite events store their address as a `location` content block
        instead of `events.location_data`.
        """
        for link in content_ids:
            if link["content_type"] != "block":
                continue
            block = self.db.get_content_block(link["content_id"])
            if block is None or block.get("content_type") != "location":
                continue
            payload = block.get("payload")
            if payload and payload.strip():
                return payload
        return None

    def get_event_details(self, organizer_key: str, event_id: str) -> dict:
        """
        Retrieve full event details including all content blocks.

        Args:
            organizer_key: The event's organizer key.
            event_id: The event ID.

        Returns:
            Event details with all content blocks.
        """
        verified = self._verify_event_organizer(organizer_key, event_id)
        event = verified["event"]
        content_ids = verified["content_ids"]

        # Get all content blocks for this event
        blocks = []
        for link in content_ids:
            if link["content_type"] == "block":
                block = self.db.get_content_block(link["content_id"])
                if block:
                    blocks.append(block)

        return {
            "event": event,
            "content_blocks": blocks,
        }

    def set_event_map(self, organizer_key: str, event_id: str, *, show_map: bool) -> dict:
        """Enable or disable the directions map for an event."""
        verified = self._verify_event_organizer(organizer_key, event_id)
        key_info = self.db.get_key(verified["key_hash"])
        if key_info is None or key_info.get("type") != "organizer":
            raise EventLifecycleError(_ACCESS_DENIED_MSG)
        event = verified["event"]

        if show_map:
            location_data = event.get("location_data")
            if not location_data or not location_data.strip():
                # Lite events keep `where` in a location content block rather
                # than events.location_data; spec §5.5 lets a full-profile
                # workspace toggle them.
                location_data = self._event_location_block(verified["content_ids"])
            if not location_data or not location_data.strip():
                message = "Event has no location to map"
                raise EventLifecycleError(message)
            if event.get("location_lat") is None and self.geocoder:
                point = self.geocoder.geocode(location_data)
                if point is not None:
                    location_geo = json.dumps({"lat": point.lat, "lon": point.lon})
                    self.db.set_event_location_geo(event_id, location_geo)

        self.db.set_event_show_map(event_id, show_map=show_map)
        updated = self.db.get_event(event_id)
        map_available = bool(
            show_map
            and updated is not None
            and updated.get("location_lat") is not None
            and self.map_style_url
        )
        return {"show_map": show_map, "map_available": map_available}

    def set_flyer(
        self,
        organizer_key: str,
        event_id: str,
        asset_id: str | None,
    ) -> dict:
        """
        Set (or clear, when asset_id is None) the event's flyer media asset,
        used as a card-cover option. Verifies the organizer's access and that
        the asset belongs to this event.
        """
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)
        org_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(org_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        if asset_id:
            asset = self.db.get_media_asset(asset_id)
            if asset is None or asset.get("event_id") != event_id:
                other_event_msg = "Flyer asset does not belong to this event"
                raise EventLifecycleError(other_event_msg)

        self.db.set_event_flyer(event_id, asset_id)
        return {"event_id": event_id, "flyer_asset_id": asset_id}

    # ------------------------------------------------------------------
    # Access Management
    # ------------------------------------------------------------------

    def generate_access_key(
        self,
        organizer_key: str,
        event_id: str,
        *,
        days: int = DEFAULT_ACCESS_KEY_DAYS,
        owner_id: str | None = None,
    ) -> dict:
        """
        Generate an attendee access key for an event.

        The access key grants access to all content linked to the event.

        Args:
            organizer_key: The event's organizer key (must be valid).
            event_id: The event ID.
            days: Lifetime of the access key in days.
            owner_id: Optional identifier of the key owner.

        Returns:
            The generated access key (shown once).
        """
        # Verify the organizer key grants access to the event
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Generate an access key
        access_key = self.key_manager.generate_key()
        access_hash = self.key_manager.hash_key(access_key)
        expires_at = (datetime.now(UTC) + timedelta(days=days)).isoformat()

        self.db.add_key(
            hash_key=access_hash,
            key_type="access",
            expires_at=expires_at,
            owner_id=owner_id,
        )

        # Link the access key to all content for this event
        for link in content_ids:
            self.db.add_key_content_link(access_hash, link["content_id"], link["content_type"])

        return {
            "access_key": f"local:{access_key}",
            "access_key_hash": access_hash,
            "event_id": event_id,
            "expires_at": expires_at,
        }

    def generate_access_keys_bulk(
        self,
        organizer_key: str,
        event_id: str,
        *,
        count: int,
        days: int = DEFAULT_ACCESS_KEY_DAYS,
        owners: list[str | None] | None = None,
    ) -> list[dict]:
        """
        Generate several attendee access keys in one call; each may carry an
        owner name. Verifies the organizer's access once, then mints `count`
        keys (linked to the event's content) with the matching owner names.
        """
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)
        org_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(org_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        if count < 1 or count > MAX_BULK_KEYS:
            message = f"count must be between 1 and {MAX_BULK_KEYS}"
            raise EventLifecycleError(message)

        results: list[dict] = []
        for i in range(count):
            owner = (owners[i] or None) if owners and i < len(owners) else None
            access_key = self.key_manager.generate_key()
            access_hash = self.key_manager.hash_key(access_key)
            expires_at = (datetime.now(UTC) + timedelta(days=days)).isoformat()
            self.db.add_key(
                hash_key=access_hash,
                key_type="access",
                expires_at=expires_at,
                owner_id=owner,
            )
            for link in content_ids:
                self.db.add_key_content_link(access_hash, link["content_id"], link["content_type"])
            results.append(
                {
                    "access_key": f"local:{access_key}",
                    "access_key_hash": access_hash,
                    "event_id": event_id,
                    "owner_id": owner,
                    "expires_at": expires_at,
                }
            )
        return results

    def list_access_keys(
        self,
        organizer_key: str,
        event_id: str,
    ) -> list[dict]:
        """
        List all access keys for an event.

        Args:
            organizer_key: The event's organizer key.
            event_id: The event ID.

        Returns:
            List of access key metadata (no raw keys).
        """
        # Verify the organizer key grants access to the event
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Get all access keys linked to this event's content (single join query
        # rather than a per-key probe — keeps listing O(1) queries instead of O(n)).
        return self.db.list_access_keys_for_event(event_id)

    def revoke_access_key(
        self,
        organizer_key: str,
        event_id: str,
        access_key: str,
    ) -> bool:
        """
        Revoke an attendee access key.

        Args:
            organizer_key: The event's organizer key.
            event_id: The event ID.
            access_key: The raw access key to revoke.

        Returns:
            True if the key was revoked.
        """
        # Verify the organizer key grants access to the event
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Revoke the access key
        return self.key_manager.revoke_key(access_key)

    def revoke_access_key_by_hash(
        self,
        organizer_key: str,
        event_id: str,
        key_hash: str,
    ) -> bool:
        """
        Revoke an attendee access key by its stored hash.

        The organizer does not hold the raw access key (it exists only in the
        attendee's card pixels), so revocation revokes by the key's hash
        returned in the access-key list.

        Args:
            organizer_key: The event's organizer key.
            event_id: The event ID.
            key_hash: The stored hash of the access key to revoke.

        Returns:
            True if the key was revoked.
        """
        # Verify the organizer key grants access to the event
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        org_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(org_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Verify the target key belongs to this event before revoking.
        target_content = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in target_content):
            other_event_msg = "Key does not belong to this event"
            raise EventLifecycleError(other_event_msg)

        return self.key_manager.revoke_key_by_hash(key_hash)

    # ------------------------------------------------------------------
    # Event Decommissioning
    # ------------------------------------------------------------------

    def decommission_event(
        self,
        organizer_key: str,
        event_id: str,
    ) -> dict:
        """
        Decommission an event: revoke all keys, wipe every trace of the
        event's data, and leave a tombstone so late attendees see an ended
        event (public view reports "ended"; RSVP submissions are refused).

        Args:
            organizer_key: The event's organizer key.
            event_id: The event ID.

        Returns:
            Summary of the decommissioning.
        """
        # Verify the organizer key grants access to the event
        validation = self.key_manager.validate_key(organizer_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid organizer key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Revoke the organizer key
        self.db.revoke_key(key_hash)

        # Revoke all access keys linked to this event's content (single query)
        revoked_count = 0
        for key in self.db.list_access_keys_for_event(event_id):
            if not key["revoked"]:
                self.db.revoke_key(key["hash_key"])
                revoked_count += 1

        # Wipe every trace of the event and leave a tombstone, so the RSVP
        # funnel (public view, submissions, the door) answers as "ended"
        # instead of serving a dead event (Phase B lifecycle contract).
        wiped = self.db.wipe_event(event_id)

        return {
            "event_id": event_id,
            "organizer_key_revoked": True,
            "access_keys_revoked": revoked_count,
            "wiped": wiped,
            "decommissioned_at": datetime.now(UTC).isoformat(),
        }
