import unittest

from helpers import TEST_MASTER_KEY

from src.api.gateway import Gateway, RateLimiter
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"


class TestGatewayIntegration(unittest.TestCase):
    """Integration tests for the full request flow: Gateway → KeyManager → DatabaseHandler."""

    def setUp(self):
        # Use an in-memory database for isolation
        self.db = DatabaseHandler(":memory:", master_key=TEST_MASTER_KEY)
        self.km = KeyManager(db=self.db, hmac_secret=TEST_HMAC_SECRET)
        self.gateway = Gateway(db=self.db, key_manager=self.km)

    def tearDown(self):
        self.db.close()

    def _seed_valid_key_and_content(self):
        """Helper: create a valid key and a content block it unlocks."""
        raw_key = "local:secret_key"
        hashed = self.km.hash_key("secret_key")
        self.db.add_key(hashed, "access")
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
        response = self.gateway.process_request(
            {"key": "local:unknown_key", "content_id": "block_1"}
        )
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
        hashed = self.km.hash_key("expired_key")
        self.db.add_key(hashed, "access", expires_at="2000-01-01T00:00:00")
        self.db.add_content_block("block_2", "event_2", hashed, "location", "data")

        response = self.gateway.process_request(
            {"key": "local:expired_key", "content_id": "block_2"}
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key")

    def test_event_fallback_access(self):
        """A valid key can also unlock an event directly (fallback path)."""
        hashed = self.km.hash_key("event_key")
        self.db.add_key(hashed, "access")
        self.db.add_event("event_3", "Underground Show", "Secret location", "org_1")

        response = self.gateway.process_request({"key": "local:event_key", "content_id": "event_3"})
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["data"]["id"], "event_3")
        self.assertEqual(response["data"]["title"], "Underground Show")

    def test_revoked_key_rejected(self):
        """A revoked key is rejected."""
        hashed = self.km.hash_key("revoked_key")
        self.db.add_key(hashed, "access")
        self.db.add_content_block("block_4", "event_4", hashed, "location", "data")
        self.db.revoke_key(hashed)

        response = self.gateway.process_request(
            {"key": "local:revoked_key", "content_id": "block_4"}
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key")

    def test_oversized_key_rejected(self):
        """An oversized key is rejected by input validation."""
        response = self.gateway.process_request(
            {"key": "local:" + "x" * 2000, "content_id": "block_1"}
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key format")

    def test_oversized_content_id_rejected(self):
        """An oversized content_id is rejected by input validation."""
        response = self.gateway.process_request(
            {"key": "local:secret_key", "content_id": "x" * 500}
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid content ID format")

    def test_whitespace_key_rejected(self):
        """A whitespace-only key is rejected."""
        response = self.gateway.process_request({"key": "   ", "content_id": "block_1"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key format")

    def test_non_string_content_id_rejected(self):
        """A non-string content_id is rejected."""
        response = self.gateway.process_request({"key": "local:secret_key", "content_id": 123})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid content ID format")


class TestRateLimiter(unittest.TestCase):
    """Unit tests for the RateLimiter with exponential backoff."""

    def setUp(self):
        self.limiter = RateLimiter(max_attempts=3, window_seconds=60.0)

    def test_allows_requests_under_limit(self):
        """Requests under the limit are allowed."""
        self.assertTrue(self.limiter.check("client_1"))
        self.limiter.record_attempt("client_1")
        self.assertTrue(self.limiter.check("client_1"))
        self.limiter.record_attempt("client_1")
        self.assertTrue(self.limiter.check("client_1"))

    def test_blocks_after_limit(self):
        """Requests over the limit are blocked."""
        for _ in range(3):
            self.limiter.record_attempt("client_1")
        self.assertFalse(self.limiter.check("client_1"))

    def test_independent_clients(self):
        """Rate limiting is per-client."""
        for _ in range(3):
            self.limiter.record_attempt("client_1")
        self.assertFalse(self.limiter.check("client_1"))
        self.assertTrue(self.limiter.check("client_2"))

    def test_reset_clears_state(self):
        """Reset clears rate limiting state."""
        for _ in range(3):
            self.limiter.record_attempt("client_1")
        self.assertFalse(self.limiter.check("client_1"))
        self.limiter.reset("client_1")
        self.assertTrue(self.limiter.check("client_1"))

    def test_exponential_backoff(self):
        """Backoff duration grows exponentially."""
        limiter = RateLimiter(max_attempts=2, base_backoff_seconds=1.0)
        limiter.record_failure("client_1")
        limiter.record_failure("client_1")
        # After 2 failures, backoff should be 2^1 = 2 seconds
        self.assertFalse(limiter.check("client_1"))
        # Backoff duration should be at least 2 seconds
        self.assertGreaterEqual(limiter._get_backoff_duration("client_1"), 2.0)

    def test_backoff_capped(self):
        """Backoff duration is capped at max_backoff_seconds."""
        limiter = RateLimiter(max_attempts=1, base_backoff_seconds=1.0, max_backoff_seconds=4.0)
        # Simulate many failures
        for _ in range(10):
            limiter.record_failure("client_1")
        self.assertLessEqual(limiter._get_backoff_duration("client_1"), 4.0)


class TestGatewayRateLimiting(unittest.TestCase):
    """Integration tests for gateway rate limiting."""

    def setUp(self):
        self.db = DatabaseHandler(":memory:", master_key=TEST_MASTER_KEY)
        self.km = KeyManager(db=self.db, hmac_secret=TEST_HMAC_SECRET)
        self.limiter = RateLimiter(max_attempts=3, window_seconds=60.0)
        self.gateway = Gateway(db=self.db, key_manager=self.km, rate_limiter=self.limiter)

    def tearDown(self):
        self.db.close()

    def test_rate_limited_after_failures(self):
        """Repeated failures trigger rate limiting."""
        for _ in range(3):
            self.gateway.process_request({"key": "local:bad_key", "content_id": "block_1"})

        response = self.gateway.process_request({"key": "local:bad_key", "content_id": "block_1"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Rate limit exceeded")

    def test_success_resets_rate_limit(self):
        """A successful request resets the rate limit."""
        hashed = self.km.hash_key("good_key")
        self.db.add_key(hashed, "access")
        self.db.add_content_block("block_1", "event_1", hashed, "location", "data")

        # Fail twice
        self.gateway.process_request({"key": "local:bad_key", "content_id": "block_1"})
        self.gateway.process_request({"key": "local:bad_key", "content_id": "block_1"})

        # Success resets
        response = self.gateway.process_request({"key": "local:good_key", "content_id": "block_1"})
        self.assertEqual(response["status"], "success")

        # Now can try again
        response = self.gateway.process_request({"key": "local:good_key", "content_id": "block_1"})
        self.assertEqual(response["status"], "success")

    def test_per_ip_rate_limiting(self):
        """Rate limiting applies per-IP."""
        for _ in range(3):
            self.gateway.process_request(
                {"key": "local:bad_key", "content_id": "block_1"}, client_ip="1.2.3.4"
            )

        response = self.gateway.process_request(
            {"key": "local:bad_key", "content_id": "block_1"}, client_ip="1.2.3.4"
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Rate limit exceeded")

        # Different IP with a different key is not limited
        response = self.gateway.process_request(
            {"key": "local:other_key", "content_id": "block_1"}, client_ip="5.6.7.8"
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Invalid key")


if __name__ == "__main__":
    unittest.main()
