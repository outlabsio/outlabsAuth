"""
Password hashing and validation utilities

Uses pwdlib with Argon2id as the primary hasher and bcrypt compatibility
for legacy hashes.
"""

import asyncio
import re
from typing import Optional

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from outlabs_auth.core.exceptions import InvalidPasswordError


# Primary hasher is Argon2id; bcrypt remains enabled for legacy hash verify.
# Parameters default to OWASP 2023 minimums (m=19 MiB, t=2, p=1) — secure and
# ~3x faster than pwdlib's stock defaults. Override via configure_argon2() at
# library init (AuthConfig.argon2_* fields).
password_hasher = PasswordHash(
    (Argon2Hasher(time_cost=2, memory_cost=19456, parallelism=1), BcryptHasher())
)


def configure_argon2(time_cost: int, memory_cost_kib: int, parallelism: int) -> None:
    """Rebuild the module-level password hasher with custom Argon2id params.

    Called by OutlabsAuth during initialization so the hash cost is driven
    by AuthConfig rather than hard-coded. Bcrypt stays enabled for verifying
    legacy hashes.
    """
    global password_hasher
    password_hasher = PasswordHash(
        (
            Argon2Hasher(
                time_cost=time_cost,
                memory_cost=memory_cost_kib,
                parallelism=parallelism,
            ),
            BcryptHasher(),
        )
    )


def hash_password(password: str) -> str:
    """
    Hash a password using the current hasher (Argon2id).

    Args:
        password: Plain text password

    Returns:
        str: Hashed password

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> verify_password("MyPassword123!", hashed)
        True
    """
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash (Argon2id or legacy bcrypt)

    Returns:
        bool: True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> verify_password("MyPassword123!", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    try:
        return password_hasher.verify(plain_password, hashed_password)
    except PwdlibError:
        return False


def verify_and_upgrade_password(plain_password: str, hashed_password: str) -> tuple[bool, Optional[str]]:
    """
    Verify password and return an upgraded hash when legacy algorithms are used.

    Returns:
        tuple[bool, Optional[str]]: (is_valid, upgraded_hash)
        - is_valid=False means verification failed
        - upgraded_hash is None when no rehash is needed
    """
    try:
        return password_hasher.verify_and_update(plain_password, hashed_password)
    except PwdlibError:
        return False, None


# Async variants — offload CPU-bound Argon2 work to a thread so the event loop
# stays free for other requests. Under concurrent logins this is the difference
# between serialized and parallel hashing; see benchmarks/bench_login.py.

async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)


async def verify_and_upgrade_password_async(
    plain_password: str, hashed_password: str
) -> tuple[bool, Optional[str]]:
    return await asyncio.to_thread(verify_and_upgrade_password, plain_password, hashed_password)


def validate_password_strength(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special_char: bool = True,
) -> tuple[bool, Optional[str]]:
    """
    Validate password meets strength requirements.

    Args:
        password: Password to validate
        min_length: Minimum password length
        require_uppercase: Require at least one uppercase letter
        require_lowercase: Require at least one lowercase letter
        require_digit: Require at least one digit
        require_special_char: Require at least one special character

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)

    Example:
        >>> validate_password_strength("weak")
        (False, "Password must be at least 8 characters long")
        >>> validate_password_strength("StrongPass123!")
        (True, None)
    """
    # Check minimum length
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"

    # Check uppercase
    if require_uppercase and not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    # Check lowercase
    if require_lowercase and not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    # Check digit
    if require_digit and not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    # Check special character
    if require_special_char and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"

    return True, None


def validate_password_with_config(password: str, config) -> None:
    """
    Validate password using configuration settings.

    Args:
        password: Password to validate
        config: AuthConfig instance with password requirements

    Raises:
        InvalidPasswordError: If password doesn't meet requirements

    Example:
        >>> from outlabs_auth.core.config import AuthConfig
        >>> config = AuthConfig(secret_key="test", password_min_length=10)
        >>> validate_password_with_config("short", config)
        InvalidPasswordError: Password must be at least 10 characters long
    """
    is_valid, error_message = validate_password_strength(
        password=password,
        min_length=config.password_min_length,
        require_uppercase=config.require_uppercase,
        require_digit=config.require_digit,
        require_special_char=config.require_special_char,
    )

    if not is_valid:
        resolved_error_message = error_message or "Password does not meet the configured requirements"
        raise InvalidPasswordError(
            message=resolved_error_message,
            details={
                "password_requirements": {
                    "min_length": config.password_min_length,
                    "require_uppercase": config.require_uppercase,
                    "require_digit": config.require_digit,
                    "require_special_char": config.require_special_char,
                }
            },
        )


def generate_password_hash(password: str, config) -> str:
    """
    Validate password requirements and return hash.

    Convenience function that validates then hashes in one step.

    Args:
        password: Plain text password
        config: AuthConfig instance with password requirements

    Returns:
        str: Hashed password

    Raises:
        InvalidPasswordError: If password doesn't meet requirements

    Example:
        >>> from outlabs_auth.core.config import AuthConfig
        >>> config = AuthConfig(secret_key="test")
        >>> hashed = generate_password_hash("StrongPass123!", config)
        >>> verify_password("StrongPass123!", hashed)
        True
    """
    # Validate password strength
    validate_password_with_config(password, config)

    # Hash and return
    return hash_password(password)


async def generate_password_hash_async(password: str, config) -> str:
    """
    Async variant of generate_password_hash.

    Validation is cheap (regex) but the Argon2 hash is CPU-heavy; offload
    the entire call to a thread so callers in async contexts don't block
    the event loop.
    """
    validate_password_with_config(password, config)
    return await asyncio.to_thread(hash_password, password)
