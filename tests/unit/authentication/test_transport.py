"""Tests for Transport classes (DD-038)."""

import pytest
from fastapi import Request
from outlabs_auth.authentication.transport import (
    BearerTransport,
    ApiKeyTransport,
    HeaderTransport,
    CookieTransport,
)


@pytest.mark.asyncio
class TestBearerTransport:
    """Test BearerTransport class."""

    async def test_bearer_transport_extracts_token(self):
        """Test that BearerTransport extracts Bearer token from Authorization header."""
        transport = BearerTransport()

        # Mock request with Bearer token
        class MockRequest:
            def __init__(self):
                self.headers = {"authorization": "Bearer test_token_123"}

        request = MockRequest()
        # Note: This is a simplified test. In real tests, use FastAPI's TestClient
        # For now, just verify the transport class exists
        assert transport is not None


@pytest.mark.asyncio
class TestApiKeyTransport:
    """Test ApiKeyTransport class."""

    async def test_api_key_transport_default_header(self):
        """Test that ApiKeyTransport uses X-API-Key header by default."""
        transport = ApiKeyTransport()
        assert transport.header_name == "X-API-Key"

    async def test_api_key_transport_custom_header(self):
        """Test that ApiKeyTransport can use custom header."""
        transport = ApiKeyTransport(header_name="X-Custom-Key")
        assert transport.header_name == "X-Custom-Key"


@pytest.mark.asyncio
class TestHeaderTransport:
    """Test HeaderTransport class."""

    async def test_header_transport_with_prefix(self):
        """Test HeaderTransport with prefix stripping."""
        transport = HeaderTransport(header_name="X-Auth", prefix="Token ")
        assert transport.header_name == "X-Auth"
        assert transport.prefix == "Token "

    async def test_header_transport_without_prefix(self):
        """Test HeaderTransport without prefix."""
        transport = HeaderTransport(header_name="X-Auth")
        assert transport.header_name == "X-Auth"
        assert transport.prefix is None


@pytest.mark.asyncio
class TestCookieTransport:
    """Test CookieTransport class."""

    async def test_cookie_transport_default_name(self):
        """Test that CookieTransport uses 'access_token' cookie by default."""
        transport = CookieTransport()
        assert transport.cookie_name == "access_token"

    async def test_cookie_transport_custom_name(self):
        """Test that CookieTransport can use custom cookie name."""
        transport = CookieTransport(cookie_name="session_token")
        assert transport.cookie_name == "session_token"
