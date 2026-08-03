# Copyright (c) 2026 Gatekeyp contributors

import secrets

from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

# Maximum sizes for content validation
MAX_TITLE_LENGTH = 256
MAX_BODY_LENGTH = 65536  # 64 KB
MAX_FILENAME_LENGTH = 256
MAX_MEDIA_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_COMMENT_LENGTH = 16384  # 16 KB
MAX_AUTHOR_ID_LENGTH = 256

# Allowed MIME types for media assets
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
}


class ContentValidationError(ValueError):
    """Raised when content fails validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ContentAccessError(PermissionError):
    """Raised when a key does not grant access to the requested content."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ContentManager:
    """
    Manages content hosting (media assets, flyers, descriptions) and
    secure communication boards (bulletins, comments) for Gatekeyp.

    All content is gated by Keys and encrypted at rest.
    """

    def __init__(
        self,
        db: DatabaseHandler,
        key_manager: KeyManager,
    ) -> None:
        """
        Initialize the ContentManager.

        Args:
            db: Shared DatabaseHandler instance.
            key_manager: Shared KeyManager instance for key validation.
        """
        self.db = db
        self.key_manager = key_manager

    # ------------------------------------------------------------------
    # ID Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_id(prefix: str) -> str:
        """Generate a unique content ID with a prefix."""
        return f"{prefix}_{secrets.token_hex(16)}"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_text(value: str, field_name: str, max_length: int) -> None:
        """Validate that a text field is non-empty and within length limits."""
        if not isinstance(value, str):
            message = f"{field_name} must be a string"
            raise ContentValidationError(message)
        if not value.strip():
            message = f"{field_name} cannot be empty"
            raise ContentValidationError(message)
        if len(value) > max_length:
            message = f"{field_name} exceeds maximum length of {max_length} characters"
            raise ContentValidationError(message)

    @staticmethod
    def _validate_mime_type(mime_type: str) -> None:
        """Validate that a MIME type is in the allowed set."""
        if mime_type not in ALLOWED_MIME_TYPES:
            message = f"Unsupported MIME type: {mime_type}"
            raise ContentValidationError(message)

    @staticmethod
    def _validate_media_size(data: bytes) -> None:
        """Validate that media data is within size limits."""
        if len(data) > MAX_MEDIA_SIZE_BYTES:
            message = f"Media exceeds maximum size of {MAX_MEDIA_SIZE_BYTES} bytes"
            raise ContentValidationError(message)

    # ------------------------------------------------------------------
    # Key Access Verification
    # ------------------------------------------------------------------

    def _verify_key_access(self, input_key: str, content_id: str) -> str:
        """
        Verify that a key grants access to a content item.

        Returns the key hash if access is granted.
        Raises ContentAccessError if the key is invalid or does not grant access.
        """
        validation = self.key_manager.validate_key(input_key)
        if validation["status"] != "valid":
            raise ContentAccessError(validation.get("message", "Invalid key"))

        key_hash = validation["hash"]
        content_ids = self.db.get_content_ids_for_key(key_hash)
        if not any(c["content_id"] == content_id for c in content_ids):
            message = "Key does not grant access to this content"
            raise ContentAccessError(message)

        return key_hash

    # ------------------------------------------------------------------
    # Media Assets (Content Hosting)
    # ------------------------------------------------------------------

    def upload_media(
        self,
        input_key: str,
        event_id: str,
        filename: str,
        mime_type: str,
        data: bytes,
    ) -> dict:
        """
        Upload a media asset (flyer, image, document) gated by a key.

        The binary data is encrypted at rest. The key must be valid and
        must have access to the specified event.

        Args:
            input_key: The raw key string.
            event_id: The event this media belongs to.
            filename: Original filename of the asset.
            mime_type: MIME type of the asset.
            data: Raw binary data of the asset.

        Returns:
            Metadata about the uploaded asset (no binary data).
        """
        # Validate inputs
        self._validate_text(filename, "filename", MAX_FILENAME_LENGTH)
        self._validate_mime_type(mime_type)
        self._validate_media_size(data)

        # Verify the key grants access to the event
        key_hash = self._verify_key_access(input_key, event_id)

        # Generate a unique asset ID
        asset_id = self._generate_id("asset")

        # Store the asset
        self.db.add_media_asset(
            asset_id=asset_id,
            event_id=event_id,
            key_id=key_hash,
            filename=filename,
            mime_type=mime_type,
            data=data,
        )

        return {
            "id": asset_id,
            "event_id": event_id,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": len(data),
        }

    def get_media(
        self,
        input_key: str,
        asset_id: str,
    ) -> dict:
        """
        Retrieve a media asset, verifying the key grants access.

        Args:
            input_key: The raw key string.
            asset_id: The media asset ID.

        Returns:
            The media asset including decrypted binary data.
        """
        # Verify the key grants access to this asset
        self._verify_key_access(input_key, asset_id)

        asset = self.db.get_media_asset(asset_id)
        if asset is None:
            message = "Media asset not found"
            raise ContentAccessError(message)

        return asset

    def list_media(
        self,
        input_key: str,
        event_id: str,
    ) -> list[dict]:
        """
        List media assets for an event, verifying the key grants access.

        Args:
            input_key: The raw key string.
            event_id: The event to list media for.

        Returns:
            List of media asset metadata (no binary data).
        """
        # Verify the key grants access to the event
        self._verify_key_access(input_key, event_id)

        return self.db.list_media_assets(event_id)

    def delete_media(
        self,
        input_key: str,
        asset_id: str,
    ) -> bool:
        """
        Delete a media asset, verifying the key grants access.

        Args:
            input_key: The raw key string.
            asset_id: The media asset ID.

        Returns:
            True if the asset was deleted.
        """
        # Verify the key grants access to this asset
        self._verify_key_access(input_key, asset_id)

        return self.db.delete_media_asset(asset_id)

    # ------------------------------------------------------------------
    # Bulletins (Secure Communication Boards)
    # ------------------------------------------------------------------

    def create_bulletin(
        self,
        input_key: str,
        event_id: str,
        title: str,
        body: str,
        author_id: str,
    ) -> dict:
        """
        Create a bulletin (communication board post) gated by a key.

        The body is encrypted at rest. The key must be valid and must
        have access to the specified event.

        Args:
            input_key: The raw key string.
            event_id: The event this bulletin belongs to.
            title: Bulletin title.
            body: Bulletin body content.
            author_id: Identifier of the author (e.g., @user:instance).

        Returns:
            The created bulletin metadata.
        """
        # Validate inputs
        self._validate_text(title, "title", MAX_TITLE_LENGTH)
        self._validate_text(body, "body", MAX_BODY_LENGTH)
        self._validate_text(author_id, "author_id", MAX_AUTHOR_ID_LENGTH)

        # Verify the key grants access to the event
        key_hash = self._verify_key_access(input_key, event_id)

        # Generate a unique bulletin ID
        bulletin_id = self._generate_id("bulletin")

        # Store the bulletin
        self.db.add_bulletin(
            bulletin_id=bulletin_id,
            event_id=event_id,
            key_id=key_hash,
            title=title,
            body=body,
            author_id=author_id,
        )

        return {
            "id": bulletin_id,
            "event_id": event_id,
            "title": title,
            "author_id": author_id,
        }

    def get_bulletin(
        self,
        input_key: str,
        bulletin_id: str,
    ) -> dict:
        """
        Retrieve a bulletin, verifying the key grants access.

        Args:
            input_key: The raw key string.
            bulletin_id: The bulletin ID.

        Returns:
            The bulletin including decrypted body.
        """
        # Verify the key grants access to this bulletin
        self._verify_key_access(input_key, bulletin_id)

        bulletin = self.db.get_bulletin(bulletin_id)
        if bulletin is None:
            message = "Bulletin not found"
            raise ContentAccessError(message)

        return bulletin

    def list_bulletins(
        self,
        input_key: str,
        event_id: str,
    ) -> list[dict]:
        """
        List bulletins for an event, verifying the key grants access.

        Args:
            input_key: The raw key string.
            event_id: The event to list bulletins for.

        Returns:
            List of bulletin metadata (no body content).
        """
        # Verify the key grants access to the event
        self._verify_key_access(input_key, event_id)

        return self.db.list_bulletins(event_id)

    def update_bulletin(
        self,
        input_key: str,
        bulletin_id: str,
        title: str | None = None,
        body: str | None = None,
    ) -> bool:
        """
        Update a bulletin's title and/or body, verifying the key grants access.

        Args:
            input_key: The raw key string.
            bulletin_id: The bulletin ID.
            title: Optional new title.
            body: Optional new body.

        Returns:
            True if the bulletin was updated.
        """
        # Verify the key grants access to this bulletin
        self._verify_key_access(input_key, bulletin_id)

        # Validate new values if provided
        if title is not None:
            self._validate_text(title, "title", MAX_TITLE_LENGTH)
        if body is not None:
            self._validate_text(body, "body", MAX_BODY_LENGTH)

        return self.db.update_bulletin(bulletin_id, title=title, body=body)

    def delete_bulletin(
        self,
        input_key: str,
        bulletin_id: str,
    ) -> bool:
        """
        Delete a bulletin and its comments, verifying the key grants access.

        Args:
            input_key: The raw key string.
            bulletin_id: The bulletin ID.

        Returns:
            True if the bulletin was deleted.
        """
        # Verify the key grants access to this bulletin
        self._verify_key_access(input_key, bulletin_id)

        return self.db.delete_bulletin(bulletin_id)

    # ------------------------------------------------------------------
    # Comments (Secure Communication Boards)
    # ------------------------------------------------------------------

    def post_comment(
        self,
        input_key: str,
        bulletin_id: str,
        body: str,
        author_id: str,
        parent_comment_id: str | None = None,
    ) -> dict:
        """
        Post a comment on a bulletin, verifying the key grants access.

        The comment body is encrypted at rest.

        Args:
            input_key: The raw key string.
            bulletin_id: The bulletin to comment on.
            body: Comment body content.
            author_id: Identifier of the author (e.g., @user:instance).
            parent_comment_id: Optional parent comment ID for threaded replies.

        Returns:
            The created comment metadata.
        """
        # Validate inputs
        self._validate_text(body, "body", MAX_COMMENT_LENGTH)
        self._validate_text(author_id, "author_id", MAX_AUTHOR_ID_LENGTH)

        # Verify the key grants access to this bulletin
        key_hash = self._verify_key_access(input_key, bulletin_id)

        # Generate a unique comment ID
        comment_id = self._generate_id("comment")

        # Store the comment
        self.db.add_comment(
            comment_id=comment_id,
            bulletin_id=bulletin_id,
            key_id=key_hash,
            body=body,
            author_id=author_id,
            parent_comment_id=parent_comment_id,
        )

        return {
            "id": comment_id,
            "bulletin_id": bulletin_id,
            "author_id": author_id,
        }

    def get_comments(
        self,
        input_key: str,
        bulletin_id: str,
    ) -> list[dict]:
        """
        Retrieve all comments for a bulletin, verifying the key grants access.

        Args:
            input_key: The raw key string.
            bulletin_id: The bulletin to get comments for.

        Returns:
            List of comments including decrypted bodies.
        """
        # Verify the key grants access to this bulletin
        self._verify_key_access(input_key, bulletin_id)

        return self.db.list_comments(bulletin_id)

    def delete_comment(
        self,
        input_key: str,
        comment_id: str,
    ) -> bool:
        """
        Delete a comment, verifying the key grants access.

        Args:
            input_key: The raw key string.
            comment_id: The comment ID.

        Returns:
            True if the comment was deleted.
        """
        # Verify the key grants access to this comment's bulletin
        comment = self.db.get_comment(comment_id)
        if comment is None:
            message = "Comment not found"
            raise ContentAccessError(message)

        self._verify_key_access(input_key, comment["bulletin_id"])

        return self.db.delete_comment(comment_id)
