# Copyright (c) 2026 Gatekeyp contributors

import os
import sys

import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet

from src.core.content_manager import ContentManager
from src.core.event_lifecycle import EventLifecycleError, EventLifecycleManager
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# Generate a valid Fernet key for tests
TEST_MASTER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_MASTER_KEY", TEST_MASTER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    handler = DatabaseHandler(db_path=":memory:", master_key=TEST_MASTER_KEY)
    yield handler
    handler.close()


@pytest.fixture
def key_manager(db):
    """Create a KeyManager with the test database."""
    return KeyManager(db=db, hmac_secret=TEST_HMAC_SECRET)


@pytest.fixture
def content_manager(db, key_manager):
    """Create a ContentManager with the test database."""
    return ContentManager(db=db, key_manager=key_manager)


@pytest.fixture
def lifecycle(db, key_manager, content_manager):
    """Create an EventLifecycleManager with the test database."""
    return EventLifecycleManager(db=db, key_manager=key_manager, content_manager=content_manager)


@pytest.fixture
def created_event(lifecycle):
    """Create an event and return the event metadata."""
    return lifecycle.create_event(
        title="Test Event",
        description="A test event for lifecycle management",
        organizer_id="@organizer:test",
        location_data="40.7128,-74.0060",
    )


# ------------------------------------------------------------------
# Event Creation
# ------------------------------------------------------------------


class TestCreateEvent:
    def test_create_event_returns_master_key(self, lifecycle):
        """Creating an event returns a master key."""
        result = lifecycle.create_event(
            title="My Event",
            description="Event description",
            organizer_id="@user:test",
        )

        assert result["event_id"].startswith("event_")
        assert result["title"] == "My Event"
        assert result["organizer_id"] == "@user:test"
        assert result["master_key"].startswith("local:")
        assert result["master_key_hash"]
        assert result["expires_at"]

    def test_create_event_stores_event_in_db(self, lifecycle, db):
        """The event record is persisted in the database."""
        result = lifecycle.create_event(
            title="Persisted Event",
            description="Will be stored",
            organizer_id="@user:test",
        )

        event = db.get_event(result["event_id"])
        assert event is not None
        assert event["title"] == "Persisted Event"

    def test_create_event_links_master_key(self, lifecycle, db):
        """The master key is linked to the event."""
        result = lifecycle.create_event(
            title="Linked Event",
            description="Key should be linked",
            organizer_id="@user:test",
        )

        content_ids = db.get_content_ids_for_key(result["master_key_hash"])
        assert any(c["content_id"] == result["event_id"] for c in content_ids)

    def test_create_event_empty_title_raises(self, lifecycle):
        """Empty title raises an error."""
        with pytest.raises(EventLifecycleError, match="title"):
            lifecycle.create_event(
                title="   ",
                description="Valid description",
                organizer_id="@user:test",
            )

    def test_create_event_empty_description_raises(self, lifecycle):
        """Empty description raises an error."""
        with pytest.raises(EventLifecycleError, match="description"):
            lifecycle.create_event(
                title="Valid Title",
                description="",
                organizer_id="@user:test",
            )

    def test_create_event_empty_organizer_raises(self, lifecycle):
        """Empty organizer ID raises an error."""
        with pytest.raises(EventLifecycleError, match="Organizer"):
            lifecycle.create_event(
                title="Valid Title",
                description="Valid description",
                organizer_id="",
            )


# ------------------------------------------------------------------
# Content Upload
# ------------------------------------------------------------------


class TestAddContentBlock:
    def test_add_content_block_success(self, lifecycle, created_event):
        """Adding a content block with the master key succeeds."""
        result = lifecycle.add_content_block(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            content_type="description",
            payload="This is the event description",
        )

        assert result["id"].startswith("block_")
        assert result["event_id"] == created_event["event_id"]
        assert result["content_type"] == "description"

    def test_add_content_block_invalid_key(self, lifecycle, created_event):
        """Adding content with an invalid key raises an error."""
        with pytest.raises(EventLifecycleError, match="does not exist"):
            lifecycle.add_content_block(
                master_key="local:invalid-key-1234567890",
                event_id=created_event["event_id"],
                content_type="description",
                payload="Should fail",
            )

    def test_add_content_block_wrong_event(self, lifecycle, created_event):
        """Adding content to a different event raises an error."""
        # Create a second event
        other_event = lifecycle.create_event(
            title="Other Event",
            description="Different event",
            organizer_id="@user:test",
        )

        with pytest.raises(EventLifecycleError, match="does not grant"):
            lifecycle.add_content_block(
                master_key=created_event["master_key"],
                event_id=other_event["event_id"],
                content_type="description",
                payload="Should fail",
            )

    def test_get_event_details_returns_content(self, lifecycle, created_event):
        """Getting event details returns all content blocks."""
        lifecycle.add_content_block(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            content_type="description",
            payload="Event description",
        )
        lifecycle.add_content_block(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            content_type="schedule",
            payload="Day 1: Registration",
        )

        details = lifecycle.get_event_details(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        assert details["event"]["title"] == "Test Event"
        assert len(details["content_blocks"]) == 2
        types = {b["content_type"] for b in details["content_blocks"]}
        assert types == {"description", "schedule"}


# ------------------------------------------------------------------
# Access Key Management
# ------------------------------------------------------------------


class TestAccessKeys:
    def test_generate_access_key(self, lifecycle, created_event):
        """Generating an access key returns a valid key."""
        result = lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            days=7,
            owner_id="@attendee:test",
        )

        assert result["access_key"].startswith("local:")
        assert result["access_key_hash"]
        assert result["event_id"] == created_event["event_id"]
        assert result["expires_at"]

    def test_generate_access_key_invalid_master(self, lifecycle, created_event):
        """Generating an access key with an invalid master key fails."""
        with pytest.raises(EventLifecycleError, match="does not exist"):
            lifecycle.generate_access_key(
                master_key="local:bad-master-key-1234567890",
                event_id=created_event["event_id"],
            )

    def test_generate_access_key_wrong_event(self, lifecycle, created_event):
        """Generating an access key for a different event fails."""
        other_event = lifecycle.create_event(
            title="Other Event",
            description="Different event",
            organizer_id="@user:test",
        )

        with pytest.raises(EventLifecycleError, match="does not grant"):
            lifecycle.generate_access_key(
                master_key=created_event["master_key"],
                event_id=other_event["event_id"],
            )

    def test_access_key_can_access_content(self, lifecycle, created_event):
        """An access key can access the event's content."""
        # Add content with the master key
        lifecycle.add_content_block(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            content_type="description",
            payload="Secret content",
        )

        # Generate an access key
        access = lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        # The access key should validate
        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "valid"

    def test_list_access_keys(self, lifecycle, created_event):
        """Listing access keys returns all generated keys."""
        lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            owner_id="@alice:test",
        )
        lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            owner_id="@bob:test",
        )

        keys = lifecycle.list_access_keys(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        assert len(keys) == 2
        assert all(k["type"] == "access" for k in keys)

    def test_revoke_access_key(self, lifecycle, created_event):
        """Revoking an access key makes it invalid."""
        access = lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        # Key is valid before revocation
        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "valid"

        # Revoke it
        revoked = lifecycle.revoke_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
            access_key=access["access_key"],
        )
        assert revoked is True

        # Key is invalid after revocation
        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "invalid"
        assert "revoked" in validation["message"]


# ------------------------------------------------------------------
# Decommissioning
# ------------------------------------------------------------------


class TestDecommission:
    def test_decommission_revokes_master_key(self, lifecycle, created_event):
        """Decommissioning revokes the master key."""
        result = lifecycle.decommission_event(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        assert result["event_id"] == created_event["event_id"]
        assert result["master_key_revoked"] is True

        # Master key is now invalid
        validation = lifecycle.key_manager.validate_key(created_event["master_key"])
        assert validation["status"] == "invalid"

    def test_decommission_revokes_access_keys(self, lifecycle, created_event):
        """Decommissioning revokes all access keys."""
        access1 = lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )
        access2 = lifecycle.generate_access_key(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        result = lifecycle.decommission_event(
            master_key=created_event["master_key"],
            event_id=created_event["event_id"],
        )

        assert result["access_keys_revoked"] == 2

        # Both access keys are now invalid
        assert lifecycle.key_manager.validate_key(access1["access_key"])["status"] == "invalid"
        assert lifecycle.key_manager.validate_key(access2["access_key"])["status"] == "invalid"

    def test_decommission_invalid_master(self, lifecycle, created_event):
        """Decommissioning with an invalid master key fails."""
        with pytest.raises(EventLifecycleError, match="does not exist"):
            lifecycle.decommission_event(
                master_key="local:bad-master-key-1234567890",
                event_id=created_event["event_id"],
            )

    def test_decommission_wrong_event(self, lifecycle, created_event):
        """Decommissioning a different event with the wrong master key fails."""
        other_event = lifecycle.create_event(
            title="Other Event",
            description="Different event",
            organizer_id="@user:test",
        )

        with pytest.raises(EventLifecycleError, match="does not grant"):
            lifecycle.decommission_event(
                master_key=created_event["master_key"],
                event_id=other_event["event_id"],
            )
