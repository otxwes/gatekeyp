# Copyright (c) 2026 Gatekeyp contributors

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src.db.database_handler import DatabaseHandler

# Constants for Key Types
KEY_TYPE_ACCESS = "access"
KEY_TYPE_MASTER = "master"

# Minimum entropy requirement: 128 bits (16 bytes) of randomness
MIN_KEY_ENTROPY_BYTES = 16

# Default HMAC secret length in bytes
HMAC_SECRET_LENGTH = 32


class MissingHMACSecretError(ValueError):
    """Raised when no HMAC secret is available."""

    def __init__(self) -> None:
        super().__init__(
            "GATEKEYP_HMAC_SECRET environment variable must be set "
            "for keyed hashing. Refusing to start with unkeyed SHA-256."
        )


class InsufficientKeyEntropyError(ValueError):
    """Raised when a key does not meet minimum entropy requirements."""

    def __init__(self, min_bytes: int) -> None:
        super().__init__(
            f"Key length must be at least {min_bytes} bytes "
            f"({min_bytes * 8} bits) to meet minimum entropy requirements"
        )


class Argon2NotEnabledError(RuntimeError):
    """Raised when Argon2id is used but not enabled."""

    def __init__(self) -> None:
        super().__init__("Argon2id hashing not enabled. Set use_argon2=True.")


class InvalidKeyFormatError(ValueError):
    """Raised when a key has an invalid format."""

    def __init__(self) -> None:
        super().__init__("Invalid key format")


class KeyManager:
    """
    Core logic for handling and validating keys within Gatekeyp.

    Security hardening (Phase 1):
    - HMAC-SHA256 keyed by a per-instance secret for stored key verification
      (replaces plain SHA-256, which is vulnerable to offline brute-force).
    - Argon2id for password-style key verification (optional, higher cost).
    - Key rotation and revocation support.
    - Minimum key entropy enforcement at generation.
    """

    def __init__(
        self,
        db: DatabaseHandler | None = None,
        hmac_secret: str | None = None,
        *,
        use_argon2: bool = False,
    ) -> None:
        """
        Initialize the KeyManager.

        Fail-secure: requires an HMAC secret. If not provided, reads from
        GATEKEYP_HMAC_SECRET env var. If neither is available, the application
        refuses to start rather than using a weak default.

        Args:
            db: Optional shared DatabaseHandler instance.
            hmac_secret: Per-instance secret for HMAC keyed hashing.
            use_argon2: If True, use Argon2id for key verification instead of HMAC.
        """
        self.db = db if db is not None else DatabaseHandler()
        if hmac_secret is None:
            hmac_secret = os.environ.get("GATEKEYP_HMAC_SECRET")
        if hmac_secret is None:
            raise MissingHMACSecretError
        self.hmac_secret = hmac_secret.encode() if isinstance(hmac_secret, str) else hmac_secret
        self.use_argon2 = use_argon2
        self.argon2_hasher = PasswordHasher() if use_argon2 else None

    # ------------------------------------------------------------------
    # Key Generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_key(length: int = 32) -> str:
        """
        Generates a cryptographically secure, opaque key as a hex string.

        Enforces minimum entropy: the key must be at least MIN_KEY_ENTROPY_BYTES
        (128 bits) of randomness.
        """
        if length < MIN_KEY_ENTROPY_BYTES:
            raise InsufficientKeyEntropyError(MIN_KEY_ENTROPY_BYTES)
        return secrets.token_hex(length)

    # ------------------------------------------------------------------
    # Key Hashing (HMAC-SHA256)
    # ------------------------------------------------------------------

    def hash_key(self, input_key: str) -> str:
        """
        Hashes an input key using HMAC-SHA256 keyed by the per-instance secret.

        This prevents offline brute-force attacks: an attacker who obtains the
        database cannot compute the HMAC without the secret key.
        """
        return hmac.new(
            self.hmac_secret,
            input_key.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_key(self, input_key: str, stored_hash: str) -> bool:
        """
        Verify an input key against a stored hash using constant-time comparison.

        Uses hmac.compare_digest to prevent timing attacks.
        """
        computed = self.hash_key(input_key)
        return hmac.compare_digest(computed, stored_hash)

    # ------------------------------------------------------------------
    # Argon2id (optional, higher-cost verification)
    # ------------------------------------------------------------------

    def hash_key_argon2(self, input_key: str) -> str:
        """Hash a key using Argon2id (memory-hard, resistant to GPU brute-force)."""
        if not self.argon2_hasher:
            raise Argon2NotEnabledError
        return self.argon2_hasher.hash(input_key)

    def verify_key_argon2(self, input_key: str, stored_hash: str) -> bool:
        """Verify a key against an Argon2id hash."""
        if not self.argon2_hasher:
            raise Argon2NotEnabledError
        try:
            self.argon2_hasher.verify(stored_hash, input_key)
        except VerifyMismatchError:
            return False
        else:
            return True

    # ------------------------------------------------------------------
    # Federation Prefix Resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_federation_prefix(raw_key: str) -> tuple[str, str]:
        """
        Parses the key to determine if it belongs to a specific
        instance or a federated host.
        Example format: @org_name:host_identifier/key_content
        """
        if not isinstance(raw_key, str) or not raw_key:
            raise InvalidKeyFormatError
        # Local keys take precedence over federated format
        if raw_key.startswith("local:"):
            local_key = raw_key.split(":", 1)[1]
            if not local_key:
                raise InvalidKeyFormatError
            return "local", local_key
        if "@" in raw_key:
            prefix_end_index = raw_key.find(":")
            if prefix_end_index != -1:
                identity = raw_key[1:prefix_end_index]
                local_key_start_index = raw_key.find("/", prefix_end_index)
                if local_key_start_index != -1:
                    local_key = raw_key[local_key_start_index + 1 :]
                else:
                    local_key = raw_key[prefix_end_index + 1 :]
                if not identity or not local_key:
                    raise InvalidKeyFormatError
                return identity, local_key
        raise InvalidKeyFormatError

    # ------------------------------------------------------------------
    # Key Validation
    # ------------------------------------------------------------------

    def validate_key(self, input_key: str) -> dict:
        """
        Validates a provided key and returns information about the
        associated content.

        Checks:
        1. Federation prefix resolution
        2. Key existence in database
        3. Key expiration
        4. Key revocation status
        """
        org_id, local_key = self.resolve_federation_prefix(input_key)
        hashed = self.hash_key(local_key)

        key_info = self.db.get_key(hashed)

        if not key_info:
            return {"status": "invalid", "message": "Key does not exist"}

        # Check revocation
        if key_info.get("revoked"):
            return {"status": "invalid", "message": "Key has been revoked"}

        # Check expiration
        expires_at = key_info.get("expires_at")
        current_time = datetime.now(UTC)

        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt.tzinfo is None:
                    # Legacy timestamps without timezone are treated as UTC
                    expires_dt = expires_dt.replace(tzinfo=UTC)
                if current_time > expires_dt:
                    return {"status": "invalid", "message": "Key has expired"}
            except ValueError:
                return {"status": "invalid", "message": "Invalid expiration timestamp"}

        return {
            "status": "valid",
            "org_id": org_id,
            "hash": hashed,
            "expires_at": expires_at,
            "revoked": False,
        }

    # ------------------------------------------------------------------
    # Key Rotation & Revocation
    # ------------------------------------------------------------------

    def rotate_key(
        self,
        old_key_hash: str,
        new_key: str,
        key_type: str = KEY_TYPE_ACCESS,
        expires_at: str | None = None,
        owner_id: str | None = None,
    ) -> str:
        """
        Rotate a key: revoke the old key and create a new one.

        Returns the new key hash.
        """
        # Revoke the old key
        self.db.revoke_key(old_key_hash)

        # Create the new key
        new_hash = self.hash_key(new_key)
        self.db.add_key(
            hash_key=new_hash,
            key_type=key_type,
            expires_at=expires_at,
            owner_id=owner_id,
        )

        # Re-link content from the old key to the new key
        content_ids = self.db.get_content_ids_for_key(old_key_hash)
        for content in content_ids:
            self.db.add_key_content_link(new_hash, content["content_id"], content["content_type"])

        return new_hash

    def revoke_key(self, input_key: str) -> bool:
        """
        Revoke a key by its raw input value.

        Returns True if the key was found and revoked.
        """
        _, local_key = self.resolve_federation_prefix(input_key)
        hashed = self.hash_key(local_key)
        return self.db.revoke_key(hashed)
