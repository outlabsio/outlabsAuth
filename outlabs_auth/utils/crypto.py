"""Encryption helpers for secrets stored at rest."""

from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from outlabs_auth.core.exceptions import ConfigurationError, TokenInvalidError


class FernetCipher:
    """Encrypt and decrypt string values with a configured Fernet key."""

    def __init__(self, key: str):
        try:
            self._fernet = Fernet(key.encode())
        except Exception as exc:
            raise ConfigurationError("Invalid oauth_token_encryption_key") from exc

    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise TokenInvalidError(
                message="Stored OAuth token could not be decrypted",
                details={"reason": "invalid_encrypted_token"},
            ) from exc
