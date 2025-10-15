"""
Password hashing and validation utilities

Uses passlib with bcrypt for secure password hashing.
"""
from passlib.context import CryptContext
from typing import Optional
import re

from outlabs_auth.core.exceptions import InvalidPasswordError


# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        str: Hashed password

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> verify_password("MyPassword123!", hashed)
        True
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hashed password

    Returns:
        bool: True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> verify_password("MyPassword123!", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


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
        raise InvalidPasswordError(
            message=error_message,
            details={"password_requirements": {
                "min_length": config.password_min_length,
                "require_uppercase": config.require_uppercase,
                "require_digit": config.require_digit,
                "require_special_char": config.require_special_char,
            }}
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
