# Copyright (c) 2026 gatekeyp contributors

"""Hard-cutoff tests for the "master" -> "organizer" terminology rename.

There are no legacy artifacts to support (everything is still a prototype),
so the old identifiers are fully removed. These tests pin that behavior:
any use of "master_key", GATEKEYP_MASTER_KEY, or legacy stored key types
must fail loudly instead of being silently accepted.
"""

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.db.database_handler import DatabaseHandler, MissingOrganizerKeyError

TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"
VALID_KEY = Fernet.generate_key().decode()


@pytest.fixture
def client():
    """TestClient with an in-memory database (same shape as test_api_server)."""
    from src.api.gateway import Gateway, RateLimiter
    from src.api.server import create_app
    from src.core.content_manager import ContentManager
    from src.core.event_lifecycle import EventLifecycleManager
    from src.core.key_manager import KeyManager

    db = DatabaseHandler(db_path=":memory:", organizer_key=VALID_KEY)
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
        yield test_client, lifecycle
    db.close()


class TestLegacyIdentifiersRejected:
    def test_post_rejects_master_key_field(self, client):
        """JSON bodies using the old "master_key" field no longer validate."""
        test_client, lifecycle = client
        created = lifecycle.create_event(
            title="Legacy", description="A legacy test event", organizer_id="@u:t"
        )
        organizer_key = created["organizer_key"]
        event_id = created["event_id"]

        response = test_client.post(
            f"/api/events/{event_id}/content",
            json={
                "master_key": organizer_key,
                "content_type": "text",
                "payload": "hello",
                "event_id": event_id,
            },
        )
        assert response.status_code == 422

    def test_get_rejects_master_key_query_param(self, client):
        """GET endpoints no longer accept the old master_key query param."""
        test_client, lifecycle = client
        created = lifecycle.create_event(
            title="Legacy GET", description="A legacy test event", organizer_id="@u:t"
        )
        organizer_key = created["organizer_key"]

        response = test_client.get(
            f"/api/events/{created['event_id']}",
            params={"master_key": organizer_key},
        )
        assert response.status_code == 422


class TestNewIdentifiersStillWork:
    def test_post_accepts_organizer_key_field(self, client):
        """JSON bodies using organizer_key still validate."""
        test_client, lifecycle = client
        created = lifecycle.create_event(
            title="New", description="A test event", organizer_id="@u:t"
        )
        organizer_key = created["organizer_key"]
        event_id = created["event_id"]

        response = test_client.post(
            f"/api/events/{event_id}/content",
            json={
                "organizer_key": organizer_key,
                "content_type": "text",
                "payload": "hello",
                "event_id": event_id,
            },
        )
        assert response.status_code == 200

    def test_get_accepts_organizer_key_query_param(self, client):
        """GET endpoints accept the organizer_key query param."""
        test_client, lifecycle = client
        created = lifecycle.create_event(
            title="New GET", description="A test event", organizer_id="@u:t"
        )
        organizer_key = created["organizer_key"]

        response = test_client.get(
            f"/api/events/{created['event_id']}",
            params={"organizer_key": organizer_key},
        )
        assert response.status_code == 200
        assert response.json()["event"]["title"] == "New GET"


def test_legacy_master_key_kwarg_rejected():
    """DatabaseHandler no longer accepts a master_key kwarg."""
    with pytest.raises(TypeError):
        DatabaseHandler(":memory:", master_key=VALID_KEY)


def test_legacy_env_var_ignored(monkeypatch):
    """GATEKEYP_MASTER_KEY alone no longer satisfies encryption-at-rest."""
    monkeypatch.delenv("GATEKEYP_ORGANIZER_KEY", raising=False)
    monkeypatch.setenv("GATEKEYP_MASTER_KEY", VALID_KEY)
    with pytest.raises(MissingOrganizerKeyError):
        DatabaseHandler(":memory:")
