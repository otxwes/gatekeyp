import unittest
from src.db.database_handler import DatabaseHandler

class TestDatabaseHandler(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseHandler(":memory:")

    def test_add_and_get_key(self):
        self.db.add_key("entry_id", "hash_key", "key_type")
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

    def test_add_and_get_event(self):
        self.db.add_event("event_id", "title", "description", "organizer_id")
        event = self.db.get_event("event_id")
        self.assertIsNotNone(event)
        self.assertEqual(event["id"], "event_id")
        self.assertEqual(event["title"], "title")

if __name__ == '__main__':
    unittest.main()