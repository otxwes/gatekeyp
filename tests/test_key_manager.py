import unittest
from datetime import UTC, datetime, timedelta

from helpers import TEST_MASTER_KEY
from hypothesis import given, settings
from hypothesis import strategies as st

from src.core.key_manager import MIN_KEY_ENTROPY_BYTES, KeyManager
from src.db.database_handler import DatabaseHandler

TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"


class TestKeyManager(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseHandler(":memory:", master_key=TEST_MASTER_KEY)
        self.km = KeyManager(db=self.db, hmac_secret=TEST_HMAC_SECRET)

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------
    # Key Generation
    # ------------------------------------------------------------------

    def test_generate_key(self):
        key1 = self.km.generate_key()
        key2 = self.km.generate_key()
        self.assertEqual(len(key1), 64)  # 32 bytes * 2 hex characters per byte
        self.assertNotEqual(key1, key2)

    def test_generate_key_min_entropy(self):
        """Keys must meet minimum entropy requirements."""
        key = self.km.generate_key(MIN_KEY_ENTROPY_BYTES)
        self.assertEqual(len(key), MIN_KEY_ENTROPY_BYTES * 2)

    def test_generate_key_rejects_low_entropy(self):
        """Keys below minimum entropy must be rejected."""
        with self.assertRaises(ValueError):
            self.km.generate_key(MIN_KEY_ENTROPY_BYTES - 1)

    def test_generate_key_high_entropy(self):
        """Larger keys are supported."""
        key = self.km.generate_key(64)
        self.assertEqual(len(key), 128)

    # ------------------------------------------------------------------
    # HMAC Keyed Hashing
    # ------------------------------------------------------------------

    def test_hash_key_uses_hmac(self):
        """Hash must be HMAC-SHA256, not plain SHA-256."""
        import hashlib

        key = "test_key"
        hashed = self.km.hash_key(key)
        # Plain SHA-256 would produce a different result
        plain_sha = hashlib.sha256(key.encode()).hexdigest()
        self.assertNotEqual(hashed, plain_sha)
        self.assertEqual(len(hashed), 64)  # SHA-256 output length

    def test_hash_key_deterministic(self):
        """Same key + same secret produces same hash."""
        key = "test_key"
        self.assertEqual(self.km.hash_key(key), self.km.hash_key(key))

    def test_hash_key_different_secrets(self):
        """Different secrets produce different hashes for the same key."""
        km2 = KeyManager(db=self.db, hmac_secret="different-secret-1234567890")
        key = "test_key"
        self.assertNotEqual(self.km.hash_key(key), km2.hash_key(key))

    def test_verify_key_correct(self):
        """verify_key returns True for the correct key."""
        key = "test_key"
        hashed = self.km.hash_key(key)
        self.assertTrue(self.km.verify_key(key, hashed))

    def test_verify_key_incorrect(self):
        """verify_key returns False for an incorrect key."""
        hashed = self.km.hash_key("correct_key")
        self.assertFalse(self.km.verify_key("wrong_key", hashed))

    def test_verify_key_constant_time(self):
        """verify_key uses constant-time comparison."""
        import hmac

        key = "test_key"
        hashed = self.km.hash_key(key)
        # hmac.compare_digest is constant-time; verify it's used
        self.assertTrue(hmac.compare_digest(self.km.hash_key(key), hashed))

    # ------------------------------------------------------------------
    # Argon2id (optional)
    # ------------------------------------------------------------------

    def test_argon2_hash_and_verify(self):
        """Argon2id hashing and verification roundtrip."""
        km_argon = KeyManager(db=self.db, hmac_secret=TEST_HMAC_SECRET, use_argon2=True)
        key = "test_key"
        hashed = km_argon.hash_key_argon2(key)
        self.assertTrue(km_argon.verify_key_argon2(key, hashed))
        self.assertFalse(km_argon.verify_key_argon2("wrong_key", hashed))

    def test_argon2_not_enabled_raises(self):
        """Argon2 methods raise if not enabled."""
        with self.assertRaises(RuntimeError):
            self.km.hash_key_argon2("test")
        with self.assertRaises(RuntimeError):
            self.km.verify_key_argon2("test", "hash")

    # ------------------------------------------------------------------
    # Federation Prefix Resolution
    # ------------------------------------------------------------------

    def test_resolve_federation_prefix(self):
        identity, local_key = self.km.resolve_federation_prefix("@example:org/key_content")
        self.assertEqual(identity, "example")
        self.assertEqual(local_key, "key_content")

        identity, local_key = self.km.resolve_federation_prefix("local:key_content")
        self.assertEqual(identity, "local")
        self.assertEqual(local_key, "key_content")

    def test_resolve_federation_prefix_no_slash(self):
        """Federated key without a slash still resolves."""
        identity, local_key = self.km.resolve_federation_prefix("@example:org")
        self.assertEqual(identity, "example")
        self.assertEqual(local_key, "org")

    def test_resolve_federation_prefix_invalid(self):
        """Invalid key formats raise ValueError."""
        with self.assertRaises(ValueError):
            self.km.resolve_federation_prefix("")
        with self.assertRaises(ValueError):
            self.km.resolve_federation_prefix("no-prefix")
        with self.assertRaises(ValueError):
            self.km.resolve_federation_prefix(None)

    # ------------------------------------------------------------------
    # Key Validation
    # ------------------------------------------------------------------

    def test_validate_key_valid(self):
        """A valid, non-expired, non-revoked key validates."""
        raw_key = "local:secret_key"
        hashed = self.km.hash_key("secret_key")
        self.db.add_key(hashed, "access")
        result = self.km.validate_key(raw_key)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["org_id"], "local")

    def test_validate_key_nonexistent(self):
        """A key not in the database is invalid."""
        result = self.km.validate_key("local:unknown_key")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["message"], "Key does not exist")

    def test_validate_key_expired(self):
        """An expired key is invalid."""
        hashed = self.km.hash_key("expired_key")
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        self.db.add_key(hashed, "access", expires_at=past)
        result = self.km.validate_key("local:expired_key")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["message"], "Key has expired")

    def test_validate_key_future_expiry(self):
        """A key with future expiry is valid."""
        hashed = self.km.hash_key("future_key")
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        self.db.add_key(hashed, "access", expires_at=future)
        result = self.km.validate_key("local:future_key")
        self.assertEqual(result["status"], "valid")

    def test_validate_key_revoked(self):
        """A revoked key is invalid."""
        hashed = self.km.hash_key("revoked_key")
        self.db.add_key(hashed, "access")
        self.db.revoke_key(hashed)
        result = self.km.validate_key("local:revoked_key")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["message"], "Key has been revoked")

    def test_validate_key_invalid_timestamp(self):
        """A malformed expiration timestamp is handled gracefully."""
        hashed = self.km.hash_key("bad_ts_key")
        self.db.add_key(hashed, "access", expires_at="not-a-timestamp")
        result = self.km.validate_key("local:bad_ts_key")
        self.assertEqual(result["status"], "invalid")

    def test_validate_key_legacy_timestamp_no_tz(self):
        """Legacy timestamps without timezone are treated as UTC."""
        hashed = self.km.hash_key("legacy_key")
        past = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        self.db.add_key(hashed, "access", expires_at=past)
        result = self.km.validate_key("local:legacy_key")
        self.assertEqual(result["status"], "invalid")

    # ------------------------------------------------------------------
    # Key Rotation & Revocation
    # ------------------------------------------------------------------

    def test_revoke_key(self):
        """Revoking a key by raw input works."""
        raw_key = "local:to_revoke"
        hashed = self.km.hash_key("to_revoke")
        self.db.add_key(hashed, "access")
        result = self.km.revoke_key(raw_key)
        self.assertTrue(result)
        self.assertTrue(self.db.is_key_revoked(hashed))

    def test_rotate_key(self):
        """Rotating a key revokes the old and creates a new one."""
        old_hash = self.km.hash_key("old_key")
        self.db.add_key(old_hash, "access")
        self.db.add_content_block("block_rot", "event_1", old_hash, "location", "data")

        new_hash = self.km.rotate_key(old_hash, "new_key")

        # Old key is revoked
        self.assertTrue(self.db.is_key_revoked(old_hash))
        # New key exists
        self.assertIsNotNone(self.db.get_key(new_hash))
        # Content is re-linked to the new key
        content_ids = self.db.get_content_ids_for_key(new_hash)
        self.assertEqual(len(content_ids), 1)
        self.assertEqual(content_ids[0]["content_id"], "block_rot")

    # ------------------------------------------------------------------
    # Fail-Secure Behavior
    # ------------------------------------------------------------------

    def test_missing_hmac_secret_raises(self):
        """KeyManager must fail-secure without an HMAC secret."""
        import os

        old = os.environ.get("GATEKEYP_HMAC_SECRET")
        os.environ.pop("GATEKEYP_HMAC_SECRET", None)
        try:
            with self.assertRaises(ValueError):
                KeyManager(db=self.db)
        finally:
            if old:
                os.environ["GATEKEYP_HMAC_SECRET"] = old


# ----------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ----------------------------------------------------------------------


class TestKeyManagerPropertyBased(unittest.TestCase):
    """Property-based tests for key generation, hashing, and federation."""

    def setUp(self):
        self.db = DatabaseHandler(":memory:", master_key=TEST_MASTER_KEY)
        self.km = KeyManager(db=self.db, hmac_secret=TEST_HMAC_SECRET)

    def tearDown(self):
        self.db.close()

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_hash_key_roundtrip(self, key):
        """verify_key(hash_key(k), k) == True for all valid keys."""
        hashed = self.km.hash_key(key)
        self.assertTrue(self.km.verify_key(key, hashed))

    @given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_hash_key_different_inputs(self, key1, key2):
        """Different keys produce different hashes (collision resistance)."""
        if key1 != key2:
            self.assertNotEqual(self.km.hash_key(key1), self.km.hash_key(key2))

    @given(st.integers(min_value=MIN_KEY_ENTROPY_BYTES, max_value=128))
    @settings(max_examples=20)
    def test_generate_key_length(self, length):
        """Generated keys have the expected length and are hex strings."""
        key = self.km.generate_key(length)
        self.assertEqual(len(key), length * 2)
        # All characters are hex
        import re

        self.assertTrue(re.fullmatch(r"[0-9a-f]+", key))

    @given(st.text(min_size=1, max_size=50).filter(lambda s: "@" not in s and ":" not in s))
    @settings(max_examples=50)
    def test_resolve_federation_prefix_local(self, key_content):
        """local: prefix always resolves to ('local', key_content)."""
        identity, local_key = self.km.resolve_federation_prefix(f"local:{key_content}")
        self.assertEqual(identity, "local")
        self.assertEqual(local_key, key_content)

    @given(
        st.text(min_size=1, max_size=50).filter(lambda s: ":" not in s and "/" not in s),
        st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=50)
    def test_resolve_federation_prefix_federated(self, org, key_content):
        """@org:host/key_content resolves correctly."""
        identity, local_key = self.km.resolve_federation_prefix(f"@{org}:host/{key_content}")
        self.assertEqual(identity, org)
        self.assertEqual(local_key, key_content)


if __name__ == "__main__":
    unittest.main()
