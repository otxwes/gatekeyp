# Copyright (c) 2026 gatekeyp contributors

import os
import sys

import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet

from src.core.content_manager import ContentManager
from src.core.event_lifecycle import EventLifecycleError, EventLifecycleManager
from src.core.geocoding import GeoPoint
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# Generate a valid Fernet key for tests
TEST_ORGANIZER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_ORGANIZER_KEY", TEST_ORGANIZER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    handler = DatabaseHandler(db_path=":memory:", organizer_key=TEST_ORGANIZER_KEY)
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
    def test_create_event_returns_organizer_key(self, lifecycle):
        """Creating an event returns a organizer key."""
        result = lifecycle.create_event(
            title="My Event",
            description="Event description",
            organizer_id="@user:test",
        )

        assert result["event_id"].startswith("event_")
        assert result["title"] == "My Event"
        assert result["organizer_id"] == "@user:test"
        assert result["organizer_key"].startswith("local:")
        assert result["organizer_key_hash"]
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

    def test_create_event_links_organizer_key(self, lifecycle, db):
        """The organizer key is linked to the event."""
        result = lifecycle.create_event(
            title="Linked Event",
            description="Key should be linked",
            organizer_id="@user:test",
        )

        content_ids = db.get_content_ids_for_key(result["organizer_key_hash"])
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
        """Adding a content block with the organizer key succeeds."""
        result = lifecycle.add_content_block(
            organizer_key=created_event["organizer_key"],
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
                organizer_key="local:invalid-key-1234567890",
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
                organizer_key=created_event["organizer_key"],
                event_id=other_event["event_id"],
                content_type="description",
                payload="Should fail",
            )

    def test_get_event_details_returns_content(self, lifecycle, created_event):
        """Getting event details returns all content blocks."""
        lifecycle.add_content_block(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            content_type="description",
            payload="Event description",
        )
        lifecycle.add_content_block(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            content_type="schedule",
            payload="Day 1: Registration",
        )

        details = lifecycle.get_event_details(
            organizer_key=created_event["organizer_key"],
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
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            days=7,
            owner_id="@attendee:test",
        )

        assert result["access_key"].startswith("local:")
        assert result["access_key_hash"]
        assert result["event_id"] == created_event["event_id"]
        assert result["expires_at"]

    def test_generate_access_key_invalid_organizer(self, lifecycle, created_event):
        """Generating an access key with an invalid organizer key fails."""
        with pytest.raises(EventLifecycleError, match="does not exist"):
            lifecycle.generate_access_key(
                organizer_key="local:bad-organizer-key-1234567890",
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
                organizer_key=created_event["organizer_key"],
                event_id=other_event["event_id"],
            )

    def test_access_key_can_access_content(self, lifecycle, created_event):
        """An access key can access the event's content."""
        # Add content with the organizer key
        lifecycle.add_content_block(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            content_type="description",
            payload="Secret content",
        )

        # Generate an access key
        access = lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )

        # The access key should validate
        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "valid"

    def test_list_access_keys(self, lifecycle, created_event):
        """Listing access keys returns all generated keys."""
        lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            owner_id="@alice:test",
        )
        lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            owner_id="@bob:test",
        )

        keys = lifecycle.list_access_keys(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )

        assert len(keys) == 2
        assert all(k["type"] == "access" for k in keys)

    def test_revoke_access_key(self, lifecycle, created_event):
        """Revoking an access key makes it invalid."""
        access = lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )

        # Key is valid before revocation
        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "valid"

        # Revoke it
        revoked = lifecycle.revoke_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            access_key=access["access_key"],
        )
        assert revoked is True

        # Key is invalid after revocation
        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "invalid"
        assert "revoked" in validation["message"]

    def test_revoke_access_key_by_hash(self, lifecycle, created_event):
        """Revoking an access key by its stored hash (organizer holds no raw key)."""
        access = lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )
        key_hash = lifecycle.key_manager.validate_key(access["access_key"])["hash"]

        assert lifecycle.key_manager.validate_key(access["access_key"])["status"] == "valid"
        revoked = lifecycle.revoke_access_key_by_hash(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            key_hash=key_hash,
        )
        assert revoked is True

        validation = lifecycle.key_manager.validate_key(access["access_key"])
        assert validation["status"] == "invalid"
        assert "revoked" in validation["message"]

    def test_revoke_access_key_by_hash_not_in_event(self, lifecycle, created_event):
        """A hash not linked to this event is rejected (defends against cross-event revoke)."""
        with pytest.raises(EventLifecycleError, match="does not belong"):
            lifecycle.revoke_access_key_by_hash(
                organizer_key=created_event["organizer_key"],
                event_id=created_event["event_id"],
                key_hash="0" * 64,
            )

    def test_generate_access_keys_bulk(self, lifecycle, created_event):
        """Bulk generation mints the requested number of named keys."""
        owners = ["Ava", "Ben", "Cal"]
        results = lifecycle.generate_access_keys_bulk(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
            count=3,
            days=14,
            owners=owners,
        )
        assert len(results) == 3
        for result, owner in zip(results, owners, strict=True):
            assert result["access_key"].startswith("local:")
            assert result["owner_id"] == owner
            assert result["expires_at"]
            # Each minted key is usable for the event.
            validation = lifecycle.key_manager.validate_key(result["access_key"])
            assert validation["status"] == "valid"

    def test_generate_access_keys_bulk_bad_count(self, lifecycle, created_event):
        """Bulk generation rejects out-of-range counts."""
        with pytest.raises(EventLifecycleError, match="count must be between"):
            lifecycle.generate_access_keys_bulk(
                organizer_key=created_event["organizer_key"],
                event_id=created_event["event_id"],
                count=0,
                days=14,
            )


# ------------------------------------------------------------------
# Decommissioning
# ------------------------------------------------------------------


class TestDecommission:
    def test_decommission_revokes_organizer_key(self, lifecycle, created_event):
        """Decommissioning revokes the organizer key."""
        result = lifecycle.decommission_event(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )

        assert result["event_id"] == created_event["event_id"]
        assert result["organizer_key_revoked"] is True

        # Organizer key is now invalid
        validation = lifecycle.key_manager.validate_key(created_event["organizer_key"])
        assert validation["status"] == "invalid"

    def test_decommission_revokes_access_keys(self, lifecycle, created_event):
        """Decommissioning revokes all access keys."""
        access1 = lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )
        access2 = lifecycle.generate_access_key(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )

        result = lifecycle.decommission_event(
            organizer_key=created_event["organizer_key"],
            event_id=created_event["event_id"],
        )

        assert result["access_keys_revoked"] == 2

        # Both access keys are now invalid
        assert lifecycle.key_manager.validate_key(access1["access_key"])["status"] == "invalid"
        assert lifecycle.key_manager.validate_key(access2["access_key"])["status"] == "invalid"

    def test_decommission_wipes_event_and_leaves_tombstone(self, lifecycle, db, created_event):
        """Decommissioning wipes the event and leaves an ended tombstone."""
        event_id = created_event["event_id"]
        lifecycle.decommission_event(
            organizer_key=created_event["organizer_key"],
            event_id=event_id,
        )

        # Every trace of the event is gone; only the tombstone remains so
        # the RSVP funnel reports the event as ended instead of live.
        assert db.get_event(event_id) is None
        assert db.get_tombstone(event_id) is not None
        assert db.list_rsvps(event_id) == []

    def test_decommission_invalid_organizer(self, lifecycle, created_event):
        """Decommissioning with an invalid organizer key fails."""
        with pytest.raises(EventLifecycleError, match="does not exist"):
            lifecycle.decommission_event(
                organizer_key="local:bad-organizer-key-1234567890",
                event_id=created_event["event_id"],
            )

    def test_decommission_wrong_event(self, lifecycle, created_event):
        """Decommissioning a different event with the wrong organizer key fails."""
        other_event = lifecycle.create_event(
            title="Other Event",
            description="Different event",
            organizer_id="@user:test",
        )

        with pytest.raises(EventLifecycleError, match="does not grant"):
            lifecycle.decommission_event(
                organizer_key=created_event["organizer_key"],
                event_id=other_event["event_id"],
            )


# ------------------------------------------------------------------
# Directions map
# ------------------------------------------------------------------


class FakeGeocoder:
    """Records calls and returns a configurable point."""

    def __init__(self, point: GeoPoint | None = None) -> None:
        self.point = point
        self.calls: list[str] = []

    def geocode(self, address: str) -> GeoPoint | None:
        self.calls.append(address)
        return self.point


@pytest.fixture
def map_geocoder():
    return FakeGeocoder(GeoPoint(40.75, -73.98))


@pytest.fixture
def map_lifecycle(db, key_manager, content_manager, map_geocoder):
    return EventLifecycleManager(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        geocoder=map_geocoder,
        map_style_url="https://example.test/style.json",
    )


class TestEventMap:
    def test_create_event_geocodes_when_map_on(self, map_lifecycle, map_geocoder, db):
        result = map_lifecycle.create_event(
            title="Mapped Event",
            description="Has a map",
            organizer_id="@organizer:test",
            location_data="Main St",
        )

        assert result["show_map"] is True
        assert result["map_available"] is True
        assert map_geocoder.calls == ["Main St"]
        event = db.get_event(result["event_id"])
        assert event["location_lat"] == 40.75
        assert event["location_lon"] == -73.98

    def test_create_event_skips_geocode_when_map_off(self, map_lifecycle, map_geocoder, db):
        result = map_lifecycle.create_event(
            title="No Map Event",
            description="Map off",
            organizer_id="@organizer:test",
            location_data="Main St",
            show_map=False,
        )

        assert result["show_map"] is False
        assert result["map_available"] is False
        assert map_geocoder.calls == []
        event = db.get_event(result["event_id"])
        assert event["location_lat"] is None
        assert event["location_lon"] is None

    def test_create_event_survives_geocode_failure(self, db, key_manager, content_manager):
        geocoder = FakeGeocoder()
        lifecycle = EventLifecycleManager(
            db=db,
            key_manager=key_manager,
            content_manager=content_manager,
            geocoder=geocoder,
            map_style_url="https://example.test/style.json",
        )

        result = lifecycle.create_event(
            title="Failed Geocode",
            description="Still created",
            organizer_id="@organizer:test",
            location_data="Nowhere",
        )

        assert result["map_available"] is False
        event = db.get_event(result["event_id"])
        assert event["location_lat"] is None
        assert event["location_lon"] is None

    def test_create_event_without_geocoder_has_no_map(self, lifecycle, db):
        result = lifecycle.create_event(
            title="No Geocoder",
            description="No map",
            organizer_id="@organizer:test",
            location_data="Main St",
        )

        assert result["map_available"] is False
        event = db.get_event(result["event_id"])
        assert event["location_lat"] is None
        assert event["location_lon"] is None

    def test_set_event_map_rejects_non_organizer_key(self, map_lifecycle):
        created = map_lifecycle.create_event(
            title="Guarded Event",
            description="Only the organizer may toggle",
            organizer_id="@organizer:test",
            location_data="Main St",
        )
        access = map_lifecycle.generate_access_key(created["organizer_key"], created["event_id"])

        with pytest.raises(EventLifecycleError, match="does not grant"):
            map_lifecycle.set_event_map(access["access_key"], created["event_id"], show_map=False)

    def test_set_event_map_off_keeps_coordinates(self, map_lifecycle, db):
        created = map_lifecycle.create_event(
            title="Toggle Off",
            description="Keep coordinates",
            organizer_id="@organizer:test",
            location_data="Main St",
        )

        result = map_lifecycle.set_event_map(
            created["organizer_key"], created["event_id"], show_map=False
        )

        assert result == {"show_map": False, "map_available": False}
        event = db.get_event(created["event_id"])
        assert event["location_lat"] == 40.75
        assert event["location_lon"] == -73.98
        assert event["show_map"] is False

    def test_set_event_map_on_geocodes_missing_coordinates(self, map_lifecycle, map_geocoder, db):
        created = map_lifecycle.create_event(
            title="Toggle On",
            description="Geocode later",
            organizer_id="@organizer:test",
            location_data="Main St",
            show_map=False,
        )
        assert map_geocoder.calls == []

        result = map_lifecycle.set_event_map(
            created["organizer_key"], created["event_id"], show_map=True
        )

        assert result == {"show_map": True, "map_available": True}
        assert map_geocoder.calls == ["Main St"]
        event = db.get_event(created["event_id"])
        assert event["location_lat"] == 40.75
        assert event["location_lon"] == -73.98

    def test_set_event_map_on_without_location_raises(self, map_lifecycle):
        created = map_lifecycle.create_event(
            title="No Location",
            description="Cannot map",
            organizer_id="@organizer:test",
        )

        with pytest.raises(EventLifecycleError, match="no location"):
            map_lifecycle.set_event_map(
                created["organizer_key"], created["event_id"], show_map=True
            )

    def test_set_event_map_on_geocode_failure_returns_unavailable(
        self, db, key_manager, content_manager
    ):
        geocoder = FakeGeocoder()
        lifecycle = EventLifecycleManager(
            db=db,
            key_manager=key_manager,
            content_manager=content_manager,
            geocoder=geocoder,
            map_style_url="https://example.test/style.json",
        )
        created = lifecycle.create_event(
            title="Failed Toggle",
            description="No coordinates",
            organizer_id="@organizer:test",
            location_data="Nowhere",
            show_map=False,
        )

        result = lifecycle.set_event_map(
            created["organizer_key"], created["event_id"], show_map=True
        )

        assert result == {"show_map": True, "map_available": False}
        event = db.get_event(created["event_id"])
        assert event["location_lat"] is None
        assert event["location_lon"] is None
