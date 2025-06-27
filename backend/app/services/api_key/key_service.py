# backend/app/services/key_service.py

import secrets
import hashlib

# Define a constant for the number of random bytes to generate for the key.
# 32 bytes will result in a 64-character hex string, which is very secure.
KEY_NUM_BYTES = 32


def generate_api_key(prefix: str) -> str:
    """Generates a new cryptographically secure API key with a given prefix.

    The key consists of a prefix and a random hexadecimal string. This raw key
    should only be shown to the user once upon creation.

    Args:
        prefix: A non-secret prefix to identify the key's purpose (e.g., 'sk_sheets').
                It should not end with an underscore.

    Returns:
        The full, raw API key string (e.g., 'sk_sheets_xxxxxxxx...').
    """
    if not prefix or prefix.endswith("_"):
        raise ValueError("Prefix cannot be empty or end with an underscore.")

    random_part = secrets.token_hex(KEY_NUM_BYTES)
    return f"{prefix}_{random_part}"


def hash_api_key(raw_key: str) -> str:
    """Hashes a raw API key using the SHA-256 algorithm.

    This function creates a one-way hash of the API key. The resulting hash is
    what should be stored in the database for security comparisons, never the
    raw key itself.

    Args:
        raw_key: The full, unhashed API key string.

    Returns:
        The SHA-256 hash of the key as a hexadecimal digest string.
    """
    # The key must be encoded to bytes before hashing.
    return hashlib.sha256(raw_key.encode()).hexdigest()
