"""
Unit tests for password utilities

Tests password hashing, verification, and strength validation.
"""
import pytest
from outlabs_auth.utils.password import (
    hash_password,
    verify_password,
    validate_password_strength,
    validate_password_with_config,
    generate_password_hash,
)
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import InvalidPasswordError


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_returns_hashed_string(self):
        """Test that hash_password returns a bcrypt hash."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # Bcrypt hash prefix
        assert len(hashed) == 60  # Bcrypt hash length

    def test_verify_password_with_correct_password(self):
        """Test password verification with correct password."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        assert verify_password("WrongPassword", hashed) is False

    def test_hash_password_generates_different_hashes(self):
        """Test that hashing same password twice produces different hashes."""
        password = "MySecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Different hashes due to random salt
        assert hash1 != hash2

        # Both hashes verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestPasswordStrengthValidation:
    """Test password strength validation."""

    def test_validate_strong_password_passes(self):
        """Test that a strong password passes validation."""
        password = "StrongPass123!"

        is_valid, error = validate_password_strength(
            password,
            min_length=8,
            require_uppercase=True,
            require_digit=True,
            require_special_char=True,
        )

        assert is_valid is True
        assert error is None

    def test_validate_short_password_fails(self):
        """Test that a password shorter than min_length fails."""
        password = "Short1!"

        is_valid, error = validate_password_strength(
            password,
            min_length=12,  # Require 12 chars
        )

        assert is_valid is False
        assert "at least 12 characters" in error

    def test_validate_password_without_uppercase_fails(self):
        """Test that password without uppercase fails when required."""
        password = "lowercase123!"

        is_valid, error = validate_password_strength(
            password,
            require_uppercase=True,
        )

        assert is_valid is False
        assert "uppercase" in error.lower()

    def test_validate_password_without_digit_fails(self):
        """Test that password without digit fails when required."""
        password = "PasswordWithoutNumber!"

        is_valid, error = validate_password_strength(
            password,
            require_digit=True,
        )

        assert is_valid is False
        assert "digit" in error.lower()

    def test_validate_password_without_special_char_fails(self):
        """Test that password without special character fails when required."""
        password = "PasswordWith123"

        is_valid, error = validate_password_strength(
            password,
            require_special_char=True,
        )

        assert is_valid is False
        assert "special character" in error.lower()

    def test_validate_password_with_optional_requirements(self):
        """Test password validation with optional requirements disabled."""
        password = "simplepassword"

        is_valid, error = validate_password_strength(
            password,
            min_length=8,
            require_uppercase=False,
            require_digit=False,
            require_special_char=False,
        )

        assert is_valid is True
        assert error is None


class TestPasswordValidationWithConfig:
    """Test password validation using AuthConfig."""

    def test_validate_with_config_passes(self, auth_config: AuthConfig):
        """Test password validation with config."""
        password = "ValidPass123!"

        # Should not raise exception
        validate_password_with_config(password, auth_config)

    def test_validate_with_config_raises_on_weak_password(self, auth_config: AuthConfig):
        """Test that weak password raises InvalidPasswordError."""
        password = "weak"

        with pytest.raises(InvalidPasswordError) as exc_info:
            validate_password_with_config(password, auth_config)

        assert "at least 8 characters" in exc_info.value.message

    def test_validate_with_config_includes_requirements_in_details(self, auth_config: AuthConfig):
        """Test that error details include password requirements."""
        password = "weak"

        with pytest.raises(InvalidPasswordError) as exc_info:
            validate_password_with_config(password, auth_config)

        details = exc_info.value.details
        assert "password_requirements" in details
        assert details["password_requirements"]["min_length"] == 8

    def test_generate_password_hash_validates_and_hashes(self, auth_config: AuthConfig):
        """Test generate_password_hash validates then hashes."""
        password = "StrongPass123!"

        hashed = generate_password_hash(password, auth_config)

        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed) is True

    def test_generate_password_hash_raises_on_weak_password(self, auth_config: AuthConfig):
        """Test that weak password raises error in generate_password_hash."""
        password = "weak"

        with pytest.raises(InvalidPasswordError):
            generate_password_hash(password, auth_config)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_password(self):
        """Test validation with empty password."""
        is_valid, error = validate_password_strength("", min_length=8)

        assert is_valid is False
        assert "at least 8 characters" in error

    def test_password_with_unicode_characters(self):
        """Test password with unicode characters."""
        password = "Pässwörd123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_very_long_password(self):
        """Test very long password (72+ characters)."""
        # Bcrypt has a 72-character limit
        password = "A" * 100 + "1!"  # 102 characters

        hashed = hash_password(password)

        # Bcrypt truncates at 72 chars, but should still work
        assert verify_password(password, hashed) is True
