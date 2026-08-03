import os
import unittest
from datetime import UTC, datetime, timedelta

from helpers import TEST_MASTER_KEY
from hypothesis import given, settings
from hypothesis import strategies as st

from src.api.gateway import Gateway, RateLimiter
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"


class TestSecurityAudit(unittest.TestCase):
    """
    Security audit tests validating the threat model checklist:
    - No third-party tracking/analytics dependencies
    - All sensitive payloads encrypted at rest
    - Keys stored as keyed hashes (HMAC/Argon2id), never plaintext
    - Rate limiting on all key-validation endpoints
    - Audit logging without PII
    - Key expiration + revocation supported
    """

    def setUp(self):
        self.db = DatabaseHandler(":memory:", master_key=TEST_MASTER_KEY)
        self.km = KeyManager(db=self.db, hmac_secret=TEST_HMAC_SECRET)
        self.gateway = Gateway(db=self.db, key_manager=self.km)

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------
    # 1. Keys stored as keyed hashes, never plaintext
    # ------------------------------------------------------------------

    def test_keys_never_stored_in_plaintext(self):
        """Raw keys must never appear in the database."""
        hashed = self.km.hash_key("super_secret_key_12345")
        self.db.add_key(hashed, "access")

        # Query the raw database
        self.db.cursor.execute("SELECT * FROM keys")
        rows = self.db.cursor.fetchall()
        for row in rows:
            for field in row:
                if isinstance(field, str):
                    self.assertNotIn("super_secret_key_12345", field)

    def test_hash_is_hmac_not_plain_sha256(self):
        """Stored hashes must be HMAC-SHA256, not plain SHA-256."""
        import hashlib

        raw_key = "test_key"
        hashed = self.km.hash_key(raw_key)
        plain_sha = hashlib.sha256(raw_key.encode()).hexdigest()
        self.assertNotEqual(hashed, plain_sha)

    def test_hmac_secret_required(self):
        """KeyManager fails-secure without an HMAC secret."""
        old = os.environ.get("GATEKEYP_HMAC_SECRET")
        os.environ.pop("GATEKEYP_HMAC_SECRET", None)
        try:
            with self.assertRaises(ValueError):
                KeyManager(db=self.db)
        finally:
            if old:
                os.environ["GATEKEYP_HMAC_SECRET"] = old

    # ------------------------------------------------------------------
    # 2. All sensitive payloads encrypted at rest
    # ------------------------------------------------------------------

    def test_content_payload_encrypted_at_rest(self):
        """Content block payloads must be encrypted in the database."""
        self.db.add_content_block("block_1", "event_1", "key_1", "location", "40.7128,-74.0060")
        self.db.cursor.execute(
            "SELECT payload FROM content_blocks WHERE block_id = ?", ("block_1",)
        )
        raw = self.db.cursor.fetchone()[0]
        self.assertNotIn("40.7128", raw)
        self.assertNotIn("-74.0060", raw)

    def test_event_location_encrypted_at_rest(self):
        """Event location data must be encrypted in the database."""
        self.db.add_event(
            "event_1", "Secret Show", "desc", "org_1", location_data="40.7128,-74.0060"
        )
        self.db.cursor.execute("SELECT location_data FROM events WHERE event_id = ?", ("event_1",))
        raw = self.db.cursor.fetchone()[0]
        self.assertNotIn("40.7128", raw)
        self.assertNotIn("-74.0060", raw)

    def test_master_key_required(self):
        """DatabaseHandler fails-secure without a master key."""
        old = os.environ.get("GATEKEYP_MASTER_KEY")
        os.environ.pop("GATEKEYP_MASTER_KEY", None)
        try:
            with self.assertRaises(ValueError):
                DatabaseHandler(":memory:")
        finally:
            if old:
                os.environ["GATEKEYP_MASTER_KEY"] = old

    # ------------------------------------------------------------------
    # 3. Rate limiting on all key-validation endpoints
    # ------------------------------------------------------------------

    def test_rate_limiting_enabled_by_default(self):
        """Gateway has rate limiting by default (fail-secure)."""
        gateway = Gateway(db=self.db, key_manager=self.km)
        self.assertIsNotNone(gateway.rate_limiter)
        self.assertGreater(gateway.rate_limiter.max_attempts, 0)

    def test_brute_force_attempts_blocked(self):
        """Repeated invalid key attempts are rate-limited."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60.0)
        gateway = Gateway(db=self.db, key_manager=self.km, rate_limiter=limiter)

        # Attempt brute-force
        for i in range(3):
            gateway.process_request({"key": f"local:guess_{i}", "content_id": "block_1"})

        # 4th attempt should be rate-limited
        response = gateway.process_request({"key": "local:guess_3", "content_id": "block_1"})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Rate limit exceeded")

    # ------------------------------------------------------------------
    # 4. Audit logging without PII
    # ------------------------------------------------------------------

    def test_audit_log_contains_no_raw_keys(self):
        """Audit logs must not contain raw keys or PII."""
        import io
        import logging

        # Capture log output
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("gateway")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            raw_key = "local:super_secret_key_12345"
            self.gateway.process_request({"key": raw_key, "content_id": "block_1"})
            log_output = log_stream.getvalue()
            self.assertNotIn("super_secret_key_12345", log_output)
        finally:
            logger.removeHandler(handler)

    # ------------------------------------------------------------------
    # 5. Key expiration + revocation supported
    # ------------------------------------------------------------------

    def test_expired_key_rejected(self):
        """Expired keys are rejected."""
        hashed = self.km.hash_key("expired_key")
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        self.db.add_key(hashed, "access", expires_at=past)
        result = self.km.validate_key("local:expired_key")
        self.assertEqual(result["status"], "invalid")

    def test_revoked_key_rejected(self):
        """Revoked keys are rejected."""
        hashed = self.km.hash_key("revoked_key")
        self.db.add_key(hashed, "access")
        self.db.revoke_key(hashed)
        result = self.km.validate_key("local:revoked_key")
        self.assertEqual(result["status"], "invalid")

    # ------------------------------------------------------------------
    # 6. No third-party tracking/analytics dependencies
    # ------------------------------------------------------------------

    def test_no_third_party_imports(self):
        """Source code must not import third-party tracking/analytics libraries."""
        import ast
        import pathlib

        forbidden = {
            "google",
            "facebook",
            "analytics",
            "tracking",
            "mixpanel",
            "segment",
            "amplitude",
            "hotjar",
            "fullstory",
        }

        src_dir = pathlib.Path("src")
        for py_file in src_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_root = alias.name.split(".")[0].lower()
                        self.assertNotIn(
                            module_root, forbidden, f"Forbidden import '{alias.name}' in {py_file}"
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module_root = node.module.split(".")[0].lower()
                    self.assertNotIn(
                        module_root, forbidden, f"Forbidden import '{node.module}' in {py_file}"
                    )


class TestEncryptionPropertyBased(unittest.TestCase):
    """Property-based tests for encryption-at-rest roundtrip."""

    def setUp(self):
        self.db = DatabaseHandler(":memory:", master_key=TEST_MASTER_KEY)

    def tearDown(self):
        self.db.close()

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_content_payload_roundtrip(self, payload):
        """Encrypt/decrypt roundtrip preserves content for arbitrary payloads."""
        import uuid

        block_id = f"block_{uuid.uuid4().hex}"
        self.db.add_content_block(block_id, "event_1", "key_1", "location", payload)
        content = self.db.get_content_block(block_id)
        self.assertEqual(content["payload"], payload)

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_event_location_roundtrip(self, location):
        """Event location encrypt/decrypt roundtrip preserves data."""
        import uuid

        event_id = f"event_{uuid.uuid4().hex}"
        self.db.add_event(event_id, "Title", "Desc", "org_1", location_data=location)
        event = self.db.get_event(event_id)
        self.assertEqual(event["location_data"], location)

    @given(st.text(min_size=8, max_size=100))
    @settings(max_examples=50)
    def test_encrypted_payload_not_plaintext(self, payload):
        """Encrypted payloads never contain the plaintext."""
        import uuid

        block_id = f"block_{uuid.uuid4().hex}"
        self.db.add_content_block(block_id, "event_1", "key_1", "location", payload)
        self.db.cursor.execute("SELECT payload FROM content_blocks WHERE block_id = ?", (block_id,))
        raw = self.db.cursor.fetchone()[0]
        self.assertNotIn(payload, raw)


if __name__ == "__main__":
    unittest.main()
