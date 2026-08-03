# Copyright (c) 2026 Gatekeyp contributors

import base64
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any

from src.core.content_manager import (
    ContentAccessError,
    ContentManager,
    ContentValidationError,
)
from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# Configure structured logging (no PII)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("gateway")

# Maximum key length in characters
MAX_KEY_LENGTH = 1024

# Maximum content ID length in characters
MAX_CONTENT_ID_LENGTH = 256


class RateLimiter:
    """
    Per-IP and per-key rate limiting with exponential backoff.

    Uses a sliding window of timestamps. When a client exceeds the limit,
    they are blocked for a backoff period that grows exponentially.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: float = 60.0,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 300.0,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        # key -> deque of timestamps
        self._attempts: dict[str, deque] = defaultdict(deque)
        # key -> backoff_until timestamp
        self._backoff_until: dict[str, float] = {}

    def _is_in_backoff(self, client_id: str) -> bool:
        """Check if a client is currently in a backoff period."""
        until = self._backoff_until.get(client_id, 0.0)
        return time.monotonic() < until

    def _get_backoff_duration(self, client_id: str) -> float:
        """Calculate the current backoff duration for a client."""
        # Count recent failures to determine exponential backoff
        recent = [
            t
            for t in self._attempts.get(client_id, [])
            if time.monotonic() - t < self.window_seconds
        ]
        failures = len(recent)
        if failures == 0:
            return 0.0
        # Exponential backoff: base * 2^(failures-1), capped
        duration = self.base_backoff_seconds * (2 ** (failures - 1))
        return min(duration, self.max_backoff_seconds)

    def check(self, client_id: str) -> bool:
        """
        Check if a request from client_id is allowed.

        Returns True if allowed, False if rate-limited.
        """
        now = time.monotonic()

        # If in backoff, reject
        if self._is_in_backoff(client_id):
            return False

        # Prune old attempts
        attempts = self._attempts[client_id]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()

        # Check if over limit
        if len(attempts) >= self.max_attempts:
            # Enter backoff
            duration = self._get_backoff_duration(client_id)
            self._backoff_until[client_id] = now + duration
            return False

        return True

    def record_attempt(self, client_id: str) -> None:
        """Record an attempt (success or failure) for a client."""
        now = time.monotonic()
        self._attempts[client_id].append(now)

    def record_failure(self, client_id: str) -> None:
        """Record a failed attempt and potentially trigger backoff."""
        self.record_attempt(client_id)
        # If we've hit the limit, enter backoff
        attempts = self._attempts[client_id]
        if len(attempts) >= self.max_attempts:
            duration = self._get_backoff_duration(client_id)
            self._backoff_until[client_id] = time.monotonic() + duration

    def reset(self, client_id: str) -> None:
        """Reset rate limiting state for a client (e.g., after successful auth)."""
        self._attempts.pop(client_id, None)
        self._backoff_until.pop(client_id, None)


class Gateway:
    """
    The primary interface for the application's API layer.
    It orchestrates interactions between logic (KeyManager)
    and data storage (DatabaseHandler).

    Security hardening (Phase 1):
    - Rate limiting (per-IP and per-key) with exponential backoff.
    - Hardened input validation.
    - Structured audit logging (no PII).
    """

    def __init__(
        self,
        db: DatabaseHandler | None = None,
        key_manager: KeyManager | None = None,
        rate_limiter: RateLimiter | None = None,
        content_manager: ContentManager | None = None,
    ) -> None:
        self.db = db if db is not None else DatabaseHandler()
        self.key_manager = key_manager if key_manager is not None else KeyManager(db=self.db)
        self.rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()
        self.content_manager = (
            content_manager
            if content_manager is not None
            else ContentManager(db=self.db, key_manager=self.key_manager)
        )

    # ------------------------------------------------------------------
    # Audit Logging (no PII)
    # ------------------------------------------------------------------

    def _audit_log(self, event: str, **kwargs: object) -> None:
        """
        Structured audit logging. Never logs raw keys, IP addresses, or PII.
        Logs only event type, status, and non-sensitive metadata.
        """
        entry = {"event": event, "timestamp": time.time()}
        entry.update(kwargs)
        logger.info(json.dumps(entry))

    # ------------------------------------------------------------------
    # Input Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_key_format(input_key: object) -> bool:
        """Validate that a key is a non-empty string with reasonable length."""
        if not isinstance(input_key, str):
            return False
        if not input_key.strip():
            return False
        # Keys should be reasonably sized (not megabytes of data)
        return len(input_key) <= MAX_KEY_LENGTH

    @staticmethod
    def _validate_content_id(content_id: object) -> bool:
        """Validate that a content ID is a non-empty string with reasonable length."""
        if not isinstance(content_id, str):
            return False
        if not content_id.strip():
            return False
        return len(content_id) <= MAX_CONTENT_ID_LENGTH

    # ------------------------------------------------------------------
    # Request Processing
    # ------------------------------------------------------------------

    def _reject_request(
        self,
        rate_limit_id: str,
        key_rate_id: str | None,
        reason: str,
        message: str,
    ) -> dict[str, Any]:
        """Record a failure and return an error response."""
        self.rate_limiter.record_failure(rate_limit_id)
        if key_rate_id:
            self.rate_limiter.record_failure(key_rate_id)
        self._audit_log("request_rejected", reason=reason, status="error")
        return {"status": "error", "message": message}

    def _retrieve_content(self, content_id: str) -> dict | None:
        """Retrieve content by ID, checking content blocks then events."""
        try:
            content = self.db.get_content_block(content_id)
            if not content:
                # Fallback to checking if it's an event directly
                content = self.db.get_event(content_id)
        except ValueError:
            self._audit_log("decryption_error", reason="payload_decrypt_failed", status="error")
            return None
        return content

    def _validate_and_rate_limit(
        self,
        input_key: object,
        content_id: object,
        rate_limit_id: str,
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        """
        Validate input and check rate limits.

        Returns a tuple of (error_response, key_rate_id, validated_key).
        If error_response is not None, the request should be rejected.
        """
        # Input validation
        if not self._validate_key_format(input_key):
            return (
                self._reject_request(
                    rate_limit_id, None, "invalid_key_format", "Invalid key format"
                ),
                None,
                None,
            )

        if not self._validate_content_id(content_id):
            return (
                self._reject_request(
                    rate_limit_id, None, "invalid_content_id", "Invalid content ID format"
                ),
                None,
                None,
            )

        # Per-key rate limiting
        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}, None, None

        return None, key_rate_id, str(input_key)

    def process_request(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Processes a generic incoming request to access content.

        Expected payload keys:
            - 'key': The user provided key string (e.g., @org:host/content)
            - 'content_id': The specific block or event ID being accessed.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting. If None, uses
                       a generic identifier (rate limiting still applies per-key).
        """
        input_key = request.get("key")
        content_id = request.get("content_id")

        # Rate limiting identifier: prefer IP, fall back to a generic bucket
        rate_limit_id = client_ip or "unknown"

        # Check rate limit (per-IP)
        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        # Validate input and per-key rate limiting
        error, key_rate_id, validated_key = self._validate_and_rate_limit(
            input_key, content_id, rate_limit_id
        )
        if error is not None:
            return error

        # After error check, these are guaranteed non-None
        if validated_key is None or key_rate_id is None or content_id is None:
            return {"status": "error", "message": "Internal validation error"}

        # 1. Logic/Federation Check
        try:
            validation_result = self.key_manager.validate_key(validated_key)
        except ValueError:
            return self._reject_request(
                rate_limit_id, key_rate_id, "invalid_key_format", "Invalid key"
            )

        if validation_result["status"] != "valid":
            reason = validation_result.get("message", "invalid")
            return self._reject_request(rate_limit_id, key_rate_id, reason, "Invalid key")

        # 2. Database Retrieval
        content = self._retrieve_content(content_id)
        if content is None:
            return self._reject_request(
                rate_limit_id, key_rate_id, "content_not_found", "Content not found"
            )

        # Success: reset rate limiting for this client and key
        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)

        self._audit_log("access_granted", content_id=content_id, status="success")
        return {
            "status": "success",
            "data": content,
            "metadata": {
                "org_id": validation_result["org_id"],
                "key_hash": validation_result["hash"],
            },
        }

    # ------------------------------------------------------------------
    # Content Management (Phase 2)
    # ------------------------------------------------------------------

    def _handle_content_error(
        self,
        rate_limit_id: str,
        key_rate_id: str | None,
        err: Exception,
    ) -> dict[str, Any]:
        """Handle content management errors with proper rate limiting."""
        if isinstance(err, ContentValidationError):
            return self._reject_request(
                rate_limit_id, key_rate_id, "content_validation_error", str(err)
            )
        if isinstance(err, ContentAccessError):
            return self._reject_request(
                rate_limit_id, key_rate_id, "content_access_denied", str(err)
            )
        self._audit_log("content_error", reason="unexpected", status="error")
        return {"status": "error", "message": "Internal content error"}

    def upload_media(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a media asset (flyer, image, document) gated by a key.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'event_id': The event this media belongs to.
            - 'filename': Original filename of the asset.
            - 'mime_type': MIME type of the asset.
            - 'data': Base64-encoded binary data of the asset.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        event_id = request.get("event_id")
        filename = request.get("filename")
        mime_type = request.get("mime_type")
        data_b64 = request.get("data")

        rate_limit_id = client_ip or "unknown"

        # Check rate limit (per-IP)
        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        # Validate inputs
        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(event_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_event_id", "Invalid event ID format"
            )

        if not isinstance(data_b64, str) or not data_b64.strip():
            return self._reject_request(
                rate_limit_id, None, "invalid_media_data", "Invalid base64 data"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        # Decode base64 data
        try:
            data = base64.b64decode(data_b64, validate=True)
        except (TypeError, ValueError):
            return self._reject_request(
                rate_limit_id, key_rate_id, "invalid_media_data", "Invalid base64 data"
            )

        try:
            result = self.content_manager.upload_media(
                input_key=str(input_key),
                event_id=str(event_id),
                filename=str(filename),
                mime_type=str(mime_type),
                data=data,
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("media_uploaded", asset_id=result["id"], status="success")
        return {"status": "success", "data": result}

    def get_media(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve a media asset, verifying the key grants access.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'asset_id': The media asset ID.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        asset_id = request.get("asset_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(asset_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_asset_id", "Invalid asset ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            asset = self.content_manager.get_media(
                input_key=str(input_key),
                asset_id=str(asset_id),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("media_retrieved", asset_id=asset_id, status="success")
        return {"status": "success", "data": asset}

    def list_media(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        List media assets for an event, verifying the key grants access.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'event_id': The event to list media for.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        event_id = request.get("event_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(event_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_event_id", "Invalid event ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            assets = self.content_manager.list_media(
                input_key=str(input_key),
                event_id=str(event_id),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("media_listed", event_id=event_id, status="success")
        return {"status": "success", "data": assets}

    def create_bulletin(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a bulletin (communication board post) gated by a key.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'event_id': The event this bulletin belongs to.
            - 'title': Bulletin title.
            - 'body': Bulletin body content.
            - 'author_id': Identifier of the author.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        event_id = request.get("event_id")
        title = request.get("title")
        body = request.get("body")
        author_id = request.get("author_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(event_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_event_id", "Invalid event ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            result = self.content_manager.create_bulletin(
                input_key=str(input_key),
                event_id=str(event_id),
                title=str(title),
                body=str(body),
                author_id=str(author_id),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("bulletin_created", bulletin_id=result["id"], status="success")
        return {"status": "success", "data": result}

    def get_bulletin(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve a bulletin, verifying the key grants access.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'bulletin_id': The bulletin ID.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        bulletin_id = request.get("bulletin_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(bulletin_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_bulletin_id", "Invalid bulletin ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            bulletin = self.content_manager.get_bulletin(
                input_key=str(input_key),
                bulletin_id=str(bulletin_id),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("bulletin_retrieved", bulletin_id=bulletin_id, status="success")
        return {"status": "success", "data": bulletin}

    def list_bulletins(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        List bulletins for an event, verifying the key grants access.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'event_id': The event to list bulletins for.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        event_id = request.get("event_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(event_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_event_id", "Invalid event ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            bulletins = self.content_manager.list_bulletins(
                input_key=str(input_key),
                event_id=str(event_id),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("bulletins_listed", event_id=event_id, status="success")
        return {"status": "success", "data": bulletins}

    def post_comment(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Post a comment on a bulletin, verifying the key grants access.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'bulletin_id': The bulletin to comment on.
            - 'body': Comment body content.
            - 'author_id': Identifier of the author.
            - 'parent_comment_id': Optional parent comment ID for threaded replies.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        bulletin_id = request.get("bulletin_id")
        body = request.get("body")
        author_id = request.get("author_id")
        parent_comment_id = request.get("parent_comment_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(bulletin_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_bulletin_id", "Invalid bulletin ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            result = self.content_manager.post_comment(
                input_key=str(input_key),
                bulletin_id=str(bulletin_id),
                body=str(body),
                author_id=str(author_id),
                parent_comment_id=(
                    str(parent_comment_id) if parent_comment_id is not None else None
                ),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("comment_posted", comment_id=result["id"], status="success")
        return {"status": "success", "data": result}

    def get_comments(
        self,
        request: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve all comments for a bulletin, verifying the key grants access.

        Expected payload keys:
            - 'key': The user provided key string.
            - 'bulletin_id': The bulletin to get comments for.

        Args:
            request: The request payload.
            client_ip: Optional client IP for rate limiting.
        """
        input_key = request.get("key")
        bulletin_id = request.get("bulletin_id")

        rate_limit_id = client_ip or "unknown"

        if not self.rate_limiter.check(rate_limit_id):
            self._audit_log("rate_limited", reason="ip_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        if not self._validate_key_format(input_key):
            return self._reject_request(
                rate_limit_id, None, "invalid_key_format", "Invalid key format"
            )
        if not self._validate_content_id(bulletin_id):
            return self._reject_request(
                rate_limit_id, None, "invalid_bulletin_id", "Invalid bulletin ID format"
            )

        key_rate_id = f"key:{input_key}"
        if not self.rate_limiter.check(key_rate_id):
            self._audit_log("rate_limited", reason="key_limit", status="error")
            return {"status": "error", "message": "Rate limit exceeded"}

        try:
            comments = self.content_manager.get_comments(
                input_key=str(input_key),
                bulletin_id=str(bulletin_id),
            )
        except (ContentValidationError, ContentAccessError) as err:
            return self._handle_content_error(rate_limit_id, key_rate_id, err)

        self.rate_limiter.reset(rate_limit_id)
        self.rate_limiter.reset(key_rate_id)
        self._audit_log("comments_retrieved", bulletin_id=bulletin_id, status="success")
        return {"status": "success", "data": comments}
