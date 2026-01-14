"""Tests for JWT OAuth state tokens (DD-042)."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from outlabs_auth.oauth.state import decode_state_token, generate_state_token


class TestOAuthStateTokens:
    """Test JWT-based OAuth state token generation and validation."""

    def test_generate_empty_state_token(self):
        """Test generating state token with no data (new user registration)."""
        secret = "test_secret"
        token = generate_state_token({}, secret)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20  # JWT tokens are long

        # Decode to verify structure
        decoded = jwt.decode(
            token, secret, algorithms=["HS256"], audience="outlabs-auth:oauth-state"
        )
        assert "aud" in decoded
        assert decoded["aud"] == "outlabs-auth:oauth-state"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_generate_state_token_with_user_id(self):
        """Test generating state token with user_id (account linking)."""
        secret = "test_secret"
        user_id = "user_123"

        token = generate_state_token({"sub": user_id}, secret)

        # Decode and verify user_id is embedded
        decoded = jwt.decode(
            token, secret, algorithms=["HS256"], audience="outlabs-auth:oauth-state"
        )
        assert decoded["sub"] == user_id
        assert decoded["aud"] == "outlabs-auth:oauth-state"

    def test_generate_state_token_with_custom_data(self):
        """Test generating state token with custom redirect data."""
        secret = "test_secret"
        data = {"redirect_uri": "/dashboard", "custom_field": "custom_value"}

        token = generate_state_token(data, secret)

        # Decode and verify custom data
        decoded = jwt.decode(
            token, secret, algorithms=["HS256"], audience="outlabs-auth:oauth-state"
        )
        assert decoded["redirect_uri"] == "/dashboard"
        assert decoded["custom_field"] == "custom_value"

    def test_decode_valid_state_token(self):
        """Test decoding valid state token."""
        secret = "test_secret"
        data = {"sub": "user_456"}

        token = generate_state_token(data, secret)
        decoded = decode_state_token(token, secret)

        assert decoded["sub"] == "user_456"
        assert decoded["aud"] == "outlabs-auth:oauth-state"

    def test_decode_expired_state_token(self):
        """Test that expired state tokens are rejected."""
        secret = "test_secret"

        # Generate token with 0 second lifetime (immediately expired)
        token = generate_state_token({}, secret, lifetime_seconds=-1)

        # Should raise ExpiredSignatureError
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_state_token(token, secret)

    def test_decode_tampered_state_token(self):
        """Test that tampered tokens are rejected."""
        secret = "test_secret"
        wrong_secret = "wrong_secret"

        token = generate_state_token({"sub": "user_789"}, secret)

        # Try to decode with wrong secret
        with pytest.raises(jwt.InvalidSignatureError):
            decode_state_token(token, wrong_secret)

    def test_decode_wrong_audience_rejected(self):
        """Test that tokens with wrong audience are rejected."""
        secret = "test_secret"

        # Create token with wrong audience manually
        payload = {
            "aud": "wrong-audience",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=600),
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        # Should raise InvalidAudienceError
        with pytest.raises(jwt.InvalidAudienceError):
            decode_state_token(token, secret)

    def test_custom_lifetime(self):
        """Test generating token with custom lifetime."""
        secret = "test_secret"

        # Generate token with 5 minute lifetime
        token = generate_state_token({}, secret, lifetime_seconds=300)

        decoded = jwt.decode(
            token, secret, algorithms=["HS256"], audience="outlabs-auth:oauth-state"
        )

        # Verify token has exp and iat claims
        assert "exp" in decoded
        assert "iat" in decoded

        # Verify the lifetime is correct (exp - iat should be ~300 seconds)
        lifetime = decoded["exp"] - decoded["iat"]
        assert 299 <= lifetime <= 301  # Allow 1 second tolerance

    def test_state_token_stateless(self):
        """Test that state tokens work without database (stateless)."""
        secret = "test_secret"

        # Generate multiple tokens
        token1 = generate_state_token({"sub": "user1"}, secret)
        token2 = generate_state_token({"sub": "user2"}, secret)
        token3 = generate_state_token({}, secret)

        # All should decode successfully (no database needed!)
        decoded1 = decode_state_token(token1, secret)
        decoded2 = decode_state_token(token2, secret)
        decoded3 = decode_state_token(token3, secret)

        assert decoded1["sub"] == "user1"
        assert decoded2["sub"] == "user2"
        assert "sub" not in decoded3

    def test_state_token_missing_secret(self):
        """Test that missing secret raises error."""
        with pytest.raises(ValueError, match="secret is required"):
            generate_state_token({}, None)

        with pytest.raises(ValueError, match="secret is required"):
            decode_state_token("some_token", None)
