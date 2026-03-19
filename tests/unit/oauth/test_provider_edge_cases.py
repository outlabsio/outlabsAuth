from __future__ import annotations

from typing import Any

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
        payload: Any,
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)
        self.headers = headers or {"content-type": "application/json"}

    def json(self) -> Any:
        return self._payload


class SequencedClient:
    def __init__(
        self,
        *,
        get_responses: list[FakeResponse | Exception] | None = None,
        post_responses: list[FakeResponse | Exception] | None = None,
        delete_responses: list[FakeResponse | Exception] | None = None,
    ) -> None:
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.delete_responses = list(delete_responses or [])
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _next(queue: list[FakeResponse | Exception]) -> FakeResponse:
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {"method": "GET", "url": url, "headers": headers, "params": params}
        )
        return self._next(self.get_responses)

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {"method": "POST", "url": url, "headers": headers, "data": data}
        )
        return self._next(self.post_responses)

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
        return self._next(self.delete_responses)


def _apple_provider(**kwargs: Any) -> AppleProvider:
    return AppleProvider(
        client_id="com.example.service",
        team_id="TEAM123456",
        key_id="KEY123456",
        private_key="-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----",
        **kwargs,
    )


@pytest.mark.unit
def test_apple_provider_init_loads_private_key_path_and_requires_key_source(tmp_path):
    private_key_path = tmp_path / "AuthKey_TEST.p8"
    private_key_path.write_text("apple-private-key")

    provider = AppleProvider(
        client_id="com.example.service",
        team_id="TEAM123456",
        key_id="KEY123456",
        private_key_path=str(private_key_path),
    )

    assert provider.private_key == "apple-private-key"

    with pytest.raises(ValueError, match="Either private_key or private_key_path"):
        AppleProvider(
            client_id="com.example.service",
            team_id="TEAM123456",
            key_id="KEY123456",
        )


@pytest.mark.unit
def test_apple_provider_reuses_cached_jwk_client(monkeypatch: pytest.MonkeyPatch):
    provider = _apple_provider()
    jwks_uris: list[str] = []

    class DummyJWKClient:
        def __init__(self, uri: str) -> None:
            jwks_uris.append(uri)

    monkeypatch.setattr(
        "outlabs_auth.oauth.providers.apple.jwt.PyJWKClient",
        DummyJWKClient,
    )

    first = provider._get_jwk_client()
    second = provider._get_jwk_client()

    assert first is second
    assert jwks_uris == [provider.jwks_uri]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, True),
        (0, False),
        ("TRUE", True),
        ("false", False),
    ],
)
def test_apple_provider_coerces_email_verified(value: Any, expected: bool):
    assert AppleProvider._coerce_email_verified(value) is expected


@pytest.mark.unit
def test_apple_provider_generates_client_secret_with_expected_claims(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()
    encode_calls: list[dict[str, Any]] = []

    monkeypatch.setattr("outlabs_auth.oauth.providers.apple.time.time", lambda: 1_700_000_000)

    def fake_encode(
        claims: dict[str, Any],
        private_key: str,
        *,
        algorithm: str,
        headers: dict[str, Any],
    ) -> str:
        encode_calls.append(
            {
                "claims": claims,
                "private_key": private_key,
                "algorithm": algorithm,
                "headers": headers,
            }
        )
        return "signed-client-secret"

    monkeypatch.setattr("outlabs_auth.oauth.providers.apple.jwt.encode", fake_encode)

    client_secret = provider._generate_client_secret()

    assert client_secret == "signed-client-secret"
    assert encode_calls == [
        {
            "claims": {
                "iss": "TEAM123456",
                "iat": 1_700_000_000,
                "exp": 1_700_003_600,
                "aud": "https://appleid.apple.com",
                "sub": "com.example.service",
            },
            "private_key": provider.private_key,
            "algorithm": "ES256",
            "headers": {"kid": "KEY123456", "alg": "ES256"},
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_exchange_code_success_includes_pkce_verifier(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()
    client = SequencedClient(
        post_responses=[
            FakeResponse(
                200,
                {
                    "access_token": "apple-access-token",
                    "refresh_token": "apple-refresh-token",
                    "id_token": "apple-id-token",
                    "expires_in": 3600,
                },
            )
        ]
    )

    async def fake_get_http_client() -> SequencedClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    token_response = await provider.exchange_code(
        "apple-code",
        "https://app.example.com/auth/apple/callback",
        code_verifier="pkce-verifier",
    )

    assert token_response.access_token == "apple-access-token"
    assert token_response.refresh_token == "apple-refresh-token"
    assert token_response.id_token == "apple-id-token"
    assert client.calls == [
        {
            "method": "POST",
            "url": provider.token_url,
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            "data": {
                "client_id": "com.example.service",
                "client_secret": "generated-client-secret",
                "code": "apple-code",
                "grant_type": "authorization_code",
                "redirect_uri": "https://app.example.com/auth/apple/callback",
                "code_verifier": "pkce-verifier",
            },
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_exchange_code_rejects_invalid_grant(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()
    client = SequencedClient(
        post_responses=[
            FakeResponse(
                400,
                {"error": "invalid_grant", "error_description": "code expired"},
            )
        ]
    )

    async def fake_get_http_client() -> SequencedClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    with pytest.raises(InvalidCodeError, match="Authorization code invalid or expired"):
        await provider.exchange_code("expired-code", "https://app.example.com/callback")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_exchange_code_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()
    client = SequencedClient(post_responses=[RuntimeError("apple token timeout")])

    async def fake_get_http_client() -> SequencedClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    with pytest.raises(ProviderError) as exc_info:
        await provider.exchange_code("apple-code", "https://app.example.com/callback")

    assert exc_info.value.provider == "apple"
    assert exc_info.value.error == "network_error"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_exchange_code_wraps_generic_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()
    client = SequencedClient(
        post_responses=[
            FakeResponse(
                400,
                {"error": "invalid_client", "error_description": "client rejected"},
            )
        ]
    )

    async def fake_get_http_client() -> SequencedClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    with pytest.raises(ProviderError) as exc_info:
        await provider.exchange_code("apple-code", "https://app.example.com/callback")

    assert exc_info.value.provider == "apple"
    assert exc_info.value.error == "invalid_client"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_get_user_info_requires_id_token():
    provider = _apple_provider()

    with pytest.raises(NotImplementedError, match="requires ID token parsing"):
        await provider.get_user_info("unused-access-token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_refresh_and_revoke_error_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()

    refresh_error_client = SequencedClient(
        post_responses=[FakeResponse(400, {"error": "invalid_grant"}, text="bad refresh")]
    )

    async def fake_refresh_http_client() -> SequencedClient:
        return refresh_error_client

    monkeypatch.setattr(provider, "get_http_client", fake_refresh_http_client)
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    with pytest.raises(ProviderError) as exc_info:
        await provider.refresh_token("apple-refresh-token")

    assert exc_info.value.provider == "apple"
    assert exc_info.value.error == "token_refresh_failed"

    revoke_false_client = SequencedClient(post_responses=[FakeResponse(400, {}, text="not revoked")])

    async def fake_revoke_http_client() -> SequencedClient:
        return revoke_false_client

    monkeypatch.setattr(provider, "get_http_client", fake_revoke_http_client)

    assert await provider.revoke_token("apple-access-token") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_apple_provider_refresh_and_revoke_wrap_network_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _apple_provider()
    monkeypatch.setattr(provider, "_generate_client_secret", lambda: "generated-client-secret")

    refresh_network_client = SequencedClient(post_responses=[RuntimeError("refresh timeout")])

    async def fake_refresh_http_client() -> SequencedClient:
        return refresh_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_refresh_http_client)

    with pytest.raises(ProviderError, match="refresh timeout"):
        await provider.refresh_token("apple-refresh-token")

    revoke_network_client = SequencedClient(post_responses=[RuntimeError("revoke timeout")])

    async def fake_revoke_http_client() -> SequencedClient:
        return revoke_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_revoke_http_client)

    with pytest.raises(ProviderError, match="revoke timeout"):
        await provider.revoke_token("apple-access-token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_google_provider_exchange_code_success_includes_pkce_verifier(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GoogleProvider(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    client = SequencedClient(
        post_responses=[
            FakeResponse(
                200,
                {
                    "access_token": "google-access-token",
                    "refresh_token": "google-refresh-token",
                    "id_token": "google-id-token",
                    "expires_in": 3600,
                    "scope": "openid email profile",
                },
            )
        ]
    )

    async def fake_get_http_client() -> SequencedClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    token_response = await provider.exchange_code(
        "google-code",
        "https://app.example.com/auth/google/callback",
        code_verifier="pkce-verifier",
    )

    assert token_response.access_token == "google-access-token"
    assert token_response.refresh_token == "google-refresh-token"
    assert token_response.id_token == "google-id-token"
    assert client.calls[0]["data"]["code_verifier"] == "pkce-verifier"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_google_provider_exchange_code_wraps_network_and_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GoogleProvider(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )

    network_client = SequencedClient(post_responses=[RuntimeError("google timeout")])

    async def fake_network_http_client() -> SequencedClient:
        return network_client

    monkeypatch.setattr(provider, "get_http_client", fake_network_http_client)

    with pytest.raises(ProviderError, match="google timeout"):
        await provider.exchange_code("google-code", "https://app.example.com/callback")

    error_client = SequencedClient(
        post_responses=[
            FakeResponse(
                400,
                {"error": "invalid_client", "error_description": "client rejected"},
            )
        ]
    )

    async def fake_error_http_client() -> SequencedClient:
        return error_client

    monkeypatch.setattr(provider, "get_http_client", fake_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.exchange_code("google-code", "https://app.example.com/callback")

    assert exc_info.value.provider == "google"
    assert exc_info.value.error == "invalid_client"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_google_provider_get_user_info_and_revoke_error_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GoogleProvider(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )

    user_info_network_client = SequencedClient(get_responses=[RuntimeError("userinfo timeout")])

    async def fake_network_http_client() -> SequencedClient:
        return user_info_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_network_http_client)

    with pytest.raises(ProviderError, match="userinfo timeout"):
        await provider.get_user_info("google-access-token")

    user_info_error_client = SequencedClient(
        get_responses=[FakeResponse(401, {"error": "invalid_token"}, text="unauthorized")]
    )

    async def fake_error_http_client() -> SequencedClient:
        return user_info_error_client

    monkeypatch.setattr(provider, "get_http_client", fake_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.get_user_info("google-access-token")

    assert exc_info.value.error == "user_info_failed"

    revoke_false_client = SequencedClient(post_responses=[FakeResponse(400, {}, text="nope")])

    async def fake_revoke_http_client() -> SequencedClient:
        return revoke_false_client

    monkeypatch.setattr(provider, "get_http_client", fake_revoke_http_client)

    assert await provider.revoke_token("google-access-token") is False

    revoke_network_client = SequencedClient(post_responses=[RuntimeError("revoke timeout")])

    async def fake_revoke_network_http_client() -> SequencedClient:
        return revoke_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_revoke_network_http_client)

    with pytest.raises(ProviderError, match="revoke timeout"):
        await provider.revoke_token("google-access-token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_exchange_code_success_and_invalid_verification_code(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GitHubProvider(
        client_id="github-client-id",
        client_secret="github-client-secret",
    )
    success_client = SequencedClient(
        post_responses=[
            FakeResponse(
                200,
                {
                    "access_token": "github-access-token",
                    "refresh_token": "github-refresh-token",
                    "expires_in": 3600,
                    "scope": "read:user user:email",
                },
            )
        ]
    )

    async def fake_success_http_client() -> SequencedClient:
        return success_client

    monkeypatch.setattr(provider, "get_http_client", fake_success_http_client)

    token_response = await provider.exchange_code(
        "github-code",
        "https://app.example.com/auth/github/callback",
        code_verifier="pkce-verifier",
    )

    assert token_response.access_token == "github-access-token"
    assert success_client.calls[0]["data"]["code_verifier"] == "pkce-verifier"

    invalid_code_client = SequencedClient(
        post_responses=[
            FakeResponse(
                400,
                {
                    "error": "bad_verification_code",
                    "error_description": "code already used",
                },
            )
        ]
    )

    async def fake_invalid_http_client() -> SequencedClient:
        return invalid_code_client

    monkeypatch.setattr(provider, "get_http_client", fake_invalid_http_client)

    with pytest.raises(InvalidCodeError, match="Authorization code invalid or expired"):
        await provider.exchange_code("github-code", "https://app.example.com/callback")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_exchange_refresh_and_revoke_wrap_failures(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GitHubProvider(
        client_id="github-client-id",
        client_secret="github-client-secret",
    )

    exchange_network_client = SequencedClient(post_responses=[RuntimeError("github timeout")])

    async def fake_exchange_http_client() -> SequencedClient:
        return exchange_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_exchange_http_client)

    with pytest.raises(ProviderError, match="github timeout"):
        await provider.exchange_code("github-code", "https://app.example.com/callback")

    exchange_error_client = SequencedClient(
        post_responses=[
            FakeResponse(
                400,
                {
                    "error": "invalid_client",
                    "error_description": "client rejected",
                },
            )
        ]
    )

    async def fake_exchange_error_http_client() -> SequencedClient:
        return exchange_error_client

    monkeypatch.setattr(provider, "get_http_client", fake_exchange_error_http_client)

    with pytest.raises(ProviderError) as exchange_exc_info:
        await provider.exchange_code("github-code", "https://app.example.com/callback")

    assert exchange_exc_info.value.error == "invalid_client"

    refresh_error_client = SequencedClient(post_responses=[FakeResponse(400, {}, text="refresh failed")])

    async def fake_refresh_error_http_client() -> SequencedClient:
        return refresh_error_client

    monkeypatch.setattr(provider, "get_http_client", fake_refresh_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.refresh_token("github-refresh-token")

    assert exc_info.value.error == "token_refresh_failed"

    refresh_network_client = SequencedClient(post_responses=[RuntimeError("refresh timeout")])

    async def fake_refresh_network_http_client() -> SequencedClient:
        return refresh_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_refresh_network_http_client)

    with pytest.raises(ProviderError, match="refresh timeout"):
        await provider.refresh_token("github-refresh-token")

    revoke_false_client = SequencedClient(delete_responses=[FakeResponse(403, {}, text="forbidden")])

    async def fake_revoke_false_http_client() -> SequencedClient:
        return revoke_false_client

    monkeypatch.setattr(provider, "get_http_client", fake_revoke_false_http_client)

    assert await provider.revoke_token("github-access-token") is False

    revoke_network_client = SequencedClient(delete_responses=[RuntimeError("revoke failed")])

    async def fake_revoke_network_http_client() -> SequencedClient:
        return revoke_network_client

    monkeypatch.setattr(provider, "get_http_client", fake_revoke_network_http_client)

    with pytest.raises(ProviderError, match="revoke failed"):
        await provider.revoke_token("github-access-token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_get_user_info_falls_back_for_email_edge_cases(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GitHubProvider(
        client_id="github-client-id",
        client_secret="github-client-secret",
    )

    any_verified_client = SequencedClient(
        get_responses=[
            FakeResponse(
                200,
                {
                    "id": 12345,
                    "login": "octocat",
                    "name": "",
                    "email": "",
                    "avatar_url": "https://example.com/octocat.png",
                },
            ),
            FakeResponse(
                200,
                [
                    {
                        "email": "secondary@example.com",
                        "primary": False,
                        "verified": True,
                    }
                ],
            ),
        ]
    )

    async def fake_any_verified_http_client() -> SequencedClient:
        return any_verified_client

    monkeypatch.setattr(provider, "get_http_client", fake_any_verified_http_client)

    any_verified_user = await provider.get_user_info("github-access-token")

    assert any_verified_user.email == "secondary@example.com"
    assert any_verified_user.email_verified is True
    assert any_verified_user.name == "octocat"

    profile_fallback_client = SequencedClient(
        get_responses=[
            FakeResponse(
                200,
                {
                    "id": 67890,
                    "login": "fallback",
                    "name": "Fallback User",
                    "email": "fallback@example.com",
                },
            ),
            RuntimeError("email API unavailable"),
        ]
    )

    async def fake_profile_fallback_http_client() -> SequencedClient:
        return profile_fallback_client

    monkeypatch.setattr(provider, "get_http_client", fake_profile_fallback_http_client)

    profile_fallback_user = await provider.get_user_info("github-access-token")

    assert profile_fallback_user.email == "fallback@example.com"
    assert profile_fallback_user.email_verified is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_get_user_info_wraps_profile_fetch_failures(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = GitHubProvider(
        client_id="github-client-id",
        client_secret="github-client-secret",
    )

    network_client = SequencedClient(get_responses=[RuntimeError("profile timeout")])

    async def fake_network_http_client() -> SequencedClient:
        return network_client

    monkeypatch.setattr(provider, "get_http_client", fake_network_http_client)

    with pytest.raises(ProviderError, match="profile timeout"):
        await provider.get_user_info("github-access-token")

    error_client = SequencedClient(
        get_responses=[FakeResponse(401, {"error": "bad_token"}, text="unauthorized")]
    )

    async def fake_error_http_client() -> SequencedClient:
        return error_client

    monkeypatch.setattr(provider, "get_http_client", fake_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.get_user_info("github-access-token")

    assert exc_info.value.error == "user_info_failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_exchange_code_wraps_network_and_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FacebookProvider(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
    )

    network_client = SequencedClient(get_responses=[RuntimeError("facebook timeout")])

    async def fake_network_http_client() -> SequencedClient:
        return network_client

    monkeypatch.setattr(provider, "get_http_client", fake_network_http_client)

    with pytest.raises(ProviderError, match="facebook timeout"):
        await provider.exchange_code("facebook-code", "https://app.example.com/callback")

    provider_error_client = SequencedClient(
        get_responses=[
            FakeResponse(
                400,
                {
                    "error": {
                        "code": 200,
                        "message": "Permissions error",
                    }
                },
            )
        ]
    )

    async def fake_provider_error_http_client() -> SequencedClient:
        return provider_error_client

    monkeypatch.setattr(provider, "get_http_client", fake_provider_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.exchange_code("facebook-code", "https://app.example.com/callback")

    assert exc_info.value.provider == "facebook"
    assert exc_info.value.error == "200"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_exchange_code_success_maps_token_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FacebookProvider(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
    )
    client = SequencedClient(
        get_responses=[
            FakeResponse(
                200,
                {
                    "access_token": "facebook-access-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        ]
    )

    async def fake_get_http_client() -> SequencedClient:
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    token_response = await provider.exchange_code(
        "facebook-code",
        "https://app.example.com/auth/facebook/callback",
    )

    assert token_response.access_token == "facebook-access-token"
    assert token_response.token_type == "bearer"
    assert token_response.expires_in == 3600


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_get_user_info_wraps_network_and_non_200_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FacebookProvider(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
    )

    network_client = SequencedClient(get_responses=[RuntimeError("graph timeout")])

    async def fake_network_http_client() -> SequencedClient:
        return network_client

    monkeypatch.setattr(provider, "get_http_client", fake_network_http_client)

    with pytest.raises(ProviderError, match="graph timeout"):
        await provider.get_user_info("facebook-access-token")

    error_client = SequencedClient(
        get_responses=[FakeResponse(401, {"error": "bad_token"}, text="unauthorized")]
    )

    async def fake_error_http_client() -> SequencedClient:
        return error_client

    monkeypatch.setattr(provider, "get_http_client", fake_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.get_user_info("facebook-access-token")

    assert exc_info.value.error == "user_info_failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_refresh_and_exchange_short_lived_token_error_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FacebookProvider(
        client_id="facebook-client-id",
        client_secret="facebook-client-secret",
    )

    with pytest.raises(NotImplementedError, match="doesn't use refresh tokens"):
        await provider.refresh_token("facebook-refresh-token")

    network_client = SequencedClient(get_responses=[RuntimeError("exchange timeout")])

    async def fake_network_http_client() -> SequencedClient:
        return network_client

    monkeypatch.setattr(provider, "get_http_client", fake_network_http_client)

    with pytest.raises(ProviderError, match="exchange timeout"):
        await provider.exchange_short_lived_token("short-lived-token")

    error_client = SequencedClient(
        get_responses=[FakeResponse(400, {"error": "bad_token"}, text="exchange failed")]
    )

    async def fake_error_http_client() -> SequencedClient:
        return error_client

    monkeypatch.setattr(provider, "get_http_client", fake_error_http_client)

    with pytest.raises(ProviderError) as exc_info:
        await provider.exchange_short_lived_token("short-lived-token")

    assert exc_info.value.error == "token_exchange_failed"
