# Copyright (c) 2026 gatekeyp contributors
"""Phase 3.6 E2E: the invite-card loop against the live FastAPI server.

Simulates the organizer + attendee flows end-to-end via TestClient: create
event -> generate access key -> embed the key into a card PNG (the stego_ref
mirror of the browser codec) -> decode it back -> unlock the event at the
door. Also asserts the new static files are served from web/ with no server
change.
"""

import os
import sys

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.gateway import Gateway, RateLimiter
from src.api.server import create_app
from src.core.content_manager import ContentManager
from src.core.event_lifecycle import EventLifecycleManager
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler
from tests import stego_ref

TEST_MASTER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_MASTER_KEY", TEST_MASTER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)


@pytest.fixture
def client():
    """Create a TestClient backed by an in-memory database."""
    db = DatabaseHandler(db_path=":memory:", master_key=TEST_MASTER_KEY)
    key_manager = KeyManager(db=db, hmac_secret=TEST_HMAC_SECRET)
    content_manager = ContentManager(db=db, key_manager=key_manager)
    lifecycle = EventLifecycleManager(
        db=db, key_manager=key_manager, content_manager=content_manager
    )
    gateway = Gateway(db=db, key_manager=key_manager, rate_limiter=RateLimiter())
    app = create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        gateway=gateway,
    )
    with TestClient(app) as test_client:
        yield test_client
    db.close()


def _card_carrier(width: int = 200, height: int = 260) -> bytes:
    """Deterministic small carrier (stand-in for the browser card art)."""
    rgba = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            v = 244 - int((x / width) * 36)
            if 40 <= x <= 50:
                v = int(v * 0.35)
            if y >= height - 40:
                v = int(v * 0.6)
            rgba[i] = rgba[i + 1] = rgba[i + 2] = v
            rgba[i + 3] = 255
    return stego_ref.write_png(width, height, bytes(rgba))


def _create_event(client, title: str, organizer: str) -> dict:
    response = client.post(
        "/api/events",
        json={
            "title": title,
            "description": "A description for E2E coverage.",
            "organizer_id": organizer,
            "location_data": "Somewhere",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_invite_card_loop_unlocks_event(client) -> None:
    # 1. Organizer creates an event.
    created = _create_event(client, "Garden Party", "@host")
    event_id = created["event_id"]
    master_key = created["master_key"]

    # 2. Organizer generates an access key for an attendee.
    key_resp = client.post(
        f"/api/events/{event_id}/access-keys",
        json={"master_key": master_key, "event_id": event_id, "days": 30, "owner_id": "@guest"},
    )
    assert key_resp.status_code == 200
    access_key = key_resp.json()["access_key"]

    # 3. The card is built (browser flow: invite_card.js draw -> stego.embed).
    payload = stego_ref.make_payload(event_id, access_key)
    card_png = stego_ref.embed(_card_carrier(), payload)

    # 4. Decode the card back (browser flow: stego.extract at the door).
    assert stego_ref.extract(card_png) == payload
    parsed = stego_ref.parse_payload(payload)
    assert parsed == (event_id, access_key)

    # 5. The attendee unlocks the event with the values read from the card.
    unlock = client.post("/api/access", json={"key": access_key, "content_id": event_id})
    assert unlock.status_code == 200
    assert unlock.json()["status"] == "success"
    assert unlock.json()["data"]["id"] == event_id

    # 6. The card's QR text carries the same credential.
    qr_text = stego_ref.make_qr_payload(event_id, access_key)
    assert stego_ref.parse_qr_payload(qr_text) == (event_id, access_key)


def test_revoked_card_key_no_longer_unlocks(client) -> None:
    # The gateway unlocks on key validity (a valid key + existing content is
    # answered with the event dict; per-event gating lives in ContentManager).
    # The property that must hold for cards is parity with revocation.
    created = _create_event(client, "Event A", "@a")
    event_id = created["event_id"]
    master_key = created["master_key"]
    key_resp = client.post(
        f"/api/events/{event_id}/access-keys",
        json={"master_key": master_key, "event_id": event_id, "days": 7, "owner_id": "@b"},
    )
    assert key_resp.status_code == 200
    access_key = key_resp.json()["access_key"]

    # The card still decodes to the (now about to be revoked) key...
    card_png = stego_ref.embed(_card_carrier(), stego_ref.make_payload(event_id, access_key))
    assert stego_ref.extract(card_png) == stego_ref.make_payload(event_id, access_key)

    # ...and it unlocks while valid.
    unlock = client.post("/api/access", json={"key": access_key, "content_id": event_id})
    assert unlock.status_code == 200
    assert unlock.json()["status"] == "success"

    # Revoke: the same card now fails at the door — no server-side change.
    revoke = client.post(
        f"/api/events/{event_id}/access-keys/revoke",
        json={"master_key": master_key, "event_id": event_id, "access_key": access_key},
    )
    assert revoke.status_code == 200
    unlock_again = client.post("/api/access", json={"key": access_key, "content_id": event_id})
    assert unlock_again.status_code == 200
    assert unlock_again.json()["status"] != "success"


def test_new_static_files_are_served_without_server_change(client) -> None:
    for path, needle in [
        ("/stego.js", "window.gkpStego"),
        ("/door_qr.js", "window.gkpDoorQr"),
        ("/invite_card.js", "window.gkpInviteCard"),
        ("/invite_card.js", "coverFit"),
        ("/invite_card.js", "containFit"),
        ("/invite_card.js", "backdropCrop"),
        ("/invite_card.js", "drawBlurBackdrop"),
        ("/vendor/qrcode-generator.js", "QR Code Generator"),
        ("/vendor/jsqr.js", "jsQR"),
        ("/vendor/jsqr-LICENSE.txt", "Apache License"),
        ("/index.html", "key-drop"),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert needle.encode() in response.content
