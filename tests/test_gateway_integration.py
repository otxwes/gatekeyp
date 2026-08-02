import unittest

from src.api.gateway import Gateway
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler


class TestGatewayIntegration(unittest.TestCase):
    """Integration tests for the full request flow: Gateway → KeyManager → DatabaseHandler."""

    def setUp(self):
        # Use an in-memory database for isolation
        self.db = DatabaseHandler(":memory:")
        self.gateway = Gateway()
        # Inject the in-memory DB into the gateway and its key manager
        self.gateway.db = self.db
        self.gateway.key_manager.db = self.db

    def tearDown(self):
        self.db.close()

    def _seed_valid_key_and_content(self):
        """Helper: create a valid key and a content block it unlocks."""
        raw_key = "local:secret_key"
        hashed = KeyManager.hash_key("secret_key")
        self.db.add_key("entry_1", hashed, "access")
        self.db.add_content_block("block_1", "event_1", hashed, "location", "40.7128,-74.0060")
        return raw_key

    def test_successful_access_flow(self):
        """A valid key + existing content block returns success with data."""
        raw_key = self._seed_valid_key_and_content()
        response = self.gateway.process_request({"key": raw_key, "content_id": "block_1"})

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["data"]["id"], "block_1")
        self.assertEqual(response["data"]["payload"], "40.7128,-74.0060")
        self.assertEqual(response["metadata"]["org_id"], "local")

    def test_invalid_key_format(self):
        """A non-string or missing key returns an error."""
        response = self.gateway.process_request({"key": None, "content_id": "block_1"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key format")

    def test_missing_content_id(self):
        """A missing content_id returns an error."""
        response = self.gateway.process_request({"key": "local:secret_key"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid content ID format")

    def test_nonexistent_key(self):
        """A key that doesn't exist in the DB returns an error."""
        response = self.gateway.process_request({"key": "local:unknown_key", "content_id": "block_1"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key")

    def test_content_not_found(self):
        """A valid key but missing content returns an error."""
        raw_key = self._seed_valid_key_and_content()
        response = self.gateway.process_request({"key": raw_key, "content_id": "missing_block"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Content not found")

    def test_expired_key_rejected(self):
        """An expired key is rejected during validation."""
        hashed = KeyManager.hash_key("expired_key")
        self.db.add_key("entry_2", hashed, "access", expires_at="2000-01-01T00:00:00")
        self.db.add_content_block("block_2", "event_2", hashed, "location", "data")

        response = self.gateway.process_request({"key": "local:expired_key", "content_id": "block_2"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key")

    def test_event_fallback_access(self):
        """A valid key can also unlock an event directly (fallback path)."""
        hashed = KeyManager.hash_key("event_key")
        self.db.add_key("entry_3", hashed, "access")
        self.db.add_event("event_3", "Underground Show", "Secret location", "org_1")

        response = self.gateway.process_request({"key": "local:event_key", "content_id": "event_3"})
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["data"]["id"], "event_3")
        self.assertEqual(response["data"]["title"], "Underground Show")


if __name__ == '__main__':
    unittest.main()