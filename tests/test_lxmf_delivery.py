# Copyright (c) 2026 gatekeyp contributors
"""Tests for the optional LXMF (mesh) organizer-key delivery prototype.

Covers the message composer, address validation, the deliverer's off and
failure states and the HTTP contract of POST /api/lite/events/{id}/deliver
with a stubbed deliverer (no RNS/LXMF network in unit tests; the loopback
demo script covers the real stack end to end).
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

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
from src.ephemeral.lxmf_delivery import (
    LXMF_DEST_RE,
    LXMFKeyDeliverer,
    compose_key_message,
)

TEST_ORGANIZER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_ORGANIZER_KEY", TEST_ORGANIZER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)

ATTENDEE_ADDRESS = "0123456789abcdef0123456789abcdef"


class StubDeliverer:
    """Stand-in deliverer: no mesh, records what the route asked for."""

    def __init__(self, *, available: bool = True, result: dict[str, str] | None = None) -> None:
        self._available = available
        self._result = result or {"status": "queued", "detail": "queued by stub"}
        self.calls: list[dict[str, Any]] = []

    def available(self) -> bool:
        return self._available

    def send_organizer_key(
        self, destination: str, *, title: str, organizer_key: str, share_url: str, expires_at: str
    ) -> dict[str, str]:
        self.calls.append(
            {
                "destination": destination,
                "title": title,
                "organizer_key": organizer_key,
                "share_url": share_url,
                "expires_at": expires_at,
            }
        )
        return dict(self._result)


def _build_app(db, key_manager, content_manager, lifecycle, deliverer):
    """Build the lite-profile app with the (stub) deliverer injected."""
    return create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        profile="lite",
        lxmf_deliverer=deliverer,
    )


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    db = DatabaseHandler(db_path=":memory:", organizer_key=TEST_ORGANIZER_KEY)
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
def stub_deliverer():
    """A working stub deliverer shared with the lite client fixture."""
    return StubDeliverer()


@pytest.fixture
def lite_client(db, key_manager, content_manager, lifecycle, stub_deliverer):
    """TestClient for the lite profile backed by an in-memory database."""
    app = _build_app(db, key_manager, content_manager, lifecycle, stub_deliverer)
    with TestClient(app) as client:
        yield client


def _future_when() -> str:
    """A time 24h in the future so the fixture never goes stale past validation."""
    return (datetime.now(UTC) + timedelta(hours=24)).isoformat()


def _create_event(client: TestClient) -> dict:
    """Create one lite event through the funnel and return its payload."""
    resp = client.post(
        "/api/lite/events",
        data={
            "title": "Mesh Night",
            "when": _future_when(),
            "ttl_hours": "48",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestComposeMessage:
    """The plaintext body travels inside the encrypted LXMF payload."""

    def test_message_contains_key_link_and_expiry(self):
        text = compose_key_message(
            title="Mesh Night",
            organizer_key="fernet-key-value",
            share_url="https://host/i/event1",
            expires_at="Sep 16, 2026 08:00 UTC",
        )
        assert "Mesh Night" in text
        assert "Organizer key: fernet-key-value" in text
        assert "Share link: https://host/i/event1" in text
        assert "wipes itself Sep 16, 2026 08:00 UTC" in text


class TestDestinationValidation:
    """LXMF addresses are 32 lowercase hex chars (16-byte destination hash)."""

    def test_accepts_32_hex_chars(self):
        assert LXMF_DEST_RE.match(ATTENDEE_ADDRESS)

    def test_rejects_wrong_length_or_charset(self):
        assert not LXMF_DEST_RE.match("0123456789abcdef")
        assert not LXMF_DEST_RE.match("z" * 32)
        assert not LXMF_DEST_RE.match(ATTENDEE_ADDRESS + "ff")


class TestDelivererStates:
    """Off/failure behaviour without starting any network stack."""

    def test_disabled_deliverer_reports_unavailable_and_fails_closed(self, monkeypatch):
        monkeypatch.delenv("GATEKEYP_LXMF_ENABLED", raising=False)
        deliverer = LXMFKeyDeliverer(enabled=False)
        assert deliverer.available() is False
        result = deliverer.send_organizer_key(
            ATTENDEE_ADDRESS,
            title="T",
            organizer_key="k",
            share_url="https://x/i/e",
            expires_at="soon",
        )
        assert result["status"] == "failed"

    def test_startup_failure_is_reported_not_raised(self, tmp_path):
        blocker = tmp_path / "state"
        blocker.write_text("not a directory")  # mkdir below this file must fail
        deliverer = LXMFKeyDeliverer(enabled=True, state_dir=blocker / "lxmf")
        assert deliverer.warmup() is False
        assert deliverer.available() is False  # startup error is sticky


class TestDeliverRoute:
    """POST /api/lite/events/{event_id}/deliver with a stubbed deliverer."""

    def test_create_response_exposes_mesh_flag(self, lite_client):
        payload = _create_event(lite_client)
        assert payload["mesh_delivery_available"] is True

    def test_returns_503_when_mesh_disabled(self, db, key_manager, content_manager, lifecycle):
        app = _build_app(
            db, key_manager, content_manager, lifecycle, StubDeliverer(available=False)
        )
        with TestClient(app) as client:
            _create_event(client)
            resp = client.post(
                "/api/lite/events/x/deliver",
                json={"destination": ATTENDEE_ADDRESS, "organizer_key": "k"},
            )
        assert resp.status_code == 503

    def test_rejects_malformed_address(self, lite_client):
        _create_event(lite_client)
        resp = lite_client.post(
            "/api/lite/events/whatever/deliver",
            json={"destination": "0123", "organizer_key": "k"},
        )
        assert resp.status_code == 400
        assert "32 hex" in resp.json()["detail"]

    def test_unknown_event_is_404(self, lite_client):
        resp = lite_client.post(
            "/api/lite/events/missing/deliver",
            json={"destination": ATTENDEE_ADDRESS, "organizer_key": "k"},
        )
        assert resp.status_code == 404

    def test_wrong_key_is_400(self, lite_client):
        created = _create_event(lite_client)
        resp = lite_client.post(
            f"/api/lite/events/{created['event_id']}/deliver",
            json={
                "destination": ATTENDEE_ADDRESS,
                "organizer_key": Fernet.generate_key().decode(),
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "does not grant access" in detail or "Invalid key format" in detail

    def test_successful_queue_relays_request(self, lite_client, stub_deliverer):
        created = _create_event(lite_client)
        resp = lite_client.post(
            f"/api/lite/events/{created['event_id']}/deliver",
            json={
                "destination": ATTENDEE_ADDRESS.upper(),
                "organizer_key": created["organizer_key"],
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "queued", "detail": "queued by stub"}
        call = stub_deliverer.calls[-1]
        assert call["destination"] == ATTENDEE_ADDRESS  # normalised to lowercase
        assert call["organizer_key"] == created["organizer_key"]
        assert call["title"] == "Mesh Night"
        assert call["share_url"].endswith(f"/i/{created['event_id']}")
        assert call["expires_at"]  # human-readable wipe stamp

    def test_failed_send_maps_to_502(self, db, key_manager, content_manager, lifecycle):
        deliverer = StubDeliverer(result={"status": "failed", "detail": "no path yet"})
        app = _build_app(db, key_manager, content_manager, lifecycle, deliverer)
        with TestClient(app) as client:
            created = _create_event(client)
            resp = client.post(
                f"/api/lite/events/{created['event_id']}/deliver",
                json={"destination": ATTENDEE_ADDRESS, "organizer_key": created["organizer_key"]},
            )
        assert resp.status_code == 502
        assert resp.json()["detail"] == "no path yet"

    def test_real_deliverer_off_by_default_is_503(
        self, db, key_manager, content_manager, lifecycle, monkeypatch
    ):
        monkeypatch.delenv("GATEKEYP_LXMF_ENABLED", raising=False)
        app = _build_app(db, key_manager, content_manager, lifecycle, None)
        with TestClient(app) as client:
            _create_event(client)
            resp = client.post(
                "/api/lite/events/missing/deliver",
                json={"destination": ATTENDEE_ADDRESS, "organizer_key": "k"},
            )
        assert resp.status_code == 503
