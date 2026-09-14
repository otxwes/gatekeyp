# Copyright (c) 2026 gatekeyp contributors

"""Tests for the RSVP funnel: service, routes, gateway gate and wipe behavior."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.api.gateway import Gateway
from src.api.server import create_app
from src.core.content_manager import ContentManager
from src.core.event_lifecycle import EventLifecycleManager
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler
from src.rsvp.service import (
    MAX_DISPLAY_NAME_LENGTH,
    RsvpGoneError,
    RsvpNotFoundError,
    RsvpRateLimiter,
    RsvpService,
    RsvpValidationError,
)

TEST_MASTER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

os.environ.setdefault("GATEKEYP_MASTER_KEY", TEST_MASTER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)


class _FakeClock:
    """Advanceable clock standing in for datetime.now(UTC)."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def timestamp(self) -> float:
        """The current fake time as a POSIX timestamp."""
        return self.now.timestamp()

    def advance(self, **kwargs: object) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    database = DatabaseHandler(db_path=":memory:", master_key=TEST_MASTER_KEY)
    yield database
    database.close()


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
def rsvp(db, key_manager, lifecycle, clock):
    """Create an RsvpService wired to the fake clock."""
    return RsvpService(db=db, key_manager=key_manager, lifecycle=lifecycle, clock=clock)


def _make_event(lifecycle: EventLifecycleManager, title: str = "Launch") -> dict:
    """Create a standard event and return its metadata (master_key included)."""
    return lifecycle.create_event(title, "A test event", "org_1")


def _key_hash(rsvp_service: RsvpService, raw_access_key: str) -> str:
    """Hash a `local:` access key the way storage does."""
    return rsvp_service.key_manager.hash_key(raw_access_key.removeprefix("local:"))


class TestSubmitRsvp:
    """Attendee submissions pre-mint grant-free keys, shown exactly once."""

    def test_pending_by_default_with_pre_minted_key(self, rsvp, lifecycle):
        """Default gate: pending status, key returned once, only HMAC stored."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada Lovelace", contact="ada@example.com")

        assert result["status"] == "pending"
        assert result["access_key"].startswith("local:")
        row = rsvp.db.get_rsvp(result["rsvp_id"])
        assert row["status"] == "pending"
        assert row["key_hash"] == _key_hash(rsvp, result["access_key"])
        assert result["access_key"] not in str(row)

    def test_pending_key_has_no_grants(self, rsvp, lifecycle):
        """A pending key unlocks nothing — not even the event row."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        grants = rsvp.db.get_content_ids_for_key(_key_hash(rsvp, result["access_key"]))
        assert grants == []

    def test_name_is_required(self, rsvp, lifecycle):
        """Whitespace-only names are rejected."""
        created = _make_event(lifecycle)
        with pytest.raises(RsvpValidationError, match="name"):
            rsvp.submit_rsvp(created["event_id"], "   ")

    def test_name_length_is_capped(self, rsvp, lifecycle):
        """Names beyond the display cap are rejected."""
        created = _make_event(lifecycle)
        with pytest.raises(RsvpValidationError, match="too long"):
            rsvp.submit_rsvp(created["event_id"], "A" * (MAX_DISPLAY_NAME_LENGTH + 1))

    def test_contact_length_is_capped(self, rsvp, lifecycle):
        """Contacts beyond the contact cap are rejected."""
        created = _make_event(lifecycle)
        with pytest.raises(RsvpValidationError, match="too long"):
            rsvp.submit_rsvp(created["event_id"], "Ada", contact="x" * 257)

    def test_non_string_name_is_rejected(self, rsvp, lifecycle):
        """JSON junk (numbers, objects) fails validation instead of crashing."""
        created = _make_event(lifecycle)
        with pytest.raises(RsvpValidationError):
            rsvp.submit_rsvp(created["event_id"], 12345)

    def test_contact_is_encrypted_at_rest(self, rsvp, lifecycle):
        """The contact column never holds the plaintext email."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada", contact="ada@example.com")
        rsvp.db.cursor.execute("SELECT contact FROM rsvps WHERE rsvp_id = ?", (result["rsvp_id"],))
        stored = rsvp.db.cursor.fetchone()[0]
        assert "ada@example.com" not in stored
        assert rsvp.db.get_rsvp(result["rsvp_id"])["contact"] == "ada@example.com"

    def test_unknown_event_is_not_found(self, rsvp):
        """RSVPs to unknown events fail with a not-found error."""
        with pytest.raises(RsvpNotFoundError):
            rsvp.submit_rsvp("event_nope", "Ada")

    def test_ended_event_is_gone(self, rsvp, lifecycle):
        """Wiped events raise the gone error (tombstone only)."""
        created = _make_event(lifecycle)
        rsvp.db.wipe_event(created["event_id"])
        with pytest.raises(RsvpGoneError):
            rsvp.submit_rsvp(created["event_id"], "Ada")

    def test_passphrase_gate_fails_closed(self, rsvp, lifecycle):
        """With the gate on, missing or wrong passphrases never mint access."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], passphrase="pw")
        with pytest.raises(RsvpValidationError, match="passphrase"):
            rsvp.submit_rsvp(created["event_id"], "Ada")
        with pytest.raises(RsvpValidationError, match="not correct"):
            rsvp.submit_rsvp(created["event_id"], "Ada", passphrase="wrong")
        ok = rsvp.submit_rsvp(created["event_id"], "Ada", passphrase="pw")
        assert ok["status"] == "pending"


class TestAutoApprove:
    """The dial auto-approves the first N submissions, then goes manual."""

    def test_first_n_approved_then_pending(self, rsvp, lifecycle):
        """Dial of 1: the first submission is approved, later ones pending."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], auto_approve=1)
        first = rsvp.submit_rsvp(created["event_id"], "First")
        second = rsvp.submit_rsvp(created["event_id"], "Second")
        assert first["status"] == "approved"
        assert second["status"] == "pending"

    def test_auto_approved_key_is_granted(self, rsvp, lifecycle):
        """An auto-approved RSVP's key is wired to the event and its content."""
        created = _make_event(lifecycle)
        lifecycle.add_content_block(created["master_key"], created["event_id"], "location", "x")
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], auto_approve=2)
        first = rsvp.submit_rsvp(created["event_id"], "First")
        grants = rsvp.db.get_content_ids_for_key(_key_hash(rsvp, first["access_key"]))
        granted = {g["content_id"] for g in grants}
        assert created["event_id"] in granted
        block_id = rsvp.db.list_content_blocks_for_event(created["event_id"])[0]["id"]
        assert block_id in granted


class TestDecide:
    """Organizer decisions stamp the row and wire (or cut) the key."""

    def test_approve_grants_event_and_content(self, rsvp, lifecycle):
        """Approve stamps the row and grants the key to event and blocks."""
        created = _make_event(lifecycle)
        block = lifecycle.add_content_block(
            created["master_key"], created["event_id"], "location", "x"
        )
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "approve")

        row = rsvp.db.get_rsvp(result["rsvp_id"])
        assert row["status"] == "approved"
        assert row["decided_at"] is not None
        grants = {g["content_id"] for g in rsvp.db.get_content_ids_for_key(row["key_hash"])}
        assert created["event_id"] in grants
        assert block["id"] in grants

    def test_approve_is_idempotent(self, rsvp, lifecycle):
        """Approving an approved RSVP changes nothing (links are ignored)."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "approve")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "approve")
        assert rsvp.db.get_rsvp(result["rsvp_id"])["status"] == "approved"

    def test_deny_revokes_key(self, rsvp, lifecycle):
        """Deny stamps the row and voids the pre-minted key."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "deny")

        row = rsvp.db.get_rsvp(result["rsvp_id"])
        assert row["status"] == "denied"
        assert row["decided_at"] is not None
        validation = rsvp.key_manager.validate_key(result["access_key"])
        assert validation["status"] == "invalid"

    def test_approve_after_deny_is_rejected(self, rsvp, lifecycle):
        """A denied RSVP cannot be revived; a new submission mints a new key."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "deny")
        with pytest.raises(RsvpValidationError, match="denied"):
            rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "approve")

    def test_unknown_rsvp_is_not_found(self, rsvp, lifecycle):
        """Deciding an RSVP that does not exist (or belongs elsewhere) is 404."""
        created = _make_event(lifecycle)
        with pytest.raises(RsvpNotFoundError):
            rsvp.decide(created["master_key"], created["event_id"], "rsvp_nope", "approve")

    def test_rsvp_from_another_event_is_not_found(self, rsvp, lifecycle):
        """An RSVP id for event A cannot be decided through event B's gate."""
        first = _make_event(lifecycle, "First")
        second = _make_event(lifecycle, "Second")
        result = rsvp.submit_rsvp(first["event_id"], "Ada")
        with pytest.raises(RsvpNotFoundError):
            rsvp.decide(second["master_key"], second["event_id"], result["rsvp_id"], "approve")

    def test_bad_decision_value_is_rejected(self, rsvp, lifecycle):
        """Anything but approve/deny fails validation."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        with pytest.raises(RsvpValidationError, match="approve"):
            rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "maybe")

    def test_unauthorized_master_key_is_rejected(self, rsvp, lifecycle):
        """A master key for another event cannot decide this event's RSVPs."""
        created = _make_event(lifecycle)
        other = _make_event(lifecycle, "Other")
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        with pytest.raises(RsvpValidationError, match="grant access"):
            rsvp.decide(other["master_key"], created["event_id"], result["rsvp_id"], "approve")


class TestSettings:
    """The organizer gate: passphrase hash + auto-approve dial."""

    def test_defaults_are_off(self, rsvp, lifecycle):
        """A fresh event requires no passphrase and approves nothing."""
        created = _make_event(lifecycle)
        settings = rsvp.get_rsvp_settings(created["master_key"], created["event_id"])
        assert settings == {"passphrase_required": False, "auto_approve": None}

    def test_passphrase_is_stored_hashed(self, rsvp, lifecycle):
        """Setting a passphrase stores a hash that differs from the secret."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], passphrase="pw")
        raw = rsvp.db.cursor.execute(
            "SELECT rsvp_passphrase_hash FROM events WHERE event_id = ?",
            (created["event_id"],),
        ).fetchone()[0]
        assert raw != "pw"
        settings = rsvp.get_rsvp_settings(created["master_key"], created["event_id"])
        assert settings["passphrase_required"] is True

    def test_passphrase_can_be_cleared(self, rsvp, lifecycle):
        """An empty passphrase clears the gate."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], passphrase="pw")
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], passphrase="")
        settings = rsvp.get_rsvp_settings(created["master_key"], created["event_id"])
        assert settings["passphrase_required"] is False

    def test_auto_approve_roundtrip(self, rsvp, lifecycle):
        """Integer dials are stored and read back."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], auto_approve=5)
        settings = rsvp.get_rsvp_settings(created["master_key"], created["event_id"])
        assert settings["auto_approve"] == 5

    def test_auto_approve_bounds(self, rsvp, lifecycle):
        """Dials outside [0, 100000] and booleans are rejected."""
        created = _make_event(lifecycle)
        for bad in (-1, 100001, True):
            with pytest.raises(RsvpValidationError):
                rsvp.update_rsvp_settings(
                    created["master_key"], created["event_id"], auto_approve=bad
                )

    def test_unauthorized_master_key_is_rejected(self, rsvp, lifecycle):
        """Only a key granting access to the event can read its settings."""
        created = _make_event(lifecycle)
        other = _make_event(lifecycle, "Other")
        with pytest.raises(RsvpValidationError, match="grant access"):
            rsvp.get_rsvp_settings(other["master_key"], created["event_id"])


class TestWipe:
    """wipe_event purges RSVP rows and voids every pre-minted key."""

    def test_wipe_purges_rsvps_and_keys(self, rsvp, lifecycle):
        """RSVP rows vanish and their keys stop validating."""
        created = _make_event(lifecycle)
        first = rsvp.submit_rsvp(created["event_id"], "Ada")
        second = rsvp.submit_rsvp(created["event_id"], "Grace")

        counts = rsvp.db.wipe_event(created["event_id"])
        assert counts["rsvps"] == 2
        assert rsvp.db.get_rsvp(first["rsvp_id"]) is None
        assert rsvp.db.get_rsvp(second["rsvp_id"]) is None
        for result in (first, second):
            validation = rsvp.key_manager.validate_key(result["access_key"])
            assert validation["status"] == "invalid"

    def test_wiped_event_answers_gone(self, rsvp, lifecycle):
        """The public view of a wiped event reports the ended state."""
        created = _make_event(lifecycle)
        rsvp.db.wipe_event(created["event_id"])
        view = rsvp.get_public_view(created["event_id"])
        assert view["status"] == "ended"


class TestPublicView:
    """The unauthenticated status endpoint leaks only safe fields."""

    def test_live_event_shape(self, rsvp, lifecycle):
        """Live events expose a nested event summary and the gate flag."""
        created = _make_event(lifecycle)
        view = rsvp.get_public_view(created["event_id"])
        assert view["status"] == "live"
        assert view["event"] == {
            "id": created["event_id"],
            "title": "Launch",
            "description": "A test event",
        }
        assert view["passphrase_required"] is False

    def test_passphrase_required_flag(self, rsvp, lifecycle):
        """Turning the passphrase gate on is visible to attendees."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], passphrase="pw")
        view = rsvp.get_public_view(created["event_id"])
        assert view["passphrase_required"] is True

    def test_unknown_event_is_not_found(self, rsvp):
        """Unknown ids raise the not-found error."""
        with pytest.raises(RsvpNotFoundError):
            rsvp.get_public_view("event_nope")


class TestRsvpRateLimiter:
    """5 submissions per 600 s per client, with an injectable clock."""

    def test_allows_five_then_blocks(self):
        """The fixed window admits exactly max_requests hits."""
        limiter = RsvpRateLimiter()
        for _ in range(5):
            assert limiter.allow("c1")
        assert not limiter.allow("c1")

    def test_clients_are_isolated(self):
        """One client burning the window does not affect another."""
        limiter = RsvpRateLimiter()
        for _ in range(5):
            limiter.allow("c1")
        assert limiter.allow("c2")

    def test_window_rolls_over(self, clock):
        """After the window elapses the client is allowed again."""
        limiter = RsvpRateLimiter(clock=clock.timestamp)
        for _ in range(5):
            assert limiter.allow("c1")
        assert not limiter.allow("c1")
        clock.advance(seconds=601)
        assert limiter.allow("c1")


class TestGatewayGate:
    """process_request answers 'pending' for pre-minted RSVP keys."""

    @pytest.fixture
    def gateway(self, db, key_manager):
        """A bare gateway over the shared (fake) stack."""
        return Gateway(db=db, key_manager=key_manager)

    def test_pending_key_is_not_yet_useful(self, gateway, rsvp, lifecycle):
        """A pending RSVP key gets the approval message, never content."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        response = gateway.process_request(
            {"key": result["access_key"], "content_id": created["event_id"]}
        )
        assert response["status"] == "pending"
        assert "awaiting organizer approval" in response["message"]

    def test_approved_key_reads_event_content(self, gateway, rsvp, lifecycle):
        """After approval the same pre-minted key opens the door."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "approve")
        response = gateway.process_request(
            {"key": result["access_key"], "content_id": created["event_id"]}
        )
        assert response["status"] == "success"
        assert response["data"]["id"] == created["event_id"]

    def test_denied_key_is_just_invalid(self, gateway, rsvp, lifecycle):
        """A denied RSVP's revoked key is rejected like any other dead key."""
        created = _make_event(lifecycle)
        result = rsvp.submit_rsvp(created["event_id"], "Ada")
        rsvp.decide(created["master_key"], created["event_id"], result["rsvp_id"], "deny")
        response = gateway.process_request(
            {"key": result["access_key"], "content_id": created["event_id"]}
        )
        assert response["status"] == "error"
        assert response["message"] == "Invalid key"

    def test_regular_keys_are_unaffected(self, gateway, lifecycle):
        """The gate changes nothing for keys without RSVP bookkeeping."""
        created = _make_event(lifecycle)
        response = gateway.process_request(
            {"key": created["master_key"], "content_id": created["event_id"]}
        )
        assert response["status"] == "success"


@pytest.fixture
def client(db, key_manager, content_manager, lifecycle):
    """TestClient for the full profile backed by an in-memory database."""
    app = create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        profile="full",
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def lite_client(db, key_manager, content_manager, lifecycle):
    """TestClient for the lite profile — RSVP routes must be mounted there too."""
    app = create_app(
        db=db,
        key_manager=key_manager,
        content_manager=content_manager,
        lifecycle=lifecycle,
        profile="lite",
    )
    with TestClient(app) as test_client:
        yield test_client


class TestAppWiring:
    """Both profiles expose the RSVP funnel endpoints."""

    _EXPECTED_PATHS = frozenset(
        {
            "/api/events/{event_id}/rsvp",
            "/api/events/{event_id}/rsvp/view",
            "/api/events/{event_id}/rsvp/decide",
            "/api/events/{event_id}/rsvp/settings",
            "/api/events/{event_id}/rsvp/list",
        }
    )

    def _rsvp_paths(self, app) -> set[str]:
        """Collect registered paths from the OpenAPI schema (covers routers)."""
        return set(app.openapi()["paths"])

    def test_full_profile_mounts_rsvp_routes(self, client):
        """The full profile registers every RSVP route."""
        assert self._rsvp_paths(client.app) >= self._EXPECTED_PATHS

    def test_lite_profile_mounts_rsvp_routes(self, lite_client):
        """The lite profile registers every RSVP route."""
        assert self._rsvp_paths(lite_client.app) >= self._EXPECTED_PATHS


class TestRoutes:
    """HTTP behavior of the RSVP funnel endpoints."""

    def test_submit_returns_201_with_pending_status(self, client, lifecycle):
        """A fresh submission is 201/pending and carries the one-time key."""
        created = _make_event(lifecycle)
        response = client.post(
            f"/api/events/{created['event_id']}/rsvp",
            json={"display_name": "Ada Lovelace", "contact": "ada@example.com"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["access_key"].startswith("local:")
        assert body["display_name"] == "Ada Lovelace"

    def test_submit_on_lite_profile_is_mounted(self, lite_client, lifecycle):
        """The lite door funnel also accepts RSVP submissions."""
        created = _make_event(lifecycle)
        response = lite_client.post(
            f"/api/events/{created['event_id']}/rsvp",
            json={"display_name": "Ada"},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "pending"

    def test_honeypot_acknowledges_without_minting(self, client, lifecycle, db):
        """Bots that fill the hidden field get a canned reply and nothing else."""
        created = _make_event(lifecycle)
        response = client.post(
            f"/api/events/{created['event_id']}/rsvp",
            json={"display_name": "Bot", "website": "http://spam.example"},
        )
        assert response.status_code == 201
        assert response.json()["rsvp_id"] is None
        assert db.list_rsvps(created["event_id"]) == []
        db.cursor.execute("SELECT COUNT(*) FROM keys WHERE rsvp_id IS NOT NULL")
        assert db.cursor.fetchone()[0] == 0

    def test_submit_rate_limit_429_with_retry_after(self, client, lifecycle):
        """The sixth submission from one client is throttled with Retry-After."""
        created = _make_event(lifecycle)
        url = f"/api/events/{created['event_id']}/rsvp"
        for _ in range(5):
            assert client.post(url, json={"display_name": "Ada"}).status_code == 201
        throttled = client.post(url, json={"display_name": "Ada"})
        assert throttled.status_code == 429
        assert throttled.headers["retry-after"] == "600"

    def test_submit_requires_passphrase_when_gated(self, client, lifecycle):
        """400 with a clear message when the shared passphrase is missing."""
        created = _make_event(lifecycle)
        client.post(
            f"/api/events/{created['event_id']}/rsvp/settings",
            json={"master_key": created["master_key"], "passphrase": "pw"},
        )
        response = client.post(
            f"/api/events/{created['event_id']}/rsvp", json={"display_name": "Ada"}
        )
        assert response.status_code == 400
        assert "passphrase" in response.json()["detail"]

    def test_view_endpoint_minimal_and_no_store(self, client, lifecycle):
        """The attendee page data is live JSON with no-store caching."""
        created = _make_event(lifecycle)
        response = client.get(f"/api/events/{created['event_id']}/rsvp/view")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert body["status"] == "live"
        assert body["event"]["title"] == "Launch"
        assert body["passphrase_required"] is False

    def test_view_unknown_event_is_404(self, client):
        """Unknown event ids are 404 on the public view."""
        response = client.get("/api/events/event_nope/rsvp/view")
        assert response.status_code == 404

    def test_view_after_wipe_reports_ended(self, client, lifecycle, db):
        """Wiped events still answer the view with the ended state."""
        created = _make_event(lifecycle)
        db.wipe_event(created["event_id"])
        response = client.get(f"/api/events/{created['event_id']}/rsvp/view")
        assert response.status_code == 200
        assert response.json()["status"] == "ended"

    def test_decide_approve_flow(self, client, lifecycle):
        """Organizer approval works end-to-end over HTTP."""
        created = _make_event(lifecycle)
        rsvp_id = client.post(
            f"/api/events/{created['event_id']}/rsvp", json={"display_name": "Ada"}
        ).json()["rsvp_id"]
        response = client.post(
            f"/api/events/{created['event_id']}/rsvp/decide",
            json={
                "master_key": created["master_key"],
                "rsvp_id": rsvp_id,
                "decision": "approve",
            },
        )
        assert response.status_code == 200
        assert response.json()["decision"] == "approve"

    def test_decide_errors_map_to_400_and_404(self, client, lifecycle):
        """Bad decisions are 400; unknown RSVPs and ids are 404."""
        created = _make_event(lifecycle)
        rsvp_id = client.post(
            f"/api/events/{created['event_id']}/rsvp", json={"display_name": "Ada"}
        ).json()["rsvp_id"]
        url = f"/api/events/{created['event_id']}/rsvp/decide"
        bad_decision = client.post(
            url,
            json={"master_key": created["master_key"], "rsvp_id": rsvp_id, "decision": "maybe"},
        )
        assert bad_decision.status_code == 400
        unknown = client.post(
            url,
            json={
                "master_key": created["master_key"],
                "rsvp_id": "rsvp_nope",
                "decision": "approve",
            },
        )
        assert unknown.status_code == 404
        unauthorized = client.post(
            url,
            json={"master_key": "local:not-a-real-key", "rsvp_id": rsvp_id, "decision": "approve"},
        )
        assert unauthorized.status_code == 400

    def test_settings_roundtrip_over_http(self, client, lifecycle):
        """The gate settings survive a POST then GET round-trip."""
        created = _make_event(lifecycle)
        update = client.post(
            f"/api/events/{created['event_id']}/rsvp/settings",
            json={"master_key": created["master_key"], "passphrase": "pw", "auto_approve": 3},
        )
        assert update.status_code == 200
        assert update.json() == {
            "event_id": created["event_id"],
            "passphrase_required": True,
            "auto_approve": 3,
        }
        read = client.get(
            f"/api/events/{created['event_id']}/rsvp/settings",
            params={"key": created["master_key"]},
        )
        assert read.status_code == 200
        assert read.json() == {"passphrase_required": True, "auto_approve": 3}

    def test_settings_reject_wrong_key(self, client, lifecycle):
        """Settings endpoints require a key granting access to the event."""
        created = _make_event(lifecycle)
        response = client.get(
            f"/api/events/{created['event_id']}/rsvp/settings",
            params={"key": "local:not-a-real-key"},
        )
        assert response.status_code == 400

    def test_list_returns_decrypted_contacts(self, client, lifecycle):
        """The organizer tab sees names and decrypted contacts only."""
        created = _make_event(lifecycle)
        client.post(
            f"/api/events/{created['event_id']}/rsvp",
            json={"display_name": "Ada", "contact": "ada@example.com"},
        )
        response = client.get(
            f"/api/events/{created['event_id']}/rsvp/list",
            params={"key": created["master_key"]},
        )
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["display_name"] == "Ada"
        assert rows[0]["contact"] == "ada@example.com"
        assert rows[0]["status"] == "pending"

    def test_auto_approve_flow_over_http(self, client, lifecycle):
        """The dial auto-approves the first submission through the API."""
        created = _make_event(lifecycle)
        client.post(
            f"/api/events/{created['event_id']}/rsvp/settings",
            json={"master_key": created["master_key"], "auto_approve": 1},
        )
        first = client.post(f"/api/events/{created['event_id']}/rsvp", json={"display_name": "A"})
        second = client.post(f"/api/events/{created['event_id']}/rsvp", json={"display_name": "B"})
        assert first.json()["status"] == "approved"
        assert second.json()["status"] == "pending"


class TestPendingQueueCap:
    """The pending cap bounds attacker-minted key growth; denial frees slots."""

    def test_pending_cap_rejects_when_full(self, rsvp, lifecycle, monkeypatch):
        """Submissions beyond the per-event pending cap are rejected."""
        created = _make_event(lifecycle)
        monkeypatch.setattr("src.rsvp.service.MAX_PENDING_RSVP_PER_EVENT", 2)
        rsvp.submit_rsvp(created["event_id"], "One")
        rsvp.submit_rsvp(created["event_id"], "Two")
        with pytest.raises(RsvpValidationError, match="queue is full"):
            rsvp.submit_rsvp(created["event_id"], "Three")

    def test_denial_frees_a_pending_slot(self, rsvp, lifecycle, monkeypatch):
        """Denying a pending RSVP drops the queue count, admitting another."""
        created = _make_event(lifecycle)
        monkeypatch.setattr("src.rsvp.service.MAX_PENDING_RSVP_PER_EVENT", 1)
        first = rsvp.submit_rsvp(created["event_id"], "One")
        rsvp.decide(created["master_key"], created["event_id"], first["rsvp_id"], "deny")
        second = rsvp.submit_rsvp(created["event_id"], "Two")
        assert second["status"] == "pending"


class TestAutoApproveDialSemantics:
    """The dial keeps up to N currently-approved, not literally the first N."""

    def test_denied_approval_frees_the_dial_slot(self, rsvp, lifecycle):
        """dial=1: after denying the approved RSVP, the next one auto-approves."""
        created = _make_event(lifecycle)
        rsvp.update_rsvp_settings(created["master_key"], created["event_id"], auto_approve=1)
        first = rsvp.submit_rsvp(created["event_id"], "One")
        assert first["status"] == "approved"
        rsvp.decide(created["master_key"], created["event_id"], first["rsvp_id"], "deny")
        second = rsvp.submit_rsvp(created["event_id"], "Two")
        assert second["status"] == "approved"
