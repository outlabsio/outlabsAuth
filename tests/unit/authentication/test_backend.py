"""Tests for AuthBackend (DD-038)."""

import pytest
from outlabs_auth.authentication.backend import AuthBackend
from outlabs_auth.authentication.transport import BearerTransport
from outlabs_auth.authentication.strategy import JWTStrategy


class TestAuthBackend:
    """Test AuthBackend class."""

    def test_auth_backend_initialization(self):
        """Test that AuthBackend initializes correctly."""
        transport = BearerTransport()
        strategy = JWTStrategy(secret="test_secret")

        backend = AuthBackend(
            name="jwt",
            transport=transport,
            strategy=strategy
        )

        assert backend.name == "jwt"
        assert backend.transport == transport
        assert backend.strategy == strategy

    def test_auth_backend_repr(self):
        """Test AuthBackend string representation."""
        transport = BearerTransport()
        strategy = JWTStrategy(secret="test_secret")

        backend = AuthBackend(
            name="jwt",
            transport=transport,
            strategy=strategy
        )

        repr_str = repr(backend)
        assert "AuthBackend" in repr_str
        assert "jwt" in repr_str
        assert "BearerTransport" in repr_str
        assert "JWTStrategy" in repr_str
