from typing import Optional, Dict
import sqlite3

class DatabaseHandler:
    """
    Handles interactions with the database for 
    Keys, Events, and Content Blocks.
    """

    def __init__(self, db_path: str = 'keys.db'):
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        self._initialize_tables()

    def _initialize_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                hash_key TEXT PRIMARY KEY,
                type TEXT,
                expires_at TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_blocks (
                block_id TEXT PRIMARY KEY,
                event_id TEXT,
                key_id TEXT,
                content_type TEXT,
                payload TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                organizer_id TEXT
            )
        ''')
        self.connection.commit()

    def get_key(self, hash_key: str) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM keys WHERE hash_key = ?", (hash_key,))
        result = self.cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "hash_key": result[0],
                "type": result[1],
                "expires_at": result[2]
            }
        return None

    def add_key(self, entry_id: str, hash_key: str, key_type: str, expires_at: Optional[str] = None):
        self.cursor.execute('''
            INSERT INTO keys (hash_key, type, expires_at) VALUES (?, ?, ?)
        ''', (hash_key, key_type, expires_at))
        self.connection.commit()

    def get_content_block(self, block_id: str) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM content_blocks WHERE block_id = ?", (block_id,))
        result = self.cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "event_id": result[1],
                "key_id": result[2],
                "content_type": result[3],
                "payload": result[4]
            }
        return None

    def add_content_block(self, block_id: str, event_id: str, key_id: str, 
                            content_type: str, payload: str):
        self.cursor.execute('''
            INSERT INTO content_blocks (block_id, event_id, key_id, 
                                        content_type, payload) VALUES (?, ?, ?, ?, ?)
        ''', (block_id, event_id, key_id, content_type, payload))
        self.connection.commit()

    def get_event(self, event_id: str) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
        result = self.cursor.fetchone()
        if result:
            return {
                "id": result[0],
                "title": result[1],
                "description": result[2],
                "organizer_id": result[3]
            }
        return None

    def add_event(self, event_id: str, title: str, description: str, organizer_id: str):
        self.cursor.execute('''
            INSERT INTO events (event_id, title, description, 
                                 organizer_id) VALUES (?, ?, ?, ?)
        ''', (event_id, title, description, organizer_id))
        self.connection.commit()

    def close(self):
        self.connection.close()