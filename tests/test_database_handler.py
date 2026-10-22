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

    def test_event_organizer_name_defaults_blank(self):
        """Events without an organizer name read back as blank, not None."""
        self.db.add_event("event_ood", "title", "description", "organizer_id")
        event = self.db.get_event("event_ood")
        self.assertEqual(event["organizer_name"], "")

    def test_event_organizer_name_stored_and_read(self):
        """A provided organizer name is persisted and returned verbatim."""
        self.db.add_event(
            "event_on",
            "title",
            "description",
            "organizer_id",
            organizer_name="Cellar Collective",
        )
        event = self.db.get_event("event_on")
        self.assertEqual(event["organizer_name"], "Cellar Collective")

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

    def test_event_map_defaults_are_empty_and_on(self):
        """Events without coordinates read back with no map, switch on."""
        self.db.add_event("event_map", "title", "description", "organizer_id")
        event = self.db.get_event("event_map")
        self.assertIsNone(event["location_lat"])
        self.assertIsNone(event["location_lon"])
        self.assertTrue(event["show_map"])

    def test_event_location_geo_is_encrypted_and_round_trips(self):
        """Coordinates are encrypted at rest and decrypted for the event view."""
        self.db.add_event(
            "event_geo",
            "title",
            "description",
            "organizer_id",
            location_geo='{"lat": 40.75, "lon": -73.98}',
        )
        self.db.cursor.execute("SELECT location_geo FROM events WHERE event_id = ?", ("event_geo",))
        raw = self.db.cursor.fetchone()[0]
        self.assertNotIn("40.75", raw)
        self.assertNotIn("-73.98", raw)
        event = self.db.get_event("event_geo")
        self.assertEqual(event["location_lat"], 40.75)
        self.assertEqual(event["location_lon"], -73.98)

    def test_set_event_location_geo_and_show_map(self):
        """The map setters update coordinates and the per-event switch."""
        self.db.add_event("event_set", "title", "description", "organizer_id")
        self.db.set_event_location_geo("event_set", '{"lat": 1.5, "lon": 2.5}')
        self.db.set_event_show_map("event_set", show_map=False)
        event = self.db.get_event("event_set")
        self.assertEqual(event["location_lat"], 1.5)
        self.assertEqual(event["location_lon"], 2.5)
        self.assertFalse(event["show_map"])

    def test_malformed_location_geo_returns_no_coordinates(self):
        """A corrupt geo payload must not break the event page."""
        self.db.add_event("event_bad_geo", "title", "description", "organizer_id")
        self.db.cursor.execute(
            "UPDATE events SET location_geo = ? WHERE event_id = ?",
            (self.db._encrypt("{not json"), "event_bad_geo"),
        )
        self.db.connection.commit()
        with self.assertLogs("src.db.database_handler", level="WARNING"):
            event = self.db.get_event("event_bad_geo")
        self.assertIsNone(event["location_lat"])
        self.assertIsNone(event["location_lon"])

    def test_fresh_schema_map_column_order(self):
        """New columns live at the indices the positional guards expect."""
        columns = [row[1] for row in self.db.cursor.execute("PRAGMA table_info(events)")]
        self.assertEqual(columns[12], "organizer_name")
        self.assertEqual(columns[13], "location_geo")
        self.assertEqual(columns[14], "show_map")

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
                "organizer_name",
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

    def test_migrate_old_schema_adds_map_columns(self):
        """A pre-map database gains the geo column and the switch."""
        import sqlite3
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
            path = handle.name
        db = None
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE events (event_id TEXT PRIMARY KEY, title TEXT, "
                "description TEXT, organizer_id TEXT, location_data TEXT, "
                "created_at TEXT, mode TEXT, expires_at TEXT, "
                "rsvp_passphrase_hash TEXT, rsvp_auto_approve INTEGER, "
                "flyer_asset_id TEXT, slug TEXT, organizer_name TEXT)"
            )
            conn.execute(
                "CREATE TABLE keys (hash_key TEXT PRIMARY KEY, type TEXT, expires_at TEXT)"
            )
            conn.commit()
            conn.close()

            db = DatabaseHandler(path, organizer_key=TEST_ORGANIZER_KEY)
            event_cols = [r[1] for r in db.cursor.execute("PRAGMA table_info(events)")]
            self.assertIn("location_geo", event_cols)
            self.assertIn("show_map", event_cols)
            db.add_event(
                "e_map",
                "Legacy",
                "d",
                "o1",
                location_geo='{"lat": 3.25, "lon": -4.5}',
            )
            event = db.get_event("e_map")
            self.assertEqual(event["location_lat"], 3.25)
            self.assertEqual(event["location_lon"], -4.5)
            self.assertTrue(event["show_map"])
        finally:
            if db is not None:
                db.close()
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
