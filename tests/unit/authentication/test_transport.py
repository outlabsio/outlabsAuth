"""Tests for Transport classes (DD-038)."""

import pytest
from starlette.requests import Request
from outlabs_auth.authentication.transport import (
    ApiKeyTransport,
    BearerTransport,
    CookieTransport,
    HeaderTransport,
    QueryParamTransport,
)


def _make_request(
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    query_string: bytes = b"",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers or [],
            "query_string": query_string,
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bearer_transport_extracts_token_and_returns_none_without_header():
    transport = BearerTransport()

    request = _make_request(headers=[(b"authorization", b"Bearer test_token_123")])
    missing_request = _make_request()

    assert await transport.get_credentials(request) == "test_token_123"
    assert await transport.get_credentials(missing_request) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_api_key_transport_reads_default_and_custom_headers():
    default_transport = ApiKeyTransport()
    custom_transport = ApiKeyTransport(header_name="X-Custom-Key")
    request = _make_request(
        headers=[
            (b"x-api-key", b"default-key"),
            (b"x-custom-key", b"custom-key"),
        ]
    )

    assert default_transport.header_name == "X-API-Key"
    assert custom_transport.header_name == "X-Custom-Key"
    assert await default_transport.get_credentials(request) == "default-key"
    assert await custom_transport.get_credentials(request) == "custom-key"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_header_transport_strips_prefix_and_rejects_mismatch():
    prefixed_transport = HeaderTransport(header_name="X-Auth", prefix="Token ")
    raw_transport = HeaderTransport(header_name="X-Auth")
    prefixed_request = _make_request(headers=[(b"x-auth", b"Token abc123")])
    wrong_prefix_request = _make_request(headers=[(b"x-auth", b"Bearer abc123")])

    assert prefixed_transport.header_name == "X-Auth"
    assert prefixed_transport.prefix == "Token "
    assert await prefixed_transport.get_credentials(prefixed_request) == "abc123"
    assert await prefixed_transport.get_credentials(wrong_prefix_request) is None
    assert await raw_transport.get_credentials(prefixed_request) == "Token abc123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cookie_and_query_param_transports_extract_credentials():
    cookie_transport = CookieTransport()
    custom_cookie_transport = CookieTransport(cookie_name="session_token")
    query_transport = QueryParamTransport()
    custom_query_transport = QueryParamTransport(param_name="api_key")

    request = _make_request(
        headers=[(b"cookie", b"access_token=cookie-123; session_token=session-456")],
        query_string=b"token=query-token&api_key=query-key",
    )

    assert cookie_transport.cookie_name == "access_token"
    assert custom_cookie_transport.cookie_name == "session_token"
    assert query_transport.param_name == "token"
    assert custom_query_transport.param_name == "api_key"
    assert await cookie_transport.get_credentials(request) == "cookie-123"
    assert await custom_cookie_transport.get_credentials(request) == "session-456"
    assert await query_transport.get_credentials(request) == "query-token"
    assert await custom_query_transport.get_credentials(request) == "query-key"
