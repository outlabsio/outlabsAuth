from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from outlabs_auth.oauth.exceptions import InvalidCodeError, ProviderError
from outlabs_auth.oauth.providers.apple import AppleProvider
from outlabs_auth.oauth.providers.facebook import FacebookProvider
from outlabs_auth.oauth.providers.github import GitHubProvider
from outlabs_auth.oauth.providers.google import GoogleProvider


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any] | list[dict[str, Any]],
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)
        self.headers = headers or {"content-type": "application/json"}

    def json(self) -> dict[str, Any] | list[dict[str, Any]]:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def get(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {"method": "GET", "url": url, "headers": headers, "params": params}
        )
        return self._responses.pop(0)

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {"method": "POST", "url": url, "headers": headers, "data": data}
        )
        return self._responses.pop(0)

    async def delete(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        auth: tuple[str, str] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": "DELETE",
                "url": url,
                "headers": headers,
                "json": json,
                "auth": auth,
            }
        )
        return self._responses.pop(0)


@pytest.mark.unit
def test_google_provider_authorization_url_adds_workspace_domain_and_offline_access():
    provider = GoogleProvider(
        client_id="google-client-id",
        client_secret="google-client-secret",
        hosted_domain="example.com",
    )

    authorization = provider.get_authorization_url(
        "https://app.example.com/auth/google/callback",
        state="state-123",
    )

    query = parse_qs(urlparse(authorization.url).query)

    assert query["hd"] == ["example.com"]
    assert query["access_type"] == ["offline"]
    assert query["state"] == ["state-123"]
    assert authorization.code_verifier is not None
    assert authorization.nonce is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_google_provider_exchange_code_rejects_invalid_grant(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GoogleProvider(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    client = FakeClient(
        [
            FakeResponse(
                400,
                {
                    "error": "invalid_grant",
                    "error_description": "code expired",
                },
            )
        ]
    )

    async def fake_get_http_client() -> FakeClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    with pytest.raises(InvalidCodeError, match="Authorization code invalid or expired"):
        await provider.exchange_code("expired-code", "https://app.example.com/callback")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_refresh_and_revoke_use_expected_requests(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GitHubProvider(
        client_id="github-client-id",
        client_secret="github-client-secret",
    )
    client = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            ),
            FakeResponse(204, {}),
        ]
    )

    async def fake_get_http_client() -> FakeClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    refresh_result = await provider.refresh_token("refresh-token")
    revoke_result = await provider.revoke_token("access-token")

    assert refresh_result.access_token == "new-access-token"
    assert refresh_result.refresh_token == "new-refresh-token"
    assert revoke_result is True
    assert client.calls == [
        {
            "method": "POST",
            "url": provider.token_url,
            "headers": {"Accept": "application/json"},
            "data": {
                "client_id": "github-client-id",
                "client_secret": "github-client-secret",
                "grant_type": "refresh_token",
                "refresh_token": "refresh-token",
            },
        },
        {
            "method": "DELETE",
            "url": provider.revocation_url.format(client_id="github-client-id"),
            "headers": {"Accept": "application/vnd.github+json"},
            "json": {"access_token": "access-token"},
            "auth": ("github-client-id", "github-client-secret"),
        },
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_exchange_code_wraps_body_error_as_provider_error(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GitHubProvider(
        client_id="github-client-id",
        client_secret="github-client-secret",
    )
    client = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "error": "incorrect_client_credentials",
                    "error_description": "bad client secret",
                },
            )
        ]
    )

    async def fake_get_http_client() -> FakeClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.exchange_code("code-123", "https://app.example.com/callback")

    assert exc_info.value.provider == "github"
    assert exc_info.value.error == "incorrect_client_credentials"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_exchange_code_rejects_invalid_code(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FacebookProvider(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
    )
    client = FakeClient(
        [
            FakeResponse(
                400,
                {
                    "error": {
                        "code": 190,
                        "message": "Invalid verification code format.",
                    }
                },
            )
        ]
    )

    async def fake_get_http_client() -> FakeClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    with pytest.raises(InvalidCodeError, match="Authorization code invalid or expired"):
        await provider.exchange_code("bad-code", "https://app.example.com/callback")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_exchange_short_lived_token_uses_default_long_lived_expiry(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FacebookProvider(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
    )
    client = FakeClient([FakeResponse(200, {"access_token": "long-lived-token"})])

    async def fake_get_http_client() -> FakeClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    result = await provider.exchange_short_lived_token("short-lived-token")

    assert result.access_token == "long-lived-token"
    assert result.expires_in == 5184000
    assert client.calls == [
        {
            "method": "GET",
            "url": provider.token_url,
            "headers": None,
            "params": {
                "grant_type": "fb_exchange_token",
                "client_id": "facebook-client-id",
                "client_secret": "facebook-client-secret",
                "fb_exchange_token": "short-lived-token",
            },
        }
    ]


@pytest.mark.unit
def test_apple_provider_parse_id_token_without_verification_uses_unverified_decode(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = AppleProvider(
        client_id="com.example.service",
        team_id="TEAM123456",
        key_id="KEY123456",
        private_key="-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----",
    )
    decode_calls: list[dict[str, Any]] = []

    def fake_decode(token: str, options: dict[str, Any] | None = None):
        decode_calls.append({"token": token, "options": options})
        return {
            "sub": "apple-user-123",
            "email": "apple@example.com",
            "email_verified": False,
        }

    monkeypatch.setattr("outlabs_auth.oauth.providers.apple.jwt.decode", fake_decode)

    user_info = provider.parse_id_token("apple-id-token", verify=False)

    assert user_info.provider_user_id == "apple-user-123"
    assert user_info.email_verified is False
    assert decode_calls == [
        {
            "token": "apple-id-token",
            "options": {"verify_signature": False},
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_refresh_and_revoke_use_generated_client_secret(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = AppleProvider(
        client_id="com.example.service",
        team_id="TEAM123456",
        key_id="KEY123456",
        private_key="-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----",
    )
    client = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "id_token": "new-id-token",
                },
            ),
            FakeResponse(200, {}),
        ]
    )

    async def fake_get_http_client() -> FakeClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    refresh_result = await provider.refresh_token("apple-refresh-token")
    revoke_result = await provider.revoke_token("apple-access-token", token_type_hint="refresh_token")

    assert refresh_result.access_token == "new-access-token"
    assert refresh_result.refresh_token == "new-refresh-token"
    assert revoke_result is True
    assert client.calls == [
        {
            "method": "POST",
            "url": provider.token_url,
            "headers": None,
            "data": {
                "client_id": "com.example.service",
                "client_secret": "generated-client-secret",
                "grant_type": "refresh_token",
                "refresh_token": "apple-refresh-token",
            },
        },
        {
            "method": "POST",
            "url": provider.revocation_url,
            "headers": None,
            "data": {
                "client_id": "com.example.service",
                "client_secret": "generated-client-secret",
                "token": "apple-access-token",
                "token_type_hint": "refresh_token",
            },
        },
    ]
