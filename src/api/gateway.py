import logging
from typing import Any, Dict

from src.core.key_manager import KeyManager
from src.db.database_handler import DatabaseHandler

logging.basicConfig(level=logging.INFO)

class Gateway:
    """
    The primary interface for the application's API layer.
    It orchestrates interactions between logic (KeyManager) 
    and data storage (DatabaseHandler).
    """

    def __init__(self):
        self.db = DatabaseHandler()
        self.key_manager = KeyManager(db=self.db)

    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a generic incoming request to access content.
        
        Expected payload keys:
            - 'key': The user provided key string (e.g., @org:host/content)
            - 'content_id': The specific block or event ID being accessed.
        """
        input_key = request.get("key")
        content_id = request.get("content_id")

        # Input validation
        if not input_key or not isinstance(input_key, str):
            logging.error(f"Invalid key format: {input_key}")
            return {"status": "error", "message": "Invalid key format"}
        
        if not content_id or not isinstance(content_id, str):
            logging.error(f"Invalid content ID format: {content_id}")
            return {"status": "error", "message": "Invalid content ID format"}

        # 1. Logic/Federation Check
        validation_result = self.key_manager.validate_key(input_key)
        
        if validation_result["status"] != "valid":
             logging.error(f"Invalid key: {input_key}")
             return {"status": "error", "message": "Invalid key"}

        # 2. Database Retrieval
        # Check if it's a content block or an event based on requested ID
        content = self.db.get_content_block(content_id)
        if not content:
            # Fallback to checking if it's an event directly
            content = self.db.get_event(content_id)

        if not content:
            logging.error(f"Content not found: {content_id}")
            return {"status": "error", "message": "Content not found"}

        logging.info(f"Access granted for key: {input_key}, content ID: {content_id}")
        return {
            "status": "success",
            "data": content,
            "metadata": {
                "org_id": validation_result["org_id"],
                "key_hash": validation_result["hash"]
            }
        }
