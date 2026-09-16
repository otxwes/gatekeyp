import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Generate a valid Fernet key (32-byte base64-encoded) for tests
from cryptography.fernet import Fernet

TEST_ORGANIZER_KEY = Fernet.generate_key().decode()
TEST_HMAC_SECRET = "test-hmac-secret-for-unit-tests-only-1234567890"

# Set required environment variables for tests
os.environ.setdefault("GATEKEYP_ORGANIZER_KEY", TEST_ORGANIZER_KEY)
os.environ.setdefault("GATEKEYP_HMAC_SECRET", TEST_HMAC_SECRET)
