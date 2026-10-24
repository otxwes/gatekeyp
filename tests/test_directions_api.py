# Copyright (c) 2026 gatekeyp contributors

"""HTTP tests for POST /api/directions and the directions_enabled payload flag.

Privacy boundary under test: the attendee's start address must never appear
in logs, error bodies, or anywhere but the successful response's origin label.
"""

import datetime
import logging
import os
import sys
import zoneinfo

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
from src.core.transit import DEFAULT_REGIONS
from src.db.database_handler import DatabaseHandler
from src.ephemeral import EphemeralService

TEST_ORGANIZER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_ORGANIZER_KEY", TEST_ORGANIZER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)

VENUE_POINT = GeoPoint(40.75, -73.98)  # inside the NYC bbox
START_TEXT = "161 S 5th St, Brooklyn"

# Epoch ms: some evening in NYC's Eastern offset.
_DEPART_MS = 1797048002000  # 2026-12-13T06:00:02Z -> 01:00-05:00
_ARRIVE_MS = _DEPART_MS + 2100 * 1000

FAKE_PLAN = {
    "itineraries": [
        {
            "startTime": _DEPART_MS,
            "endTime": _ARRIVE_MS,
            "duration": 2100.0,
            "legs": [
                {
                    "mode": "WALK",
                    "duration": 240.0,
                    "distance": 300.0,
                    "from": {"name": "Origin", "lat": 40.71, "lon": -73.95},
                    "to": {"name": "Bedford Av", "lat": 40.71, "lon": -73.95},
                },
                {
                    "mode": "TRANSIT",
                    "duration": 1500.0,
                    "distance": 4000.0,
                    "from": {
                        "name": "Bedford Av",
                        "lat": 40.71,
                        "lon": -73.95,
                        "stop": {"name": "Bedford Av"},
                    },
                    "to": {
                        "name": "1 Av",
                        "lat": 40.72,
                        "lon": -73.98,
                        "stop": {"name": "1 Av"},
                    },
                    "route": {
                        "shortName": "L",
                        "longName": "14 St-Canarsie Local",
                        "color": "A7A9AC",
                        "agency": {"name": "MTA"},
                    },
                    "headsign": "Canarsie",
                    "intermediateStops": [{"name": "3 Av"}, {"name": "Union Sq"}],
                    "startTime": _DEPART_MS,
                    "endTime": _ARRIVE_MS,
                },
                {
                    "mode": "WALK",
                    "duration": 360.0,
                    "distance": 450.0,
                    "from": {"name": "1 Av", "lat": 40.72, "lon": -73.98},
                    "to": {"name": "Venue", "lat": 40.75, "lon": -73.98},
                },
            ],
        }
    ]
}


class FakeOtp:
    """Records plan calls; returns a canned fixture plan."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.plan_response: dict | None = FAKE_PLAN

    def plan(self, region, origin, destination, *, depart_at=None):
        self.calls.append((region, origin, destination, depart_at))
        return self.plan_response


class FakeDirectionsGeocoder:
    """Geocodes the start to a fixed point, recording kwargs (never logs)."""

    def __init__(self, point: GeoPoint | None = None) -> None:
        self.point = point
        self.calls: list[tuple] = []

    def geocode(self, address, *, viewbox=None, use_cache=True):
        self.calls.append((address, viewbox, use_cache))
        return self.point


def _build_env(otp):
    db = DatabaseHandler(db_path=":memory:", organizer_key=TEST_ORGANIZER_KEY)
    key_manager = KeyManager(db=db, hmac_secret=TEST_HMAC_SECRET)
    content_manager = ContentManager(db=db, key_manager=key_manager)
    geocoder = FakeDirectionsGeocoder(VENUE_POINT)
    lifecycle = EventLifecycleManager(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        geocoder=geocoder,
        map_style_url="https://example.test/style.json",
    )
    gateway = Gateway(
        db=db,
        key_manager=key_manager,
        rate_limiter=RateLimiter(),
        map_style_url="https://example.test/style.json",
        transit_regions=DEFAULT_REGIONS,
        directions_enabled=otp is not None,
    )
    app = create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        gateway=gateway,
        otp=otp,
        transit_regions=DEFAULT_REGIONS,
        geocoder=geocoder,
    )
    ephemeral = EphemeralService(
        db=db,
        lifecycle=lifecycle,
        content_manager=content_manager,
        geocoder=geocoder,
        map_style_url="https://example.test/style.json",
        transit_regions=DEFAULT_REGIONS,
        directions_enabled=otp is not None,
    )
    return TestClient(app), db, lifecycle, geocoder, ephemeral


def _env_dict(client, db, lifecycle, geocoder, otp, ephemeral):
    return {
        "client": client,
        "db": db,
        "lifecycle": lifecycle,
        "geocoder": geocoder,
        "otp": otp,
        "ephemeral": ephemeral,
    }


@pytest.fixture
def directions_env(monkeypatch):
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", "")
    monkeypatch.setenv("GATEKEYP_OTP_URL", "")
    otp = FakeOtp()
    client, db, lifecycle, geocoder, ephemeral = _build_env(otp)
    with client:
        yield _env_dict(client, db, lifecycle, geocoder, otp, ephemeral)
    db.close()


@pytest.fixture
def no_otp_env(monkeypatch):
    monkeypatch.setenv("GATEKEYP_GEOCODER_URL", "")
    monkeypatch.setenv("GATEKEYP_OTP_URL", "")
    client, db, lifecycle, geocoder, ephemeral = _build_env(None)
    with client:
        yield _env_dict(client, db, lifecycle, geocoder, None, ephemeral)
    db.close()


def _create_event(env, client: TestClient | None = None, **overrides: object):
    client = client or env["client"]
    body = {
        "title": "Directions Event",
        "description": "A test event",
        "organizer_id": "@organizer:test",
        "location_data": "1 Av, Brooklyn",
    }
    body.update(overrides)
    response = client.post("/api/events", json=body)
    assert response.status_code == 200
    return response.json()


def _directions(client, event_id, key=None, start=START_TEXT):
    payload = {"event_id": event_id, "start": start}
    if key is not None:
        payload["key"] = key
    return client.post("/api/directions", json=payload)


def _access_key(env, created):
    """Mint an attendee access key that grants the event."""
    generated = env["lifecycle"].generate_access_key(created["organizer_key"], created["event_id"])
    return generated["access_key"]


def test_directions_requires_key_for_standard_event(directions_env):
    created = _create_event(directions_env)
    response = _directions(directions_env["client"], created["event_id"])
    assert response.status_code == 403


def test_directions_accepts_valid_access_key(directions_env):
    created = _create_event(directions_env)
    key = _access_key(directions_env, created)
    response = _directions(directions_env["client"], created["event_id"], key=key)
    assert response.status_code == 200


def test_directions_rejects_key_that_does_not_grant_event(directions_env):
    created = _create_event(directions_env)
    response = _directions(directions_env["client"], created["event_id"], key="local:nonsense")
    assert response.status_code == 403


def test_directions_lite_event_needs_no_key(directions_env):
    created = _create_event(directions_env)
    event_id = created["event_id"]
    organizer_key = created["organizer_key"]
    when = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).isoformat()
    directions_env["lifecycle"].add_content_block(
        organizer_key=organizer_key, event_id=event_id, content_type="schedule", payload=when
    )
    directions_env["db"].set_event_mode(event_id, "ephemeral", when)
    response = _directions(directions_env["client"], event_id)
    assert response.status_code == 200


def test_directions_without_venue_coordinates_422(directions_env):
    created = _create_event(directions_env, location_data=None)
    key = created["organizer_key"]
    response = _directions(directions_env["client"], created["event_id"], key=key)
    assert response.status_code == 422


def test_directions_unconfigured_region_422(directions_env):
    created = _create_event(directions_env)
    key = created["organizer_key"]
    # Put the venue outside every configured bbox.
    directions_env["db"].set_event_location_geo(created["event_id"], '{"lat": 10.0, "lon": 10.0}')
    response = _directions(directions_env["client"], created["event_id"], key=key)
    assert response.status_code == 422


def test_directions_unknown_or_ended_event_404(directions_env):
    client = directions_env["client"]
    response = _directions(client, "event_missing")
    assert response.status_code == 404

    created = _create_event(directions_env)
    directions_env["db"].wipe_event(created["event_id"])
    response = _directions(client, created["event_id"], key=created["organizer_key"])
    assert response.status_code == 404


def test_directions_geocode_failure_422_and_no_start_echo(directions_env):
    directions_env["geocoder"].point = None
    created = _create_event(directions_env)
    key = created["organizer_key"]
    response = _directions(directions_env["client"], created["event_id"], key=key)
    assert response.status_code == 422
    assert START_TEXT.lower() not in response.text.lower()


def test_directions_otp_failure_503(directions_env):
    directions_env["otp"].plan_response = None
    created = _create_event(directions_env)
    key = created["organizer_key"]
    response = _directions(directions_env["client"], created["event_id"], key=key)
    assert response.status_code == 503


def test_directions_returns_mapped_itinerary(directions_env):
    created = _create_event(directions_env)
    key = created["organizer_key"]
    response = _directions(directions_env["client"], created["event_id"], key=key)

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == created["event_id"]
    assert body["attribution"] == "Transit data © MTA"
    assert body["duration_minutes"] == 35
    assert body["depart_at"].endswith("-05:00")
    assert [leg["mode"] for leg in body["legs"]] == ["WALK", "TRANSIT", "WALK"]
    transit = body["legs"][1]
    assert transit["agency"] == "MTA"
    assert transit["line"] == "L"
    assert transit["headsign"] == "Canarsie"
    assert transit["stops"] == 2
    assert transit["depart"].endswith("-05:00")
    # Venue-local offset comes from the region timezone, not the host.
    offset = zoneinfo.ZoneInfo("America/New_York")
    _ = offset  # document intent; above endswith asserts the offset

    # The geocoder was used with no-cache and a soft viewbox of the region.
    start_calls = [c for c in directions_env["geocoder"].calls if c[0] == START_TEXT]
    assert start_calls, "start address should be geocoded"
    _, viewbox, use_cache = start_calls[0]
    assert use_cache is False
    assert viewbox == (40.4, 41.1, -74.3, -73.6)  # NYC bbox


def test_directions_rate_limited_429(directions_env):
    created = _create_event(directions_env)
    key = created["organizer_key"]
    client = directions_env["client"]
    for _ in range(10):
        client.post(
            "/api/directions",
            json={"event_id": created["event_id"], "start": START_TEXT, "key": key},
        )
    response = _directions(client, created["event_id"], key=key)
    assert response.status_code == 429
    assert "retry-after" in {name.lower() for name in response.headers}


def test_start_address_never_logged(directions_env, caplog):
    created = _create_event(directions_env)
    key = created["organizer_key"]
    client = directions_env["client"]
    with caplog.at_level(logging.DEBUG):
        # Successful and failing requests: neither may log the start text.
        ok = _directions(client, created["event_id"], key=key)
        assert ok.status_code == 200
        directions_env["geocoder"].point = None
        failed = _directions(client, created["event_id"], key=key)
        assert failed.status_code == 422
    assert START_TEXT.lower() not in caplog.text.lower()


def test_door_payload_includes_directions_enabled(directions_env):
    created = _create_event(directions_env)
    response = directions_env["client"].post(
        "/api/access",
        json={"key": created["organizer_key"], "content_id": created["event_id"]},
    )
    data = response.json()["data"]
    assert data["directions_enabled"] is True


def test_door_payload_disables_directions_for_map_off_event(directions_env):
    created = _create_event(directions_env, show_map=False)
    response = directions_env["client"].post(
        "/api/access",
        json={"key": created["organizer_key"], "content_id": created["event_id"]},
    )
    data = response.json()["data"]
    assert data["directions_enabled"] is False


def test_directions_disabled_without_otp(no_otp_env):
    created = _create_event(no_otp_env)
    client = no_otp_env["client"]
    response = client.post(
        "/api/access",
        json={"key": created["organizer_key"], "content_id": created["event_id"]},
    )
    data = response.json()["data"]
    assert data["directions_enabled"] is False

    directions = client.post(
        "/api/directions",
        json={"event_id": created["event_id"], "start": START_TEXT},
    )
    assert directions.status_code == 503


def test_lite_public_view_includes_directions_enabled(directions_env):
    created = _create_event(directions_env)
    event_id = created["event_id"]
    when = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).isoformat()
    directions_env["lifecycle"].add_content_block(
        organizer_key=created["organizer_key"],
        event_id=event_id,
        content_type="schedule",
        payload=when,
    )
    directions_env["db"].set_event_mode(event_id, "ephemeral", when)

    view = directions_env["ephemeral"].get_public_view(event_id)

    assert view["status"] == "live"
    assert view["event"]["directions_enabled"] is True
