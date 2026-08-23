# Copyright (c) 2026 gatekeyp contributors

"""Tests for the FastAPI HTTP server (src.api.server).

Exercises the RESTful API surface end-to-end via FastAPI's TestClient,
covering the flows the web UI depends on (event lifecycle, content,
media, bulletins, comments) and the routes added for Phase 3.
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

# Generate a valid Fernet key for tests
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


@pytest.fixture
def created_event(client):
    """Create an event through the API and return the response body."""
    response = client.post(
        "/api/events",
        json={
            "title": "Open Mic Night",
            "description": "An informal evening of music, readings, and snacks.",
            "organizer_id": "@theo:nyc",
            "location_data": "Comfort Station — 40.75,-73.98",
        },
    )
    assert response.status_code == 200
    return response.json()


# ------------------------------------------------------------------
# Event Lifecycle
# ------------------------------------------------------------------


class TestEventApi:
    def test_create_event_returns_master_key(self, created_event):
        """POST /api/events creates an event with a master key."""
        assert created_event["event_id"].startswith("event_")
        assert created_event["title"] == "Open Mic Night"
        assert created_event["master_key"].startswith("local:")
        assert created_event["expires_at"]

    def test_get_event_details_with_master_key(self, client, created_event):
        """Organizers can read full details with the master key."""
        response = client.get(
            f"/api/events/{created_event['event_id']}",
            params={"master_key": created_event["master_key"]},
        )
        assert response.status_code == 200
        details = response.json()
        assert details["event"]["title"] == "Open Mic Night"
        assert details["content_blocks"] == []

    def test_get_event_details_rejects_bad_key(self, client, created_event):
        """An invalid key is rejected (fail-secure)."""
        response = client.get(
            f"/api/events/{created_event['event_id']}",
            params={"master_key": "local:invalid-key-0000000000000000"},
        )
        assert response.status_code == 400

    def test_add_content_then_read_block(self, client, created_event):
        """Content blocks can be added and read back."""
        event_id = created_event["event_id"]
        add = client.post(
            f"/api/events/{event_id}/content",
            json={
                "master_key": created_event["master_key"],
                "event_id": event_id,
                "content_type": "schedule",
                "payload": "Doors 7pm · sets 8pm",
            },
        )
        assert add.status_code == 200
        block_id = add.json()["id"]

        details = client.get(
            f"/api/events/{event_id}",
            params={"master_key": created_event["master_key"]},
        ).json()
        assert any(b["id"] == block_id for b in details["content_blocks"])

    def test_event_decommission(self, client, created_event):
        """Decommissioning revokes the master key."""
        event_id = created_event["event_id"]
        response = client.post(
            f"/api/events/{event_id}/decommission",
            json={"master_key": created_event["master_key"], "event_id": event_id},
        )
        assert response.status_code == 200
        assert response.json()["master_key_revoked"] is True

        # Master key no longer grants access after decommission
        after = client.get(
            f"/api/events/{event_id}",
            params={"master_key": created_event["master_key"]},
        )
        assert after.status_code == 400


# ------------------------------------------------------------------
# Access Keys + Participant Unlock
# ------------------------------------------------------------------


class TestAccessKeyApi:
    def test_generate_and_list_access_keys(self, client, created_event):
        """Organizers can generate and list access keys."""
        event_id = created_event["event_id"]
        generated = client.post(
            f"/api/events/{event_id}/access-keys",
            json={
                "master_key": created_event["master_key"],
                "event_id": event_id,
                "days": 14,
                "owner_id": "@sam:nyc",
            },
        )
        assert generated.status_code == 200
        access_key = generated.json()["access_key"]
        assert access_key.startswith("local:")

        listed = client.get(
            f"/api/events/{event_id}/access-keys",
            params={"master_key": created_event["master_key"]},
        )
        assert listed.status_code == 200
        assert any(k["owner_id"] == "@sam:nyc" for k in listed.json())

    def test_access_key_unlocks_event_details(self, client, created_event):
        """A generated access key can open the event (participant view)."""
        event_id = created_event["event_id"]
        generated = client.post(
            f"/api/events/{event_id}/access-keys",
            json={
                "master_key": created_event["master_key"],
                "event_id": event_id,
                "days": 7,
            },
        ).json()
        access_key = generated["access_key"]

        response = client.get(
            f"/api/events/{event_id}",
            params={"master_key": access_key},
        )
        assert response.status_code == 200
        assert response.json()["event"]["title"] == "Open Mic Night"

    def test_revoke_access_key(self, client, created_event):
        """Access keys can be revoked and no longer unlock content."""
        event_id = created_event["event_id"]
        generated = client.post(
            f"/api/events/{event_id}/access-keys",
            json={
                "master_key": created_event["master_key"],
                "event_id": event_id,
                "days": 30,
            },
        ).json()
        access_key = generated["access_key"]

        revoked = client.post(
            f"/api/events/{event_id}/access-keys/revoke",
            json={
                "master_key": created_event["master_key"],
                "event_id": event_id,
                "access_key": access_key,
            },
        )
        assert revoked.status_code == 200
        assert revoked.json()["revoked"] is True

        after = client.get(
            f"/api/events/{event_id}",
            params={"master_key": access_key},
        )
        assert after.status_code == 400


# ------------------------------------------------------------------
# Bulletins & Comments
# ------------------------------------------------------------------


class TestCommunicationBoard:
    def test_create_list_and_read_bulletin(self, client, created_event):
        """Bulletins can be created, listed, and read with a body."""
        event_id = created_event["event_id"]
        master_key = created_event["master_key"]

        created = client.post(
            f"/api/events/{event_id}/bulletins",
            json={
                "key": master_key,
                "event_id": event_id,
                "title": "Set list",
                "body": "1. Ruby — 20min\n2. The Usual — 25min",
                "author_id": "@theo:nyc",
            },
        )
        assert created.status_code == 200
        bulletin_id = created.json()["id"]

        listed = client.get(
            f"/api/events/{event_id}/bulletins",
            params={"key": master_key},
        )
        assert listed.status_code == 200
        assert any(b["id"] == bulletin_id for b in listed.json())

        single = client.get(
            f"/api/bulletins/{bulletin_id}",
            params={"key": master_key},
        )
        assert single.status_code == 200
        assert "Ruby" in single.json()["body"]

    def test_bulletin_read_requires_key(self, client, created_event):
        """The bulletin body is key-gated."""
        event_id = created_event["event_id"]
        created = client.post(
            f"/api/events/{event_id}/bulletins",
            json={
                "key": created_event["master_key"],
                "event_id": event_id,
                "title": "Secret board",
                "body": "Never read without a key",
                "author_id": "@theo:nyc",
            },
        ).json()

        denied = client.get(
            f"/api/bulletins/{created['id']}",
            params={"key": "local:wrong-key-0000000000000000"},
        )
        assert denied.status_code == 400

    def test_comments_thread_and_delete(self, client, created_event):
        """Comments can be posted, read, and deleted."""
        event_id = created_event["event_id"]
        master_key = created_event["master_key"]
        bulletin_id = client.post(
            f"/api/events/{event_id}/bulletins",
            json={
                "key": master_key,
                "event_id": event_id,
                "title": "Thread",
                "body": "Start here",
                "author_id": "@theo:nyc",
            },
        ).json()["id"]

        first = client.post(
            f"/api/bulletins/{bulletin_id}/comments",
            json={
                "key": master_key,
                "bulletin_id": bulletin_id,
                "author_id": "@sam:nyc",
                "body": "I'm in",
            },
        )
        assert first.status_code == 200
        comment_id = first.json()["id"]

        comments = client.get(
            f"/api/bulletins/{bulletin_id}/comments",
            params={"key": master_key},
        )
        assert comments.status_code == 200
        assert any(c["id"] == comment_id and c["body"] == "I'm in" for c in comments.json())

        deleted = client.delete(f"/api/comments/{comment_id}", params={"key": master_key})
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        remaining = client.get(
            f"/api/bulletins/{bulletin_id}/comments",
            params={"key": master_key},
        ).json()
        assert all(c["id"] != comment_id for c in remaining)

    def test_delete_bulletin(self, client, created_event):
        """A bulletin can be deleted with its comments."""
        event_id = created_event["event_id"]
        master_key = created_event["master_key"]
        bulletin_id = client.post(
            f"/api/events/{event_id}/bulletins",
            json={
                "key": master_key,
                "event_id": event_id,
                "title": "Temporary",
                "body": "To be removed",
                "author_id": "@theo:nyc",
            },
        ).json()["id"]

        deleted = client.delete(f"/api/bulletins/{bulletin_id}", params={"key": master_key})
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


# ------------------------------------------------------------------
# Media Assets
# ------------------------------------------------------------------


class TestMediaApi:
    def test_upload_list_and_delete_media(self, client, created_event):
        """Media can be uploaded, listed, and deleted with a key."""
        event_id = created_event["event_id"]
        master_key = created_event["master_key"]

        uploaded = client.post(
            f"/api/events/{event_id}/media",
            params={"key": master_key},
            files={"file": ("flyer.png", b"\x89PNG\r\n\x1a\nfake-image-bytes", "image/png")},
        )
        assert uploaded.status_code == 200
        asset_id = uploaded.json()["id"]
        assert uploaded.json()["mime_type"] == "image/png"

        listed = client.get(
            f"/api/events/{event_id}/media",
            params={"key": master_key},
        )
        assert listed.status_code == 200
        assert any(a["id"] == asset_id for a in listed.json())

        # Retrieving an asset returns its raw bytes with the right MIME type
        retrieved = client.get(f"/api/media/{asset_id}", params={"key": master_key})
        assert retrieved.status_code == 200
        assert retrieved.headers["content-type"] == "image/png"
        assert retrieved.content == b"\x89PNG\r\n\x1a\nfake-image-bytes"

        deleted = client.delete(f"/api/media/{asset_id}", params={"key": master_key})
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
