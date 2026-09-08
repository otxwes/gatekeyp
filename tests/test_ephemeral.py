# Copyright (c) 2026 gatekeyp contributors
"""Phase A tests: ephemeral ("lite") events.

Covers the schema migration for existing databases, the ephemeral wipe
machinery, the EphemeralService (creation, public/keyed views, expiry
sweep with an injectable clock, rate limiting) and the lite HTTP routes
(creation funnel, OG page, flyer, keyed attendee view, profile isolation
and invalid-key handling).
"""

import os
import sqlite3
import struct
import sys
import zlib
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.server import create_app
from src.core.content_manager import ContentManager
from src.core.event_lifecycle import EventLifecycleManager
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler
from src.ephemeral import (
    EphemeralService,
    LiteGoneError,
    LiteNotFoundError,
    LiteRateLimiter,
    LiteValidationError,
)

TEST_MASTER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_MASTER_KEY", TEST_MASTER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)


def _png_bytes() -> bytes:
    """A minimal valid 1x1 PNG (stand-in for an uploaded flyer)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


_FLYER = _png_bytes()


class _FakeClock:
    """Advanceable clock standing in for datetime.now(UTC)."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: object) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    db = DatabaseHandler(db_path=":memory:", master_key=TEST_MASTER_KEY)
    yield db
    db.close()


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
def clock():
    """A controllable clock for expiry tests."""
    return _FakeClock(datetime.now(UTC))


@pytest.fixture
def ephemeral(db, lifecycle, content_manager, clock):
    """Create an EphemeralService wired to the fake clock."""
    return EphemeralService(
        db=db, lifecycle=lifecycle, content_manager=content_manager, clock=clock
    )


def _build_app(db, key_manager, content_manager, lifecycle, profile):
    """Build an app for the requested profile with shared services."""
    return create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        profile=profile,
    )


@pytest.fixture
def client(db, key_manager, content_manager, lifecycle):
    """TestClient for the full profile backed by an in-memory database."""
    app = _build_app(db, key_manager, content_manager, lifecycle, "full")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def lite_client(db, key_manager, content_manager, lifecycle):
    """TestClient for the lite (ephemeral-only) profile."""
    app = _build_app(db, key_manager, content_manager, lifecycle, "lite")
    with TestClient(app) as test_client:
        yield test_client


class TestSchemaMigration:
    """Phase A schema lands on fresh and pre-existing databases alike."""

    def test_fresh_schema_has_ephemeral_columns(self, db):
        """New databases get mode/expires_at columns and the tombstones table."""
        db.cursor.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in db.cursor.fetchall()]
        assert "mode" in columns
        assert "expires_at" in columns
        db.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='event_tombstones'"
        )
        assert db.cursor.fetchone() is not None

    def test_new_events_default_to_standard_mode(self, lifecycle):
        """Events created without a mode are standard (non-ephemeral)."""
        created = lifecycle.create_event("Standard", "desc", "org_1")
        event = lifecycle.db.get_event(created["event_id"])
        assert event["mode"] == "standard"
        assert event["expires_at"] is None

    def test_legacy_database_is_migrated(self, tmp_path):
        """A pre-Phase-A database gains the new columns without data loss."""
        legacy = tmp_path / "legacy.db"
        conn = sqlite3.connect(legacy)
        conn.execute(
            "CREATE TABLE events ("
            "event_id TEXT PRIMARY KEY, title TEXT, description TEXT,"
            " organizer_id TEXT, location_data TEXT, created_at TEXT)"
        )
        conn.execute("CREATE TABLE keys (hash_key TEXT PRIMARY KEY, type TEXT, expires_at TEXT)")
        conn.execute(
            "CREATE TABLE content_blocks ("
            "block_id TEXT PRIMARY KEY, event_id TEXT, key_id TEXT,"
            " content_type TEXT, payload TEXT)"
        )
        conn.execute(
            "CREATE TABLE key_content_links ("
            "key_hash TEXT, content_id TEXT, content_type TEXT,"
            " PRIMARY KEY (key_hash, content_id, content_type))"
        )
        conn.execute(
            "INSERT INTO events (event_id, title, description, organizer_id,"
            " location_data, created_at)"
            " VALUES ('legacy_event', 'Old', 'Old desc', 'org_1', NULL, '2020-01-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO keys (hash_key, type, expires_at) VALUES ('legacy_hash', 'master', NULL)"
        )
        conn.commit()
        conn.close()

        db = DatabaseHandler(db_path=str(legacy), master_key=TEST_MASTER_KEY)
        try:
            db.cursor.execute("PRAGMA table_info(events)")
            columns = [row[1] for row in db.cursor.fetchall()]
            assert "mode" in columns
            assert "expires_at" in columns
            db.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='event_tombstones'"
            )
            assert db.cursor.fetchone() is not None
            # Existing rows survived and read back with standard mode
            event = db.get_event("legacy_event")
            assert event is not None
            assert event["title"] == "Old"
            assert event["mode"] == "standard"
            assert event["expires_at"] is None
            # Legacy key row survived the keys-table migration
            assert db.get_key("legacy_hash") is not None
        finally:
            db.close()


class TestWipeEvent:
    """wipe_event removes every trace of an event in one transaction."""

    def _event_with_content(self, content_manager, lifecycle):
        created = lifecycle.create_event("Wipe me", "desc", "org_1")
        event_id = created["event_id"]
        master = created["master_key"]
        lifecycle.add_content_block(master, event_id, "description", "very secret payload")
        content_manager.upload_media(
            input_key=master,
            event_id=event_id,
            filename="flyer.png",
            mime_type="image/png",
            data=_FLYER,
        )
        return event_id, master

    def test_wipe_removes_every_trace(self, db, content_manager, key_manager, lifecycle):
        """Event, blocks, media, links and orphaned keys all disappear."""
        event_id, master = self._event_with_content(content_manager, lifecycle)
        master_hash = key_manager.hash_key(master.removeprefix("local:"))

        counts = db.wipe_event(event_id)

        assert counts["events"] == 1
        assert counts["content_blocks"] == 1
        assert counts["media_assets"] == 1
        assert counts["key_content_links"] >= 2
        assert counts["keys"] >= 1
        assert db.get_event(event_id) is None
        assert db.list_content_blocks_for_event(event_id) == []
        assert db.list_media_assets(event_id) == []
        # The master key existed solely for this event -> deleted
        assert db.get_key(master_hash) is None
        # Tombstone left behind
        tombstone = db.get_tombstone(event_id)
        assert tombstone is not None
        assert tombstone["ended_at"]

    def test_wipe_preserves_keys_shared_with_other_events(self, db, key_manager, lifecycle):
        """A key linked to other events survives the wipe of one event."""
        event_a = lifecycle.create_event("A", "desc", "org_1")["event_id"]
        event_b = lifecycle.create_event("B", "desc", "org_1")["event_id"]
        shared_hash = key_manager.hash_key("shared_access_key_raw")
        db.add_key(shared_hash, "access")
        db.add_key_content_link(shared_hash, event_a, "event")
        db.add_key_content_link(shared_hash, event_b, "event")
        db.add_key_content_link(key_manager.hash_key("other_key_raw"), event_b, "event")

        db.wipe_event(event_a)

        assert db.get_key(shared_hash) is not None
        links = db.get_content_ids_for_key(shared_hash)
        assert [link["content_id"] for link in links] == [event_b]

    def test_wipe_without_tombstone_leaves_no_marker(self, db, lifecycle):
        """tombstone=False (rollback mode) records nothing."""
        created = lifecycle.create_event("Rollback", "desc", "org_1")
        event_id = created["event_id"]

        db.wipe_event(event_id, tombstone=False)

        assert db.get_event(event_id) is None
        assert db.get_tombstone(event_id) is None

    def test_wipe_of_unknown_event_is_harmless(self, db):
        """Wiping a nonexistent event reports zeros and adds no tombstone."""
        counts = db.wipe_event("event_nope")
        assert counts["events"] == 0
        assert db.get_tombstone("event_nope") is None

    def test_set_event_mode_and_expiry_query(self, db, lifecycle):
        """set_event_mode flips the mode; the expiry query finds due events."""
        created = lifecycle.create_event("Ephemeral", "desc", "org_1")
        event_id = created["event_id"]
        past = "2020-01-01T00:00:00+00:00"
        db.set_event_mode(event_id, "ephemeral", past)

        event = db.get_event(event_id)
        assert event["mode"] == "ephemeral"
        assert event["expires_at"] == past
        assert event_id in db.get_expired_event_ids("2030-01-01T00:00:00+00:00")
        assert event_id not in db.get_expired_event_ids("2019-01-01T00:00:00+00:00")


class TestEphemeralService:
    """Service-level behaviour: creation, views, expiry, sweeping."""

    def test_create_lite_event_defaults(self, ephemeral):
        """A lite event is a standard event flagged ephemeral with a deadline."""
        result = ephemeral.create_lite_event("Rooftop set", when="Friday 9pm", where="The roof")
        assert result["event_id"].startswith("event_")
        assert result["master_key"].startswith("local:")
        assert result["flyer_asset_id"] is None
        event = ephemeral.db.get_event(result["event_id"])
        assert event["mode"] == "ephemeral"
        assert event["expires_at"] is not None

    def test_create_lite_event_with_flyer(self, ephemeral):
        """The flyer is uploaded encrypted-at-rest and referenced by asset id."""
        result = ephemeral.create_lite_event(
            "Flyer show", flyer={"filename": "flyer.png", "mime_type": "image/png", "data": _FLYER}
        )
        assert result["flyer_asset_id"] is not None

    def test_ttl_bounds_enforced(self, ephemeral):
        """TTLs below one hour or above 14 days are rejected."""
        with pytest.raises(LiteValidationError):
            ephemeral.create_lite_event("Too short", ttl_hours=0)
        with pytest.raises(LiteValidationError):
            ephemeral.create_lite_event("Too long", ttl_hours=337)

    def test_blank_title_rejected(self, ephemeral):
        """A blank title cannot create an event."""
        with pytest.raises(LiteValidationError):
            ephemeral.create_lite_event("   ")

    def test_public_view_is_live(self, ephemeral):
        """The public view exposes only status, title and the flyer reference."""
        result = ephemeral.create_lite_event(
            "Public", flyer={"filename": "flyer.png", "mime_type": "image/png", "data": _FLYER}
        )
        view = ephemeral.get_public_view(result["event_id"])
        assert view["status"] == "live"
        assert view["event"]["title"] == "Public"
        assert view["flyer_asset_id"] == result["flyer_asset_id"]

    def test_public_view_unknown_event(self, ephemeral):
        """Unknown events raise LiteNotFoundError."""
        with pytest.raises(LiteNotFoundError):
            ephemeral.get_public_view("event_missing")

    def test_standard_events_not_served_by_lite(self, ephemeral, lifecycle):
        """Standard events are invisible to the ephemeral surface."""
        created = lifecycle.create_event("Standard", "desc", "org_1")
        with pytest.raises(LiteNotFoundError):
            ephemeral.get_public_view(created["event_id"])

    def test_keyed_view_with_master_key(self, ephemeral):
        """The master key unlocks description, when and where."""
        result = ephemeral.create_lite_event(
            "Keyed", description="secret desc", when="Sat 8pm", where="Corner"
        )
        view = ephemeral.get_keyed_view(key=result["master_key"], event_id=result["event_id"])
        assert view["event"]["description"] == "secret desc"
        assert view["when"] == "Sat 8pm"
        assert view["where"] == "Corner"
        assert view["expires_at"] is not None

    def test_keyed_view_rejects_unknown_key(self, ephemeral):
        """A well-formed key that unlocks nothing is rejected."""
        result = ephemeral.create_lite_event("Locked")
        with pytest.raises(LiteValidationError):
            ephemeral.get_keyed_view(key="local:" + "ab" * 32, event_id=result["event_id"])

    def test_expired_event_views_fail_closed(self, ephemeral, clock):
        """After the deadline the public view reports expired and keyed access dies."""
        result = ephemeral.create_lite_event("Gone soon", when="soon", ttl_hours=1)
        clock.advance(hours=2)
        assert ephemeral.get_public_view(result["event_id"])["status"] == "expired"
        with pytest.raises(LiteGoneError):
            ephemeral.get_keyed_view(key=result["master_key"], event_id=result["event_id"])

    def test_sweep_wipes_only_expired_events(self, ephemeral, clock):
        """The sweep wipes due events and leaves live events untouched."""
        doomed = ephemeral.create_lite_event("Sweep me", when="soon", where="here", ttl_hours=1)
        kept = ephemeral.create_lite_event("Staying", when="soon", ttl_hours=72)
        clock.advance(hours=2)

        swept = ephemeral.sweep_expired()

        assert swept == [doomed["event_id"]]
        assert ephemeral.db.get_event(doomed["event_id"]) is None
        assert ephemeral.db.get_tombstone(doomed["event_id"]) is not None
        assert ephemeral.db.get_event(kept["event_id"])["mode"] == "ephemeral"

    def test_swept_event_shows_ended_with_tombstone(self, ephemeral, clock):
        """A swept event reads back as ended (honest tombstone page)."""
        result = ephemeral.create_lite_event("Ended", when="soon", ttl_hours=1)
        clock.advance(hours=2)
        ephemeral.sweep_expired()
        view = ephemeral.get_public_view(result["event_id"])
        assert view["status"] == "ended"
        with pytest.raises(LiteGoneError):
            ephemeral.get_keyed_view(key=result["master_key"], event_id=result["event_id"])


class TestLiteRateLimiter:
    """The unauthenticated creation funnel is rate limited per client."""

    def test_blocks_after_max_requests(self):
        ticks = iter(float(i * 10) for i in range(1000))
        limiter = LiteRateLimiter(max_requests=2, window_seconds=600.0, clock=lambda: next(ticks))
        assert limiter.allow("ip1") is True
        assert limiter.allow("ip1") is True
        assert limiter.allow("ip1") is False
        # A different client still has its own allowance
        assert limiter.allow("ip2") is True

    def test_window_expiry_restores_allowance(self):
        state = {"t": 0.0}
        limiter = LiteRateLimiter(max_requests=1, window_seconds=100.0, clock=lambda: state["t"])
        assert limiter.allow("ip1") is True
        assert limiter.allow("ip1") is False
        state["t"] = 200.0  # beyond the window
        assert limiter.allow("ip1") is True


def _create_lite(client, *, with_flyer: bool = False, **overrides: str | int):
    """POST /api/lite/events with sensible defaults."""
    data = {
        "title": overrides.pop("title", "Flyer show"),
        "description": overrides.pop("description", "b-sides only"),
        "when": overrides.pop("when", "Friday 9pm"),
        "where": overrides.pop("where", "The roof"),
        "ttl_hours": overrides.pop("ttl_hours", 48),
        **overrides,
    }
    files = {"flyer": ("flyer.png", _FLYER, "image/png")} if with_flyer else None
    return client.post("/api/lite/events", data=data, files=files)


class TestLiteRoutes:
    """HTTP surface of the ephemeral funnel (full profile)."""

    def test_create_lite_event(self, client):
        """Creating returns the secrets plus shareable URLs."""
        resp = _create_lite(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["event_id"].startswith("event_")
        assert body["master_key"].startswith("local:")
        assert body["public_url"].endswith(f"/i/{body['event_id']}")
        assert "#/organizer/" in body["organizer_url"]
        assert f"k={body['master_key']}" in body["organizer_url"]

    def test_master_key_never_leaks_to_public_page(self, client):
        """The OG page shows the title only - never keys or description."""
        body = _create_lite(client, description="private description").json()
        page = client.get(f"/i/{body['event_id']}")
        assert page.status_code == 200
        assert 'property="og:title"' in page.text
        assert body["master_key"] not in page.text
        assert "private description" not in page.text

    def test_og_page_after_wipe_shows_honest_ended_page(self, client, db):
        """A wiped event renders a noindex 'ended' page, not old content."""
        body = _create_lite(client, title="Doomed Event").json()
        event_id = body["event_id"]
        db.wipe_event(event_id)

        page = client.get(f"/i/{event_id}")
        assert page.status_code == 200
        assert "Event ended" in page.text
        assert "noindex" in page.text
        assert "Doomed" not in page.text

    def test_flyer_served_publicly_without_key(self, client):
        """The flyer is the one public asset; bytes round-trip."""
        body = _create_lite(client, with_flyer=True).json()
        resp = client.get(f"/api/lite/events/{body['event_id']}/flyer")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.headers["cache-control"] == "no-store"
        assert resp.content == _FLYER

    def test_flyer_404_when_absent(self, client):
        """Events without a flyer report 404 on the flyer route."""
        body = _create_lite(client).json()
        resp = client.get(f"/api/lite/events/{body['event_id']}/flyer")
        assert resp.status_code == 404

    def test_keyed_view_with_master_key(self, client):
        """Keyed attendee view returns when/where with a valid master key."""
        body = _create_lite(client).json()
        resp = client.get(
            f"/api/lite/events/{body['event_id']}", params={"key": body["master_key"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event"]["description"] == "b-sides only"
        assert data["when"] == "Friday 9pm"
        assert data["where"] == "The roof"

    def test_keyed_view_with_attendee_access_key(self, client):
        """An access key generated through the standard API unlocks the view."""
        body = _create_lite(client).json()
        resp = client.post(
            f"/api/events/{body['event_id']}/access-keys",
            json={"master_key": body["master_key"], "event_id": body["event_id"], "days": 1},
        )
        assert resp.status_code == 200
        access_key = resp.json()["access_key"]
        keyed = client.get(f"/api/lite/events/{body['event_id']}", params={"key": access_key})
        assert keyed.status_code == 200
        assert keyed.json()["event"]["title"] == "Flyer show"

    def test_keyed_view_rejects_unknown_key(self, client):
        """A well-formed key with no grants yields 400, not 500."""
        body = _create_lite(client).json()
        resp = client.get(
            f"/api/lite/events/{body['event_id']}", params={"key": "local:" + "ab" * 32}
        )
        assert resp.status_code == 400

    def test_malformed_key_is_a_client_error(self, client):
        """InvalidKeyFormatError maps to 400 (was a 500 before Phase A)."""
        body = _create_lite(client).json()
        resp = client.get(
            f"/api/lite/events/{body['event_id']}", params={"key": "not-a-real-key-format"}
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]

    def test_unknown_event_404(self, client):
        """Unknown events are 404 on every lite route."""
        assert client.get("/i/event_missing").status_code == 404
        missing = client.get("/api/lite/events/event_missing", params={"key": "local:" + "ab" * 32})
        assert missing.status_code == 404
        assert client.get("/api/lite/events/event_missing/flyer").status_code == 404

    def test_standard_events_not_exposed_via_lite_routes(self, client):
        """Standard events stay invisible on the lite surface."""
        std = client.post(
            "/api/events",
            json={"title": "Standard", "description": "d", "organizer_id": "org_1"},
        ).json()
        assert client.get(f"/i/{std['event_id']}").status_code == 404
        keyed = client.get(f"/api/lite/events/{std['event_id']}", params={"key": std["master_key"]})
        assert keyed.status_code == 404

    def test_creation_validation_errors(self, client):
        """TTL bounds and the MIME allow-list surface as 400s."""
        assert _create_lite(client, ttl_hours=0).status_code == 400
        wrong_mime = client.post(
            "/api/lite/events",
            data={"title": "Bad flyer"},
            files={"flyer": ("page.html", b"<h1>x</h1>", "text/html")},
        )
        assert wrong_mime.status_code == 400

    def test_rate_limit_kicks_in_on_sixth_event(self, client):
        """Five events per window per client; the sixth is a 429."""
        for i in range(5):
            resp = _create_lite(client, title=f"Event {i}")
            assert resp.status_code == 201
        limited = _create_lite(client, title="Too many")
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers

    def test_lite_profile_hides_standard_api(self, lite_client):
        """The lite profile mounts only the funnel routes and /health."""
        assert lite_client.get("/health").status_code == 200
        created = _create_lite(lite_client, with_flyer=True)
        assert created.status_code == 201
        event_id = created.json()["event_id"]
        # Standard API routes are not mounted
        hidden = lite_client.post(
            "/api/events", json={"title": "Nope", "description": "d", "organizer_id": "o"}
        )
        # Unmatched POSTs fall through to the static mount, which answers 405
        assert hidden.status_code in (404, 405)
        assert lite_client.get(f"/api/events/{event_id}", params={"key": "x"}).status_code == 404
        assert lite_client.get("/api/media/whatever", params={"key": "x"}).status_code == 404
