import base64
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from app.config import get_settings, Settings

settings: Settings = get_settings()


try:
    # Initialize Fernet with the SECRET_KEY_FOR_ENCRYPTION
    secret_key = settings.SECRET_KEY_FOR_ENCRYPTION.encode()
    if len(secret_key) != 44:
        raise ValueError(
            "SECRET_KEY_FOR_ENCRYPTION must be a 44-byte Base64 encoded key."
        )
    fernet = Fernet(secret_key)  # Use the key directly as Fernet handles the encoding.
    logger.info("Fernet cipher initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Fernet: {e}", exc_info=True)
    raise


def encrypt_logical_token(token: str) -> bytes:
    """Encrypts the logical token."""
    try:
        encrypted_token = fernet.encrypt(token.encode())
        logger.debug(f"Token encrypted successfully.")
        return encrypted_token
    except Exception as e:
        logger.exception(f"Error during encryption: {e}", exc_info=True)
        raise


def decrypt_logical_token(encrypted_token: bytes) -> str:
    """Decrypts the logical token."""
    try:
        decrypted_token = fernet.decrypt(encrypted_token).decode()
        logger.debug(f"Token decrypted successfully.")
        return decrypted_token
    except InvalidToken as e:
        logger.error(f"Token is invalid: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error during decryption: {e}", exc_info=True)
        raise
