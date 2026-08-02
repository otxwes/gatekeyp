import unittest
from src.core.key_manager import KeyManager

class TestKeyManager(unittest.TestCase):
    def test_generate_key(self):
        key_manager = KeyManager()
        key1 = key_manager.generate_key()
        key2 = key_manager.generate_key()
        self.assertEqual(len(key1), 64)  # 32 bytes * 2 hex characters per byte
        self.assertNotEqual(key1, key2)

    def test_hash_key(self):
        key_manager = KeyManager()
        original_key = "test_key"
        hashed_key = key_manager.hash_key(original_key)
        self.assertEqual(len(hashed_key), 64)  # SHA-256 hash length
        self.assertNotEqual(original_key, hashed_key)

    def test_resolve_federation_prefix(self):
        key_manager = KeyManager()
        identity, local_key = key_manager.resolve_federation_prefix("@example:org/key_content")
        self.assertEqual(identity, "example")
        self.assertEqual(local_key, "key_content")

        identity, local_key = key_manager.resolve_federation_prefix("local:key_content")
        self.assertEqual(identity, "local")
        # The prefix 'local:' is removed, leaving just the key content
        self.assertEqual(local_key, "key_content")

if __name__ == '__main__':
    unittest.main()