import hashlib
import secrets
from datetime import datetime
from typing import Optional, List

from src.db.database_handler import DatabaseHandler

# Constants for Key Types
KEY_TYPE_ACCESS = "access"
KEY_TYPE_MASTER = "master"

class KeyManager:
    """
    Core logic for handling and validating keys within Gatekeyp.
    """

    def __init__(self, db: Optional[DatabaseHandler] = None):
        """
        Optionally accept a shared DatabaseHandler instance.
        If not provided, a default one is created.
        """
        self.db = db if db is not None else DatabaseHandler()

    @staticmethod
    def generate_key(length: int = 32) -> str:
        """
        Generates a cryptographically secure, opaque key as a hex string.
        """
        return secrets.token_hex(length)

    @staticmethod
    def hash_key(input_key: str) -> str:
        """
        Hashes an input key using SHA-256 to ensure that the raw 
        key is never stored directly in a way that's easily retrievable.
        """
        return hashlib.sha256(input_key.encode()).hexdigest()

    @staticmethod
    def resolve_federation_prefix(raw_key: str) -> tuple[str, str]:
        """
        Parses the key to determine if it belongs to a specific 
        instance or a federated host.
        Example format: @org_name:host_identifier/key_content
        """
        if "@" in raw_key:
            prefix_end_index = raw_key.find(":")
            if prefix_end_index != -1:
                identity = raw_key[1:prefix_end_index]
                local_key_start_index = raw_key.find("/", prefix_end_index)
                if local_key_start_index != -1:
                    local_key = raw_key[local_key_start_index + 1:]
                else:
                    local_key = raw_key[prefix_end_index + 1:]
                return identity, local_key
        elif raw_key.startswith("local:"):
            local_key = raw_key.split(":")[1]
            return "local", local_key
        raise ValueError("Invalid key format")

    def validate_key(self, input_key: str) -> dict:
        """
        Validates a provided key and returns information about the 
        associated content.
        """
        # In a real implementation, this would interact with the database (src/db)
        # For now, it validates format and extracts federation info.
        
        org_id, local_key = self.resolve_federation_prefix(input_key)
        hashed = self.hash_key(local_key)
        
        key_info = self.db.get_key(hashed)
        
        if not key_info:
            return {"status": "invalid", "message": "Key does not exist"}
        
        expires_at = key_info.get("expires_at")
        current_time = datetime.now()
        
        if expires_at and current_time > datetime.fromisoformat(expires_at):
            return {"status": "invalid", "message": "Key has expired"}
        
        return {
            "status": "valid",
            "org_id": org_id,
            "hash": hashed,
            "expires_at": expires_at
        }