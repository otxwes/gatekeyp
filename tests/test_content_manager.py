# Copyright (c) 2026 Gatekeyp contributors

import base64
import os
import sys

import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet

from src.core.content_manager import (
    ContentAccessError,
    ContentManager,
    ContentValidationError,
)
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
def setup_event_and_key(db, key_manager):
    """Set up an event and a key that grants access to it."""
    # Create a key
    raw_key = "local:test-access-key-1234567890"
    # The local part is what gets hashed (after the "local:" prefix)
    local_key = raw_key.split(":", 1)[1]
    key_hash = key_manager.hash_key(local_key)
    db.add_key(hash_key=key_hash, key_type="access", owner_id="local")

    # Create an event
    event_id = "event_test_001"
    db.add_event(
        event_id=event_id,
        title="Test Event",
        description="A test event",
        organizer_id="local",
    )

    # Link the key to the event
    db.add_key_content_link(key_hash, event_id, "event")

    return {"raw_key": raw_key, "key_hash": key_hash, "event_id": event_id}


class TestMediaAssets:
    """Tests for media asset upload/retrieval."""

    def test_upload_and_retrieve_media(self, content_manager, setup_event_and_key):
        """Test uploading and retrieving a media asset."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        data = b"fake-image-binary-data"
        result = content_manager.upload_media(
            input_key=raw_key,
            event_id=event_id,
            filename="flyer.png",
            mime_type="image/png",
            data=data,
        )

        assert result["id"].startswith("asset_")
        assert result["event_id"] == event_id
        assert result["filename"] == "flyer.png"
        assert result["mime_type"] == "image/png"
        assert result["size_bytes"] == len(data)

        # Retrieve the asset
        asset = content_manager.get_media(raw_key, result["id"])
        assert asset["data"] == data
        assert asset["filename"] == "flyer.png"

    def test_media_encrypted_at_rest(self, db, content_manager, setup_event_and_key):
        """Test that media data is encrypted at rest in the database."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        data = b"secret-flyer-content"
        result = content_manager.upload_media(
            input_key=raw_key,
            event_id=event_id,
            filename="secret.pdf",
            mime_type="application/pdf",
            data=data,
        )

        # Check the raw database value is encrypted (not plaintext)
        db.cursor.execute("SELECT data FROM media_assets WHERE asset_id = ?", (result["id"],))
        stored = db.cursor.fetchone()[0]
        assert stored != data
        assert b"secret-flyer-content" not in stored

    def test_upload_media_invalid_mime_type(self, content_manager, setup_event_and_key):
        """Test that unsupported MIME types are rejected."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        with pytest.raises(ContentValidationError):
            content_manager.upload_media(
                input_key=raw_key,
                event_id=event_id,
                filename="malware.exe",
                mime_type="application/x-msdownload",
                data=b"bad",
            )

    def test_upload_media_oversized(self, content_manager, setup_event_and_key):
        """Test that oversized media is rejected."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        with pytest.raises(ContentValidationError):
            content_manager.upload_media(
                input_key=raw_key,
                event_id=event_id,
                filename="huge.bin",
                mime_type="application/pdf",
                data=b"x" * (10 * 1024 * 1024 + 1),
            )

    def test_upload_media_invalid_key(self, content_manager, setup_event_and_key):
        """Test that an invalid key cannot upload media."""
        event_id = setup_event_and_key["event_id"]

        with pytest.raises(ContentAccessError):
            content_manager.upload_media(
                input_key="local:wrong-key",
                event_id=event_id,
                filename="test.png",
                mime_type="image/png",
                data=b"data",
            )

    def test_get_media_access_denied(self, content_manager, setup_event_and_key):
        """Test that a key without access cannot retrieve media."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        # Upload media with the valid key
        result = content_manager.upload_media(
            input_key=raw_key,
            event_id=event_id,
            filename="flyer.png",
            mime_type="image/png",
            data=b"data",
        )

        # Try to retrieve with a different key
        with pytest.raises(ContentAccessError):
            content_manager.get_media("local:other-key", result["id"])

    def test_list_media(self, content_manager, setup_event_and_key):
        """Test listing media assets for an event."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        content_manager.upload_media(
            input_key=raw_key,
            event_id=event_id,
            filename="flyer1.png",
            mime_type="image/png",
            data=b"data1",
        )
        content_manager.upload_media(
            input_key=raw_key,
            event_id=event_id,
            filename="flyer2.png",
            mime_type="image/png",
            data=b"data2",
        )

        assets = content_manager.list_media(raw_key, event_id)
        assert len(assets) == 2
        assert all("data" not in a for a in assets)  # No binary data in listing

    def test_delete_media(self, content_manager, setup_event_and_key):
        """Test deleting a media asset."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        result = content_manager.upload_media(
            input_key=raw_key,
            event_id=event_id,
            filename="flyer.png",
            mime_type="image/png",
            data=b"data",
        )

        assert content_manager.delete_media(raw_key, result["id"]) is True
        with pytest.raises(ContentAccessError):
            content_manager.get_media(raw_key, result["id"])


class TestBulletins:
    """Tests for secure communication board bulletins."""

    def test_create_and_retrieve_bulletin(self, content_manager, setup_event_and_key):
        """Test creating and retrieving a bulletin."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        result = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Welcome",
            body="Welcome to the event!",
            author_id="@alice:local",
        )

        assert result["id"].startswith("bulletin_")
        assert result["title"] == "Welcome"
        assert result["author_id"] == "@alice:local"

        # Retrieve the bulletin
        bulletin = content_manager.get_bulletin(raw_key, result["id"])
        assert bulletin["body"] == "Welcome to the event!"
        assert bulletin["title"] == "Welcome"

    def test_bulletin_encrypted_at_rest(self, db, content_manager, setup_event_and_key):
        """Test that bulletin body is encrypted at rest."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        result = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Secret",
            body="This is a secret message",
            author_id="@alice:local",
        )

        # Check the raw database value is encrypted
        db.cursor.execute("SELECT body FROM bulletins WHERE bulletin_id = ?", (result["id"],))
        stored = db.cursor.fetchone()[0]
        assert "secret message" not in stored

    def test_create_bulletin_invalid_key(self, content_manager, setup_event_and_key):
        """Test that an invalid key cannot create a bulletin."""
        event_id = setup_event_and_key["event_id"]

        with pytest.raises(ContentAccessError):
            content_manager.create_bulletin(
                input_key="local:wrong-key",
                event_id=event_id,
                title="Test",
                body="Test body",
                author_id="@alice:local",
            )

    def test_create_bulletin_empty_title(self, content_manager, setup_event_and_key):
        """Test that an empty title is rejected."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        with pytest.raises(ContentValidationError):
            content_manager.create_bulletin(
                input_key=raw_key,
                event_id=event_id,
                title="",
                body="Test body",
                author_id="@alice:local",
            )

    def test_list_bulletins(self, content_manager, setup_event_and_key):
        """Test listing bulletins for an event."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="First",
            body="First body",
            author_id="@alice:local",
        )
        content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Second",
            body="Second body",
            author_id="@bob:local",
        )

        bulletins = content_manager.list_bulletins(raw_key, event_id)
        assert len(bulletins) == 2
        assert all("body" not in b for b in bulletins)  # No body in listing

    def test_update_bulletin(self, content_manager, setup_event_and_key):
        """Test updating a bulletin."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        result = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Original",
            body="Original body",
            author_id="@alice:local",
        )

        assert (
            content_manager.update_bulletin(
                raw_key, result["id"], title="Updated", body="Updated body"
            )
            is True
        )

        bulletin = content_manager.get_bulletin(raw_key, result["id"])
        assert bulletin["title"] == "Updated"
        assert bulletin["body"] == "Updated body"

    def test_delete_bulletin(self, content_manager, setup_event_and_key):
        """Test deleting a bulletin."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        result = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="To Delete",
            body="Delete me",
            author_id="@alice:local",
        )

        assert content_manager.delete_bulletin(raw_key, result["id"]) is True
        with pytest.raises(ContentAccessError):
            content_manager.get_bulletin(raw_key, result["id"])


class TestComments:
    """Tests for secure communication board comments."""

    def test_post_and_get_comments(self, content_manager, setup_event_and_key):
        """Test posting and retrieving comments."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        bulletin = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Discussion",
            body="Let's discuss",
            author_id="@alice:local",
        )

        comment = content_manager.post_comment(
            input_key=raw_key,
            bulletin_id=bulletin["id"],
            body="Great idea!",
            author_id="@bob:local",
        )

        assert comment["id"].startswith("comment_")
        assert comment["author_id"] == "@bob:local"

        comments = content_manager.get_comments(raw_key, bulletin["id"])
        assert len(comments) == 1
        assert comments[0]["body"] == "Great idea!"

    def test_comment_encrypted_at_rest(self, db, content_manager, setup_event_and_key):
        """Test that comment body is encrypted at rest."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        bulletin = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Discussion",
            body="Let's discuss",
            author_id="@alice:local",
        )

        comment = content_manager.post_comment(
            input_key=raw_key,
            bulletin_id=bulletin["id"],
            body="This is a private comment",
            author_id="@bob:local",
        )

        db.cursor.execute("SELECT body FROM comments WHERE comment_id = ?", (comment["id"],))
        stored = db.cursor.fetchone()[0]
        assert "private comment" not in stored

    def test_threaded_comments(self, content_manager, setup_event_and_key):
        """Test threaded (nested) comments."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        bulletin = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Thread",
            body="Thread body",
            author_id="@alice:local",
        )

        parent = content_manager.post_comment(
            input_key=raw_key,
            bulletin_id=bulletin["id"],
            body="Parent comment",
            author_id="@alice:local",
        )

        content_manager.post_comment(
            input_key=raw_key,
            bulletin_id=bulletin["id"],
            body="Reply to parent",
            author_id="@bob:local",
            parent_comment_id=parent["id"],
        )

        comments = content_manager.get_comments(raw_key, bulletin["id"])
        assert len(comments) == 2
        assert comments[0]["parent_comment_id"] is None
        assert comments[1]["parent_comment_id"] == parent["id"]

    def test_post_comment_invalid_key(self, content_manager, setup_event_and_key):
        """Test that an invalid key cannot post a comment."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        bulletin = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Discussion",
            body="Let's discuss",
            author_id="@alice:local",
        )

        with pytest.raises(ContentAccessError):
            content_manager.post_comment(
                input_key="local:wrong-key",
                bulletin_id=bulletin["id"],
                body="Should fail",
                author_id="@bob:local",
            )

    def test_delete_comment(self, content_manager, setup_event_and_key):
        """Test deleting a comment."""
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        bulletin = content_manager.create_bulletin(
            input_key=raw_key,
            event_id=event_id,
            title="Discussion",
            body="Let's discuss",
            author_id="@alice:local",
        )

        comment = content_manager.post_comment(
            input_key=raw_key,
            bulletin_id=bulletin["id"],
            body="Delete me",
            author_id="@bob:local",
        )

        assert content_manager.delete_comment(raw_key, comment["id"]) is True
        comments = content_manager.get_comments(raw_key, bulletin["id"])
        assert len(comments) == 0


class TestGatewayContentEndpoints:
    """Tests for the Gateway content management endpoints."""

    def test_upload_media_via_gateway(self, db, key_manager, setup_event_and_key):
        """Test uploading media through the Gateway."""
        from src.api.gateway import Gateway

        gateway = Gateway(db=db, key_manager=key_manager)
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        data_b64 = base64.b64encode(b"fake-image-data").decode()
        response = gateway.upload_media(
            {
                "key": raw_key,
                "event_id": event_id,
                "filename": "flyer.png",
                "mime_type": "image/png",
                "data": data_b64,
            }
        )

        assert response["status"] == "success"
        assert response["data"]["filename"] == "flyer.png"

    def test_upload_media_invalid_base64(self, db, key_manager, setup_event_and_key):
        """Test that invalid base64 data is rejected."""
        from src.api.gateway import Gateway

        gateway = Gateway(db=db, key_manager=key_manager)
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        response = gateway.upload_media(
            {
                "key": raw_key,
                "event_id": event_id,
                "filename": "flyer.png",
                "mime_type": "image/png",
                "data": "not-valid-base64!!!",
            }
        )

        assert response["status"] == "error"
        assert "base64" in response["message"].lower()

    def test_create_bulletin_via_gateway(self, db, key_manager, setup_event_and_key):
        """Test creating a bulletin through the Gateway."""
        from src.api.gateway import Gateway

        gateway = Gateway(db=db, key_manager=key_manager)
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        response = gateway.create_bulletin(
            {
                "key": raw_key,
                "event_id": event_id,
                "title": "Announcement",
                "body": "Important announcement",
                "author_id": "@alice:local",
            }
        )

        assert response["status"] == "success"
        assert response["data"]["title"] == "Announcement"

    def test_post_comment_via_gateway(self, db, key_manager, setup_event_and_key):
        """Test posting a comment through the Gateway."""
        from src.api.gateway import Gateway

        gateway = Gateway(db=db, key_manager=key_manager)
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        # Create a bulletin first
        bulletin_resp = gateway.create_bulletin(
            {
                "key": raw_key,
                "event_id": event_id,
                "title": "Discussion",
                "body": "Let's discuss",
                "author_id": "@alice:local",
            }
        )
        bulletin_id = bulletin_resp["data"]["id"]

        # Post a comment
        response = gateway.post_comment(
            {
                "key": raw_key,
                "bulletin_id": bulletin_id,
                "body": "My comment",
                "author_id": "@bob:local",
            }
        )

        assert response["status"] == "success"
        assert response["data"]["author_id"] == "@bob:local"

    def test_get_comments_via_gateway(self, db, key_manager, setup_event_and_key):
        """Test getting comments through the Gateway."""
        from src.api.gateway import Gateway

        gateway = Gateway(db=db, key_manager=key_manager)
        raw_key = setup_event_and_key["raw_key"]
        event_id = setup_event_and_key["event_id"]

        # Create a bulletin
        bulletin_resp = gateway.create_bulletin(
            {
                "key": raw_key,
                "event_id": event_id,
                "title": "Discussion",
                "body": "Let's discuss",
                "author_id": "@alice:local",
            }
        )
        bulletin_id = bulletin_resp["data"]["id"]

        # Post a comment
        gateway.post_comment(
            {
                "key": raw_key,
                "bulletin_id": bulletin_id,
                "body": "My comment",
                "author_id": "@bob:local",
            }
        )

        # Get comments
        response = gateway.get_comments({"key": raw_key, "bulletin_id": bulletin_id})

        assert response["status"] == "success"
        assert len(response["data"]) == 1
        assert response["data"][0]["body"] == "My comment"

    def test_access_denied_via_gateway(self, db, key_manager, setup_event_and_key):
        """Test that access denied errors are properly handled."""
        from src.api.gateway import Gateway

        gateway = Gateway(db=db, key_manager=key_manager)
        event_id = setup_event_and_key["event_id"]

        response = gateway.create_bulletin(
            {
                "key": "local:wrong-key",
                "event_id": event_id,
                "title": "Should Fail",
                "body": "Should not be created",
                "author_id": "@alice:local",
            }
        )

        assert response["status"] == "error"
        assert "access" in response["message"].lower() or "key" in response["message"].lower()
