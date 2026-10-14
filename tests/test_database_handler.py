import unittest

from helpers import TEST_ORGANIZER_KEY

from src.db.database_handler import DatabaseHandler


class TestDatabaseHandler(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseHandler(":memory:", organizer_key=TEST_ORGANIZER_KEY)

    def tearDown(self):
        self.db.close()

    def test_add_and_get_key(self):
        self.db.add_key("hash_key", "key_type")
        key = self.db.get_key("hash_key")
        self.assertIsNotNone(key)
        self.assertEqual(key["id"], "hash_key")
        self.assertEqual(key["type"], "key_type")

    def test_add_and_get_content_block(self):
        self.db.add_content_block("block_id", "event_id", "key_id", "content_type", "payload")
        content = self.db.get_content_block("block_id")
        self.assertIsNotNone(content)
        self.assertEqual(content["id"], "block_id")
        self.assertEqual(content["event_id"], "event_id")
        self.assertEqual(content["payload"], "payload")

    def test_add_and_get_event(self):
        self.db.add_event("event_id", "title", "description", "organizer_id")
        event = self.db.get_event("event_id")
        self.assertIsNotNone(event)
        self.assertEqual(event["id"], "event_id")
        self.assertEqual(event["title"], "title")

    def test_content_payload_encrypted_at_rest(self):
        """Sensitive payloads must be encrypted in the database, not plaintext."""
        self.db.add_content_block("block_enc", "event_1", "key_1", "location", "40.7128,-74.0060")
        # Read raw from the database to verify it's not plaintext
        self.db.cursor.execute(
            "SELECT payload FROM content_blocks WHERE block_id = ?", ("block_enc",)
        )
        raw = self.db.cursor.fetchone()[0]
        self.assertNotIn("40.7128", raw)
        self.assertNotIn("-74.0060", raw)

    def test_event_location_encrypted_at_rest(self):
        """Event location data must be encrypted in the database."""
        self.db.add_event(
            "event_enc", "Secret Show", "desc", "org_1", location_data="40.7128,-74.0060"
        )
        self.db.cursor.execute(
            "SELECT location_data FROM events WHERE event_id = ?", ("event_enc",)
        )
        raw = self.db.cursor.fetchone()[0]
        self.assertNotIn("40.7128", raw)
        self.assertNotIn("-74.0060", raw)

    def test_revoke_key(self):
        """Revoking a key marks it as revoked."""
        self.db.add_key("hash_1", "access")
        self.assertFalse(self.db.is_key_revoked("hash_1"))
        result = self.db.revoke_key("hash_1")
        self.assertTrue(result)
        self.assertTrue(self.db.is_key_revoked("hash_1"))

    def test_revoke_nonexistent_key_returns_false(self):
        """Revoking a non-existent key returns False."""
        result = self.db.revoke_key("nonexistent")
        self.assertFalse(result)

    def test_key_content_links(self):
        """Many-to-many key↔content mapping works."""
        self.db.add_key("hash_1", "access")
        self.db.add_content_block("block_1", "event_1", "hash_1", "location", "data")
        self.db.add_content_block("block_2", "event_1", "hash_1", "contact", "info")

        content_ids = self.db.get_content_ids_for_key("hash_1")
        self.assertEqual(len(content_ids), 2)
        ids = {c["content_id"] for c in content_ids}
        self.assertEqual(ids, {"block_1", "block_2"})

        keys = self.db.get_keys_for_content("block_1")
        self.assertIn("hash_1", keys)

    def test_created_at_set_on_key(self):
        """Keys get a created_at timestamp."""
        self.db.add_key("hash_1", "access")
        key = self.db.get_key("hash_1")
        self.assertIsNotNone(key["created_at"])

    def test_owner_id_stored(self):
        """Owner identifier is stored for federation support."""
        self.db.add_key("hash_1", "access", owner_id="@org:instance")
        key = self.db.get_key("hash_1")
        self.assertEqual(key["owner_id"], "@org:instance")

    def test_missing_organizer_key_raises(self):
        """DatabaseHandler must fail-secure without a organizer key."""
        import os

        old = os.environ.get("GATEKEYP_ORGANIZER_KEY")
        os.environ.pop("GATEKEYP_ORGANIZER_KEY", None)
        try:
            with self.assertRaises(ValueError):
                DatabaseHandler(":memory:")
        finally:
            if old:
                os.environ["GATEKEYP_ORGANIZER_KEY"] = old


class TestSchemaMigration(unittest.TestCase):
    """Opening a pre-migration database applies additive column migrations."""

    def test_migrate_old_schema_adds_columns_without_data_loss(self):
        import sqlite3
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
            path = handle.name
        db = None
        try:
            # Reproduce an old schema lacking every column added in Phase A/B.
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE events (event_id TEXT PRIMARY KEY, title TEXT, "
                "description TEXT, organizer_id TEXT)"
            )
            conn.execute(
                "CREATE TABLE keys (hash_key TEXT PRIMARY KEY, type TEXT, expires_at TEXT)"
            )
            conn.execute(
                "INSERT INTO events (event_id, title, description, organizer_id) "
                "VALUES ('e1', 'Legacy', 'd', 'o1')"
            )
            conn.commit()
            conn.close()

            db = DatabaseHandler(path, organizer_key=TEST_ORGANIZER_KEY)
            event_cols = {r[1] for r in db.cursor.execute("PRAGMA table_info(events)")}
            key_cols = {r[1] for r in db.cursor.execute("PRAGMA table_info(keys)")}

            for col in (
                "mode",
                "expires_at",
                "rsvp_passphrase_hash",
                "rsvp_auto_approve",
                "flyer_asset_id",
                "slug",
                "location_data",
            ):
                self.assertIn(col, event_cols)
            for col in ("created_at", "revoked", "revoked_at", "owner_id", "rsvp_id"):
                self.assertIn(col, key_cols)
            # The human-readable slug index is created during migration.
            index = db.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_events_slug'"
            ).fetchone()
            self.assertIsNotNone(index)
            # The pre-existing row survives the migration intact.
            row = db.cursor.execute("SELECT title FROM events WHERE event_id='e1'").fetchone()
            self.assertEqual(row[0], "Legacy")
        finally:
            if db is not None:
                db.close()
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
