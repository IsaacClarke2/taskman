"""
Cryptography utilities for encrypting/decrypting credentials.
"""

import json
import logging

from cryptography.fernet import Fernet, InvalidToken

from api.config import get_settings

logger = logging.getLogger(__name__)


def get_fernet() -> Fernet:
    """Get Fernet instance with encryption key from settings."""
    settings = get_settings()
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set")
    return Fernet(settings.encryption_key.encode())


def encrypt_credentials(credentials: dict) -> str:
    """
    Encrypt credentials dictionary for storage in database.

    Args:
        credentials: Dictionary containing tokens/passwords.

    Returns:
        Base64-encoded encrypted string.
    """
    f = get_fernet()
    json_bytes = json.dumps(credentials).encode("utf-8")
    encrypted = f.encrypt(json_bytes)
    return encrypted.decode("utf-8")


def decrypt_credentials(encrypted: str) -> dict:
    """
    Decrypt credentials from database.

    Args:
        encrypted: Base64-encoded encrypted string.

    Returns:
        Decrypted credentials dictionary.

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data).
    """
    try:
        f = get_fernet()
        decrypted = f.decrypt(encrypted.encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))
    except InvalidToken:
        logger.error("Failed to decrypt credentials - invalid token")
        raise
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise
