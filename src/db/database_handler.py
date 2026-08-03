# Copyright (c) 2026 Gatekeyp contributors

import os
import sqlite3
from datetime import UTC, datetime

from cryptography.fernet import Fernet


class MissingMasterKeyError(ValueError):
    """Raised when no master key is available for encryption-at-rest."""

    def __init__(self) -> None:
        super().__init__(
            "GATEKEYP_MASTER_KEY environment variable must be set "
            "for encryption-at-rest. Refusing to start with unencrypted storage."
        )


class DecryptionError(ValueError):
    """Raised when stored data cannot be decrypted."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DatabaseHandler:
    """
    Handles interactions with the database for Keys, Events, Content Blocks,
    Media Assets, Bulletins, and Comments.
    Implements encryption-at-rest for sensitive payloads (Fernet/AES-GCM).
    """

    def __init__(self, db_path: str = "keys.db", master_key: str | None = None) -> None:
        """
        Initialize the database handler.

        Fail-secure: requires a master key for encryption-at-rest.
        The master key can be provided directly or via the GATEKEYP_MASTER_KEY
        environment variable. If neither is available, the application refuses
        to start rather than running with unencrypted storage.

        Args:
            db_path: Path to the SQLite database file. Use ':memory:' for tests.
            master_key: Fernet-compatible master key (base64-encoded 32-byte key).
                        If None, reads from GATEKEYP_MASTER_KEY env var.
        """
        if master_key is None:
            master_key = os.environ.get("GATEKEYP_MASTER_KEY")
        if master_key is None:
            raise MissingMasterKeyError
        self.fernet = Fernet(master_key.encode() if isinstance(master_key, str) else master_key)
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        self._initialize_tables()
        self._migrate_schema()

    def _initialize_tables(self) -> None:
        """Create all tables if they don't exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                hash_key TEXT PRIMARY KEY,
                type TEXT,
                expires_at TEXT,
                created_at TEXT,
                revoked INTEGER DEFAULT 0,
                revoked_at TEXT,
                owner_id TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_blocks (
                block_id TEXT PRIMARY KEY,
                event_id TEXT,
                key_id TEXT,
                content_type TEXT,
                payload TEXT,
                created_at TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                organizer_id TEXT,
                location_data TEXT,
                created_at TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS key_content_links (
                key_hash TEXT,
                content_id TEXT,
                content_type TEXT,
                PRIMARY KEY (key_hash, content_id, content_type)
            )
        """)
        # Phase 2: Media assets (flyers, images, documents)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_assets (
                asset_id TEXT PRIMARY KEY,
                event_id TEXT,
                key_id TEXT,
                filename TEXT,
                mime_type TEXT,
                size_bytes INTEGER,
                data BLOB,
                created_at TEXT
            )
        """)
        # Phase 2: Secure communication boards (bulletins)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS bulletins (
                bulletin_id TEXT PRIMARY KEY,
                event_id TEXT,
                key_id TEXT,
                title TEXT,
                body TEXT,
                author_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        # Phase 2: Comments on bulletins
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                comment_id TEXT PRIMARY KEY,
                bulletin_id TEXT,
                key_id TEXT,
                body TEXT,
                author_id TEXT,
                created_at TEXT,
                parent_comment_id TEXT
            )
        """)
        self.connection.commit()

    def _migrate_schema(self) -> None:
        """Add missing columns to existing tables (for backward compatibility)."""
        # Check and add missing columns to 'keys'
        self._ensure_column("keys", "created_at", "TEXT")
        self._ensure_column("keys", "revoked", "INTEGER DEFAULT 0")
        self._ensure_column("keys", "revoked_at", "TEXT")
        self._ensure_column("keys", "owner_id", "TEXT")

        # Check and add missing columns to 'content_blocks'
        self._ensure_column("content_blocks", "created_at", "TEXT")

        # Check and add missing columns to 'events'
        self._ensure_column("events", "location_data", "TEXT")
        self._ensure_column("events", "created_at", "TEXT")

        # Phase 2: Check and add missing columns to 'media_assets'
        self._ensure_column("media_assets", "created_at", "TEXT")

        # Phase 2: Check and add missing columns to 'bulletins'
        self._ensure_column("bulletins", "updated_at", "TEXT")

        # Phase 2: Check and add missing columns to 'comments'
        self._ensure_column("comments", "parent_comment_id", "TEXT")

        self.connection.commit()

    def _ensure_column(self, table: str, column: str, col_type: str) -> None:
        """Add a column to a table if it doesn't already exist."""
        self.cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in self.cursor.fetchall()]
        if column not in columns:
            self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a sensitive string for storage at rest."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a sensitive string retrieved from storage."""
        return self.fernet.decrypt(ciphertext.encode()).decode()

    def _encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt sensitive binary data for storage at rest."""
        return self.fernet.encrypt(data)

    def _decrypt_bytes(self, ciphertext: bytes) -> bytes:
        """Decrypt sensitive binary data retrieved from storage."""
        return self.fernet.decrypt(ciphertext)

    def _now_iso(self) -> str:
        """Return current UTC time in ISO format."""
        return datetime.now(UTC).isoformat()

    # ------------------------------------------------------------------
    # Keys
    # ------------------------------------------------------------------

    def get_key(self, hash_key: str) -> dict | None:
        """Retrieve a key record by its hash."""
        self.cursor.execute("SELECT * FROM keys WHERE hash_key = ?", (hash_key,))
        result = self.cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "hash_key": result[0],
                "type": result[1],
                "expires_at": result[2],
                "created_at": result[3],
                "revoked": bool(result[4]),
                "revoked_at": result[5],
                "owner_id": result[6],
            }
        return None

    def add_key(
        self,
        hash_key: str,
        key_type: str,
        expires_at: str | None = None,
        owner_id: str | None = None,
    ) -> None:
        """Add a new key record."""
        now = self._now_iso()
        self.cursor.execute(
            """
            INSERT INTO keys (hash_key, type, expires_at, created_at, revoked, revoked_at, owner_id)
            VALUES (?, ?, ?, ?, 0, NULL, ?)
        """,
            (hash_key, key_type, expires_at, now, owner_id),
        )
        self.connection.commit()

    def revoke_key(self, hash_key: str) -> bool:
        """Mark a key as revoked. Returns True if a key was revoked."""
        now = self._now_iso()
        self.cursor.execute(
            """
            UPDATE keys SET revoked = 1, revoked_at = ? WHERE hash_key = ? AND revoked = 0
        """,
            (now, hash_key),
        )
        self.connection.commit()
        return self.cursor.rowcount > 0

    def is_key_revoked(self, hash_key: str) -> bool:
        """Check if a key has been revoked."""
        self.cursor.execute("SELECT revoked FROM keys WHERE hash_key = ?", (hash_key,))
        result = self.cursor.fetchone()
        return bool(result and result[0])

    def list_keys(self) -> list[dict]:
        """List all keys (for admin/rotation workflows)."""
        self.cursor.execute("SELECT * FROM keys")
        results = self.cursor.fetchall()
        return [
            {
                "id": r[0],
                "hash_key": r[0],
                "type": r[1],
                "expires_at": r[2],
                "created_at": r[3],
                "revoked": bool(r[4]),
                "revoked_at": r[5],
                "owner_id": r[6],
            }
            for r in results
        ]

    # ------------------------------------------------------------------
    # Content Blocks
    # ------------------------------------------------------------------

    def get_content_block(self, block_id: str) -> dict | None:
        """Retrieve a content block, decrypting the payload."""
        self.cursor.execute("SELECT * FROM content_blocks WHERE block_id = ?", (block_id,))
        result = self.cursor.fetchone()
        if result:
            payload = result[4]
            try:
                payload = self._decrypt(payload)
            except (ValueError, TypeError) as err:
                # If decryption fails, the payload may be legacy plaintext.
                # In a hardened system, we treat this as an error.
                message = f"Failed to decrypt payload for content block {block_id}"
                raise DecryptionError(message) from err
            return {
                "id": result[0],
                "event_id": result[1],
                "key_id": result[2],
                "content_type": result[3],
                "payload": payload,
                "created_at": result[5],
            }
        return None

    def add_content_block(
        self,
        block_id: str,
        event_id: str,
        key_id: str,
        content_type: str,
        payload: str,
    ) -> None:
        """Add a content block, encrypting the payload at rest."""
        now = self._now_iso()
        encrypted_payload = self._encrypt(payload)
        self.cursor.execute(
            """
            INSERT INTO content_blocks
                (block_id, event_id, key_id, content_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (block_id, event_id, key_id, content_type, encrypted_payload, now),
        )
        # Also create a key_content_link for the many-to-many mapping
        self.add_key_content_link(key_id, block_id, "block")
        self.connection.commit()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def get_event(self, event_id: str) -> dict | None:
        """Retrieve an event, decrypting location_data if present."""
        self.cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
        result = self.cursor.fetchone()
        if result:
            location_data = result[4]
            if location_data:
                try:
                    location_data = self._decrypt(location_data)
                except (ValueError, TypeError) as err:
                    message = f"Failed to decrypt location_data for event {event_id}"
                    raise DecryptionError(message) from err
            return {
                "id": result[0],
                "title": result[1],
                "description": result[2],
                "organizer_id": result[3],
                "location_data": location_data,
                "created_at": result[5],
            }
        return None

    def add_event(
        self,
        event_id: str,
        title: str,
        description: str,
        organizer_id: str,
        location_data: str | None = None,
    ) -> None:
        """Add an event, encrypting location_data at rest."""
        now = self._now_iso()
        encrypted_location = self._encrypt(location_data) if location_data else None
        self.cursor.execute(
            """
            INSERT INTO events
                (event_id, title, description, organizer_id, location_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (event_id, title, description, organizer_id, encrypted_location, now),
        )
        self.connection.commit()

    # ------------------------------------------------------------------
    # Key ↔ Content Links (many-to-many)
    # ------------------------------------------------------------------

    def add_key_content_link(self, key_hash: str, content_id: str, content_type: str) -> None:
        """Create a many-to-many link between a key and a content item."""
        self.cursor.execute(
            """
            INSERT OR IGNORE INTO key_content_links (key_hash, content_id, content_type)
            VALUES (?, ?, ?)
        """,
            (key_hash, content_id, content_type),
        )
        self.connection.commit()

    def get_content_ids_for_key(self, key_hash: str) -> list[dict]:
        """Get all content IDs linked to a given key hash."""
        self.cursor.execute(
            """
            SELECT content_id, content_type FROM key_content_links WHERE key_hash = ?
        """,
            (key_hash,),
        )
        results = self.cursor.fetchall()
        return [{"content_id": r[0], "content_type": r[1]} for r in results]

    def get_keys_for_content(self, content_id: str) -> list[str]:
        """Get all key hashes linked to a given content item."""
        self.cursor.execute(
            """
            SELECT key_hash FROM key_content_links WHERE content_id = ?
        """,
            (content_id,),
        )
        results = self.cursor.fetchall()
        return [r[0] for r in results]

    # ------------------------------------------------------------------
    # Media Assets (Phase 2)
    # ------------------------------------------------------------------

    def add_media_asset(
        self,
        asset_id: str,
        event_id: str,
        key_id: str,
        filename: str,
        mime_type: str,
        data: bytes,
    ) -> None:
        """
        Add a media asset (flyer, image, document), encrypting the binary
        data at rest. Also creates a key_content_link for key-gated access.
        """
        now = self._now_iso()
        encrypted_data = self._encrypt_bytes(data)
        self.cursor.execute(
            """
            INSERT INTO media_assets
                (asset_id, event_id, key_id, filename, mime_type, size_bytes, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (asset_id, event_id, key_id, filename, mime_type, len(data), encrypted_data, now),
        )
        self.add_key_content_link(key_id, asset_id, "media")
        self.connection.commit()

    def get_media_asset(self, asset_id: str) -> dict | None:
        """Retrieve a media asset, decrypting the binary data."""
        self.cursor.execute("SELECT * FROM media_assets WHERE asset_id = ?", (asset_id,))
        result = self.cursor.fetchone()
        if result:
            try:
                data = self._decrypt_bytes(result[6])
            except (ValueError, TypeError) as err:
                message = f"Failed to decrypt media asset {asset_id}"
                raise DecryptionError(message) from err
            return {
                "id": result[0],
                "event_id": result[1],
                "key_id": result[2],
                "filename": result[3],
                "mime_type": result[4],
                "size_bytes": result[5],
                "data": data,
                "created_at": result[7],
            }
        return None

    def list_media_assets(self, event_id: str | None = None) -> list[dict]:
        """List media assets, optionally filtered by event. Does not return binary data."""
        if event_id:
            self.cursor.execute("SELECT * FROM media_assets WHERE event_id = ?", (event_id,))
        else:
            self.cursor.execute("SELECT * FROM media_assets")
        results = self.cursor.fetchall()
        return [
            {
                "id": r[0],
                "event_id": r[1],
                "key_id": r[2],
                "filename": r[3],
                "mime_type": r[4],
                "size_bytes": r[5],
                "created_at": r[7],
            }
            for r in results
        ]

    def delete_media_asset(self, asset_id: str) -> bool:
        """Delete a media asset. Returns True if an asset was deleted."""
        self.cursor.execute("DELETE FROM media_assets WHERE asset_id = ?", (asset_id,))
        self.connection.commit()
        return self.cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Bulletins (Phase 2 - Secure Communication Boards)
    # ------------------------------------------------------------------

    def add_bulletin(
        self,
        bulletin_id: str,
        event_id: str,
        key_id: str,
        title: str,
        body: str,
        author_id: str,
    ) -> None:
        """
        Add a bulletin (communication board post), encrypting the body at rest.
        Also creates a key_content_link for key-gated access.
        """
        now = self._now_iso()
        encrypted_body = self._encrypt(body)
        self.cursor.execute(
            """
            INSERT INTO bulletins
                (bulletin_id, event_id, key_id, title, body, author_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (bulletin_id, event_id, key_id, title, encrypted_body, author_id, now, now),
        )
        self.add_key_content_link(key_id, bulletin_id, "bulletin")
        self.connection.commit()

    def get_bulletin(self, bulletin_id: str) -> dict | None:
        """Retrieve a bulletin, decrypting the body."""
        self.cursor.execute("SELECT * FROM bulletins WHERE bulletin_id = ?", (bulletin_id,))
        result = self.cursor.fetchone()
        if result:
            try:
                body = self._decrypt(result[4])
            except (ValueError, TypeError) as err:
                message = f"Failed to decrypt bulletin {bulletin_id}"
                raise DecryptionError(message) from err
            return {
                "id": result[0],
                "event_id": result[1],
                "key_id": result[2],
                "title": result[3],
                "body": body,
                "author_id": result[5],
                "created_at": result[6],
                "updated_at": result[7],
            }
        return None

    def list_bulletins(self, event_id: str | None = None) -> list[dict]:
        """List bulletins, optionally filtered by event. Does not return body content."""
        if event_id:
            self.cursor.execute(
                "SELECT * FROM bulletins WHERE event_id = ? ORDER BY created_at DESC",
                (event_id,),
            )
        else:
            self.cursor.execute("SELECT * FROM bulletins ORDER BY created_at DESC")
        results = self.cursor.fetchall()
        return [
            {
                "id": r[0],
                "event_id": r[1],
                "key_id": r[2],
                "title": r[3],
                "author_id": r[5],
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in results
        ]

    def update_bulletin(
        self, bulletin_id: str, title: str | None = None, body: str | None = None
    ) -> bool:
        """Update a bulletin's title and/or body. Returns True if updated."""
        now = self._now_iso()

        if title is not None and body is not None:
            self.cursor.execute(
                "UPDATE bulletins SET title = ?, body = ?, updated_at = ? WHERE bulletin_id = ?",
                (title, self._encrypt(body), now, bulletin_id),
            )
        elif title is not None:
            self.cursor.execute(
                "UPDATE bulletins SET title = ?, updated_at = ? WHERE bulletin_id = ?",
                (title, now, bulletin_id),
            )
        elif body is not None:
            self.cursor.execute(
                "UPDATE bulletins SET body = ?, updated_at = ? WHERE bulletin_id = ?",
                (self._encrypt(body), now, bulletin_id),
            )
        else:
            return False

        self.connection.commit()
        return self.cursor.rowcount > 0

    def delete_bulletin(self, bulletin_id: str) -> bool:
        """Delete a bulletin and its comments. Returns True if a bulletin was deleted."""
        # Delete associated comments first
        self.cursor.execute("DELETE FROM comments WHERE bulletin_id = ?", (bulletin_id,))
        # Delete the bulletin
        self.cursor.execute("DELETE FROM bulletins WHERE bulletin_id = ?", (bulletin_id,))
        self.connection.commit()
        return self.cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Comments (Phase 2 - Secure Communication Boards)
    # ------------------------------------------------------------------

    def add_comment(
        self,
        comment_id: str,
        bulletin_id: str,
        key_id: str,
        body: str,
        author_id: str,
        parent_comment_id: str | None = None,
    ) -> None:
        """Add a comment to a bulletin, encrypting the body at rest."""
        now = self._now_iso()
        encrypted_body = self._encrypt(body)
        self.cursor.execute(
            """
            INSERT INTO comments
                (comment_id, bulletin_id, key_id, body, author_id, created_at, parent_comment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (comment_id, bulletin_id, key_id, encrypted_body, author_id, now, parent_comment_id),
        )
        self.connection.commit()

    def get_comment(self, comment_id: str) -> dict | None:
        """Retrieve a comment, decrypting the body."""
        self.cursor.execute("SELECT * FROM comments WHERE comment_id = ?", (comment_id,))
        result = self.cursor.fetchone()
        if result:
            try:
                body = self._decrypt(result[3])
            except (ValueError, TypeError) as err:
                message = f"Failed to decrypt comment {comment_id}"
                raise DecryptionError(message) from err
            return {
                "id": result[0],
                "bulletin_id": result[1],
                "key_id": result[2],
                "body": body,
                "author_id": result[4],
                "created_at": result[5],
                "parent_comment_id": result[6],
            }
        return None

    def list_comments(self, bulletin_id: str) -> list[dict]:
        """List all comments for a bulletin, decrypting bodies."""
        self.cursor.execute(
            "SELECT * FROM comments WHERE bulletin_id = ? ORDER BY created_at ASC",
            (bulletin_id,),
        )
        results = self.cursor.fetchall()
        comments: list[dict] = []
        for r in results:
            try:
                body = self._decrypt(r[3])
            except (ValueError, TypeError) as err:
                message = f"Failed to decrypt comment {r[0]}"
                raise DecryptionError(message) from err
            comments.append(
                {
                    "id": r[0],
                    "bulletin_id": r[1],
                    "key_id": r[2],
                    "body": body,
                    "author_id": r[4],
                    "created_at": r[5],
                    "parent_comment_id": r[6],
                }
            )
        return comments

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment. Returns True if a comment was deleted."""
        self.cursor.execute("DELETE FROM comments WHERE comment_id = ?", (comment_id,))
        self.connection.commit()
        return self.cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()
