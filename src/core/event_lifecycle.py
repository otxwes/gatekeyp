# Copyright (c) 2026 Gatekeyp contributors

import secrets
from datetime import UTC, datetime, timedelta

from src.core.content_manager import ContentManager
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# Default key lifetime for access keys (30 days)
DEFAULT_ACCESS_KEY_DAYS = 30

# Default key lifetime for master keys (365 days)
DEFAULT_MASTER_KEY_DAYS = 365

# Error message for master key not granting access to an event
_ACCESS_DENIED_MSG = "Master key does not grant access to this event"


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
    ) -> None:
        """
        Initialize the EventLifecycleManager.

        Args:
            db: Shared DatabaseHandler instance.
            key_manager: Shared KeyManager instance.
            content_manager: Shared ContentManager instance.
        """
        self.db = db
        self.key_manager = key_manager
        self.content_manager = content_manager

    # ------------------------------------------------------------------
    # ID Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_id(prefix: str) -> str:
        """Generate a unique ID with a prefix."""
        return f"{prefix}_{secrets.token_hex(16)}"

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
        master_key_days: int = DEFAULT_MASTER_KEY_DAYS,
    ) -> dict:
        """
        Create a new event with a master key.

        The master key grants full access to all event content and
        can be used to generate attendee access keys.

        Args:
            title: Event title.
            description: Event description.
            organizer_id: Identifier of the organizer (e.g., @user:instance).
            location_data: Optional location data (e.g., coordinates).
            master_key_days: Lifetime of the master key in days.

        Returns:
            Event metadata including the master key (shown once).
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

        # Create the event record
        self.db.add_event(
            event_id=event_id,
            title=title,
            description=description,
            organizer_id=organizer_id,
            location_data=location_data,
        )

        # Generate a master key for this event
        master_key = self.key_manager.generate_key()
        master_hash = self.key_manager.hash_key(master_key)
        expires_at = (datetime.now(UTC) + timedelta(days=master_key_days)).isoformat()

        self.db.add_key(
            hash_key=master_hash,
            key_type="master",
            expires_at=expires_at,
            owner_id=organizer_id,
        )

        # Link the master key to the event
        self.db.add_key_content_link(master_hash, event_id, "event")

        return {
            "event_id": event_id,
            "title": title,
            "description": description,
            "organizer_id": organizer_id,
            "master_key": f"local:{master_key}",
            "master_key_hash": master_hash,
            "expires_at": expires_at,
        }

    # ------------------------------------------------------------------
    # Content Upload
    # ------------------------------------------------------------------

    def add_content_block(
        self,
        master_key: str,
        event_id: str,
        content_type: str,
        payload: str,
    ) -> dict:
        """
        Add a content block (description, location, schedule, etc.) to an event.

        Args:
            master_key: The event's master key.
            event_id: The event ID.
            content_type: Type of content (e.g., "description", "schedule").
            payload: The content payload.

        Returns:
            The created content block metadata.
        """
        # Verify the master key grants access to the event
        validation = self.key_manager.validate_key(master_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid master key")
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

    def get_event_details(self, master_key: str, event_id: str) -> dict:
        """
        Retrieve full event details including all content blocks.

        Args:
            master_key: The event's master key.
            event_id: The event ID.

        Returns:
            Event details with all content blocks.
        """
        # Verify the master key grants access to the event
        validation = self.key_manager.validate_key(master_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid master key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        event = self.db.get_event(event_id)
        if event is None:
            message = "Event not found"
            raise EventLifecycleError(message)

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

    # ------------------------------------------------------------------
    # Access Management
    # ------------------------------------------------------------------

    def generate_access_key(
        self,
        master_key: str,
        event_id: str,
        *,
        days: int = DEFAULT_ACCESS_KEY_DAYS,
        owner_id: str | None = None,
    ) -> dict:
        """
        Generate an attendee access key for an event.

        The access key grants access to all content linked to the event.

        Args:
            master_key: The event's master key (must be valid).
            event_id: The event ID.
            days: Lifetime of the access key in days.
            owner_id: Optional identifier of the key owner.

        Returns:
            The generated access key (shown once).
        """
        # Verify the master key grants access to the event
        validation = self.key_manager.validate_key(master_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid master key")
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

    def list_access_keys(
        self,
        master_key: str,
        event_id: str,
    ) -> list[dict]:
        """
        List all access keys for an event.

        Args:
            master_key: The event's master key.
            event_id: The event ID.

        Returns:
            List of access key metadata (no raw keys).
        """
        # Verify the master key grants access to the event
        validation = self.key_manager.validate_key(master_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid master key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Get all keys linked to this event's content
        all_keys = self.db.list_keys()
        event_keys = []
        for key in all_keys:
            if key["type"] == "access":
                key_content = self.db.get_content_ids_for_key(key["hash_key"])
                if any(c["content_id"] == event_id for c in key_content):
                    event_keys.append(key)

        return event_keys

    def revoke_access_key(
        self,
        master_key: str,
        event_id: str,
        access_key: str,
    ) -> bool:
        """
        Revoke an attendee access key.

        Args:
            master_key: The event's master key.
            event_id: The event ID.
            access_key: The raw access key to revoke.

        Returns:
            True if the key was revoked.
        """
        # Verify the master key grants access to the event
        validation = self.key_manager.validate_key(master_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid master key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Revoke the access key
        return self.key_manager.revoke_key(access_key)

    # ------------------------------------------------------------------
    # Event Decommissioning
    # ------------------------------------------------------------------

    def decommission_event(
        self,
        master_key: str,
        event_id: str,
    ) -> dict:
        """
        Decommission an event: revoke all keys and mark the event as inactive.

        Args:
            master_key: The event's master key.
            event_id: The event ID.

        Returns:
            Summary of the decommissioning.
        """
        # Verify the master key grants access to the event
        validation = self.key_manager.validate_key(master_key)
        if validation["status"] != "valid":
            message = validation.get("message", "Invalid master key")
            raise EventLifecycleError(message)

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == event_id for c in content_ids):
            raise EventLifecycleError(_ACCESS_DENIED_MSG)

        # Revoke the master key
        self.db.revoke_key(key_hash)

        # Revoke all access keys linked to this event's content
        revoked_count = 0
        all_keys = self.db.list_keys()
        for key in all_keys:
            if key["type"] == "access" and not key["revoked"]:
                key_content = self.db.get_content_ids_for_key(key["hash_key"])
                if any(c["content_id"] == event_id for c in key_content):
                    self.db.revoke_key(key["hash_key"])
                    revoked_count += 1

        return {
            "event_id": event_id,
            "master_key_revoked": True,
            "access_keys_revoked": revoked_count,
            "decommissioned_at": datetime.now(UTC).isoformat(),
        }
