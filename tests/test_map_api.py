# Copyright (c) 2026 gatekeyp contributors

"""HTTP tests for the directions-map config, toggle route and door response."""

import os
import sys

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.gateway import Gateway, RateLimiter
from src.api.server import create_app
from src.core.content_manager import ContentManager
from src.core.event_lifecycle import EventLifecycleManager
from src.core.geocoding import GeoPoint
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

TEST_ORGANIZER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"
MAP_STYLE_URL = "https://example.test/style.json"

os.environ.setdefault("GATEKEYP_ORGANIZER_KEY", TEST_ORGANIZER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)


class FakeGeocoder:
    """Returns a fixed point and records every lookup."""

    def __init__(self, point: GeoPoint | None = None) -> None:
        self.point = point or GeoPoint(40.75, -73.98)
        self.calls: list[str] = []

    def geocode(self, address: str) -> GeoPoint | None:
        self.calls.append(address)
        return self.point


def _build_env(
    *, map_style_url: str | None
) -> tuple[TestClient, DatabaseHandler, FakeGeocoder, EventLifecycleManager]:
    db = DatabaseHandler(db_path=":memory:", organizer_key=TEST_ORGANIZER_KEY)
    key_manager = KeyManager(db=db, hmac_secret=TEST_HMAC_SECRET)
    content_manager = ContentManager(db=db, key_manager=key_manager)
    geocoder = FakeGeocoder()
    lifecycle = EventLifecycleManager(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        geocoder=geocoder if map_style_url else None,
        map_style_url=map_style_url,
    )
    gateway = Gateway(
        db=db,
        key_manager=key_manager,
        rate_limiter=RateLimiter(),
        map_style_url=map_style_url,
    )
    app = create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        gateway=gateway,
    )
    return TestClient(app), db, geocoder, lifecycle


@pytest.fixture
def map_env(monkeypatch):
    monkeypatch.setenv("GATEKEYP_MAP_STYLE_URL", "")
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", "")
    client, db, geocoder, lifecycle = _build_env(map_style_url=MAP_STYLE_URL)
    with client:
        yield {"client": client, "db": db, "geocoder": geocoder, "lifecycle": lifecycle}
    db.close()


@pytest.fixture
def no_map_client(monkeypatch):
    monkeypatch.setenv("GATEKEYP_MAP_STYLE_URL", "")
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", "")
    client, db, _geocoder, _lifecycle = _build_env(map_style_url=None)
    with client:
        yield client
    db.close()


def _create_event(client: TestClient, **overrides: object):
    body = {
        "title": "Mapped Event",
        "description": "A test event",
        "organizer_id": "@organizer:test",
        "location_data": "Main St",
    }
    body.update(overrides)
    response = client.post("/api/events", json=body)
    assert response.status_code == 200
    return response.json()


def _access(client: TestClient, created: dict):
    response = client.post(
        "/api/access",
        json={"key": created["organizer_key"], "content_id": created["event_id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    return body["data"]


def test_create_event_defaults_show_map_true(map_env):
    created = _create_event(map_env["client"])

    assert created["show_map"] is True
    assert created["map_available"] is True
    assert map_env["geocoder"].calls == ["Main St"]
    event = map_env["db"].get_event(created["event_id"])
    assert event["location_lat"] == 40.75
    assert event["location_lon"] == -73.98


def test_create_event_show_map_false_skips_geocode(map_env):
    created = _create_event(map_env["client"], show_map=False)

    assert created["show_map"] is False
    assert created["map_available"] is False
    assert map_env["geocoder"].calls == []


def test_door_response_includes_map_style_url_inside_event(map_env):
    created = _create_event(map_env["client"])
    data = _access(map_env["client"], created)

    assert data["map_style_url"] == MAP_STYLE_URL
    assert data["location_lat"] == 40.75
    assert data["location_lon"] == -73.98
    assert data["show_map"] is True


def test_door_response_omits_map_style_url_when_disabled(no_map_client):
    created = _create_event(no_map_client)
    data = _access(no_map_client, created)

    assert "map_style_url" not in data


def test_toggle_route_rejects_non_organizer_key(map_env):
    created = _create_event(map_env["client"])
    # An access key grants event content, but only the organizer key may
    # change the map switch.
    access = map_env["lifecycle"].generate_access_key(created["organizer_key"], created["event_id"])

    response = map_env["client"].post(
        f"/api/events/{created['event_id']}/map",
        json={"organizer_key": access["access_key"], "show_map": False},
    )

    assert response.status_code == 400
    assert map_env["db"].get_event(created["event_id"])["show_map"] is True


def test_toggle_route_off_then_on(map_env):
    created = _create_event(map_env["client"])
    calls_after_create = len(map_env["geocoder"].calls)

    off = map_env["client"].post(
        f"/api/events/{created['event_id']}/map",
        json={"organizer_key": created["organizer_key"], "show_map": False},
    )
    assert off.status_code == 200
    assert off.json() == {"show_map": False, "map_available": False}

    on = map_env["client"].post(
        f"/api/events/{created['event_id']}/map",
        json={"organizer_key": created["organizer_key"], "show_map": True},
    )
    assert on.status_code == 200
    assert on.json() == {"show_map": True, "map_available": True}
    assert len(map_env["geocoder"].calls) == calls_after_create


def test_toggle_route_on_geocodes_missing_coordinates(map_env):
    created = _create_event(map_env["client"], show_map=False)
    assert map_env["geocoder"].calls == []

    response = map_env["client"].post(
        f"/api/events/{created['event_id']}/map",
        json={"organizer_key": created["organizer_key"], "show_map": True},
    )

    assert response.status_code == 200
    assert response.json() == {"show_map": True, "map_available": True}
    assert map_env["geocoder"].calls == ["Main St"]
    event = map_env["db"].get_event(created["event_id"])
    assert event["location_lat"] == 40.75


def test_toggle_route_on_without_location_returns_400(map_env):
    created = _create_event(map_env["client"], location_data=None)

    response = map_env["client"].post(
        f"/api/events/{created['event_id']}/map",
        json={"organizer_key": created["organizer_key"], "show_map": True},
    )

    assert response.status_code == 400


def test_referrer_policy_header(map_env):
    response = map_env["client"].get("/health")

    assert response.headers["referrer-policy"] == "no-referrer"


def test_rsvp_public_view_excludes_map_fields(map_env):
    created = _create_event(map_env["client"])

    response = map_env["client"].get(f"/api/events/{created['event_id']}/rsvp/view")

    assert response.status_code == 200
    event = response.json()["event"]
    assert "location_lat" not in event
    assert "location_lon" not in event
    assert "show_map" not in event
    assert "map_style_url" not in event
