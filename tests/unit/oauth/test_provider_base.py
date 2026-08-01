from __future__ import annotations

from typing import Any

import pytest

from outlabs_auth.oauth.exceptions import ProviderError
from outlabs_auth.oauth.models import OAuthAuthorizationURL, OAuthTokenResponse, OAuthUserInfo
from outlabs_auth.oauth.provider import OAuthProvider


class DummyProvider(OAuthProvider):
    name = "dummy"
    display_name = "Dummy"
    authorization_url = "https://provider.example.com/oauth/authorize"
    token_url = "https://provider.example.com/oauth/token"
    default_scopes = ["openid", "email"]
    is_oidc = True

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> OAuthTokenResponse:
        return OAuthTokenResponse(access_token="access-token")

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        return OAuthUserInfo(
            provider_user_id="provider-user-123",
            email="dummy@example.com",
            email_verified=True,
        )


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def post(self, url: str, data: dict[str, Any]) -> FakeResponse:
        self.calls.append((url, "POST", data))
        return self.response


@pytest.mark.unit
def test_oauth_provider_get_authorization_url_generates_security_params(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = DummyProvider(client_id="client-id", client_secret="client-secret")
    captured: dict[str, Any] = {}

    monkeypatch.setattr("outlabs_auth.oauth.provider.generate_state", lambda: "state-123")
    monkeypatch.setattr(
        "outlabs_auth.oauth.provider.generate_pkce_pair",
        lambda: ("verifier-123", "challenge-123"),
    )
    monkeypatch.setattr("outlabs_auth.oauth.provider.generate_nonce", lambda: "nonce-123")

    def fake_build_authorization_url(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "https://provider.example.com/oauth/authorize?built=1"

    monkeypatch.setattr("outlabs_auth.oauth.provider.build_authorization_url", fake_build_authorization_url)

    result = provider.get_authorization_url(
        "https://app.example.com/callback",
        prompt="consent",
    )

    assert isinstance(result, OAuthAuthorizationURL)
    assert result.url == "https://provider.example.com/oauth/authorize?built=1"
    assert result.state == "state-123"
    assert result.code_verifier == "verifier-123"
    assert result.code_challenge == "challenge-123"
    assert result.nonce == "nonce-123"
    assert captured["base_url"] == provider.authorization_url
    assert captured["client_id"] == "client-id"
    assert captured["redirect_uri"] == "https://app.example.com/callback"
    assert captured["scope"] == "openid email"
    assert captured["state"] == "state-123"
    assert captured["code_challenge"] == "challenge-123"
    assert captured["nonce"] == "nonce-123"
    assert captured["prompt"] == "consent"


@pytest.mark.unit
def test_oauth_provider_get_authorization_url_can_skip_pkce_and_nonce(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = DummyProvider(client_id="client-id", client_secret="client-secret")
    provider.supports_pkce = False
    captured: dict[str, Any] = {}

    monkeypatch.setattr("outlabs_auth.oauth.provider.generate_state", lambda: "state-123")
    monkeypatch.setattr("outlabs_auth.oauth.provider.build_authorization_url", lambda **kwargs: captured.update(kwargs) or "https://built")

    result = provider.get_authorization_url(
        "https://app.example.com/callback",
        use_pkce=True,
        use_nonce=False,
    )

    assert result.code_verifier is None
    assert result.code_challenge is None
    assert result.nonce is None
    assert captured["code_challenge"] is None
    assert captured["nonce"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_provider_reuses_http_client_until_closed():
    provider = DummyProvider(client_id="client-id", client_secret="client-secret")

    client_one = await provider.get_http_client()
    client_two = await provider.get_http_client()
    await provider.close()

    assert client_one is client_two
    assert provider._http_client is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_provider_default_refresh_token_posts_standard_request(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = DummyProvider(client_id="client-id", client_secret="client-secret")
    fake_client = FakeClient(
        FakeResponse(
            200,
            {
                "access_token": "new-access-token",
                "token_type": "Bearer",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            },
        )
    )

    async def fake_get_http_client() -> FakeClient:
        return fake_client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    result = await provider.refresh_token("refresh-token")

    assert result.access_token == "new-access-token"
    assert result.refresh_token == "new-refresh-token"
    assert fake_client.calls == [
        (
            provider.token_url,
            "POST",
            {
                "grant_type": "refresh_token",
                "refresh_token": "refresh-token",
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
        )
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_provider_default_refresh_token_wraps_non_200_as_provider_error(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = DummyProvider(client_id="client-id", client_secret="client-secret")
    fake_client = FakeClient(FakeResponse(400, {"error": "invalid_grant"}, text="invalid grant"))

    async def fake_get_http_client() -> FakeClient:
        return fake_client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.refresh_token("refresh-token")

    assert exc_info.value.provider == "dummy"
    assert exc_info.value.error == "token_refresh_failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_provider_refresh_and_revoke_report_unsupported_features():
    provider = DummyProvider(client_id="client-id", client_secret="client-secret")
    provider.supports_refresh = False

    with pytest.raises(NotImplementedError, match="Dummy does not support token refresh"):
        await provider.refresh_token("refresh-token")

    with pytest.raises(NotImplementedError, match="Dummy does not support token revocation"):
        await provider.revoke_token("access-token")

    assert repr(provider) == "DummyProvider(name=dummy)"
