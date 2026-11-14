"""Authenticated encryption for provider API credentials.

The encryption key is supplied by deployment configuration and is never
stored in the database. A missing or malformed key fails closed.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionError(RuntimeError):
    """Raised when credentials cannot be safely encrypted or decrypted."""


def _fernet() -> Fernet:
    key = os.getenv("PROVIDER_CREDENTIALS_ENCRYPTION_KEY", "").strip()
    if not key:
        raise CredentialEncryptionError(
            "Provider credential encryption is not configured"
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        raise CredentialEncryptionError(
            "Provider credential encryption key is invalid"
        ) from None


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key using the deployment-managed Fernet key."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise CredentialEncryptionError("API key must not be empty")
    try:
        return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")
    except CredentialEncryptionError:
        raise
    except Exception:
        raise CredentialEncryptionError("Could not encrypt provider credential") from None


def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypt an API key; never return ciphertext as a fallback."""
    if not encrypted_api_key:
        raise CredentialEncryptionError("Encrypted provider credential is missing")
    try:
        return _fernet().decrypt(encrypted_api_key.encode("ascii")).decode("utf-8")
    except CredentialEncryptionError:
        raise
    except (InvalidToken, ValueError, UnicodeEncodeError, UnicodeDecodeError):
        raise CredentialEncryptionError(
            "Provider credential could not be decrypted"
        ) from None
