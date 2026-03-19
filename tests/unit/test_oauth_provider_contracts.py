from __future__ import annotations

from typing import Any

import pytest

from outlabs_auth.oauth.providers.facebook import FacebookProvider
from outlabs_auth.oauth.providers.github import GitHubProvider
from outlabs_auth.oauth.providers.google import GoogleProvider


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]] = []

    async def get(self, url: str, headers: dict[str, Any] | None = None, params: dict[str, Any] | None = None):
        self.calls.append(("GET", url, headers, params))
        return self._responses.pop(0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_google_provider_get_user_info_maps_verified_email(monkeypatch: pytest.MonkeyPatch):
    provider = GoogleProvider(
        client_id="google-client-id",
        client_secret="google-client-secret",
    )
    client = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "id": "google-user-123",
                    "email": "google@example.com",
                    "verified_email": True,
                    "name": "Google User",
                    "given_name": "Google",
                    "family_name": "User",
                    "picture": "https://example.com/google.png",
                    "locale": "en",
                },
            )
        ]
    )

    async def fake_get_http_client():
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    user_info = await provider.get_user_info("google-access-token")

    assert user_info.provider_user_id == "google-user-123"
    assert user_info.email == "google@example.com"
    assert user_info.email_verified is True
    assert user_info.given_name == "Google"
    assert user_info.family_name == "User"
    assert client.calls[0][1] == provider.user_info_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_github_provider_get_user_info_prefers_verified_primary_email(
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
                    "id": 12345,
                    "login": "octocat",
                    "name": "The Octocat",
                    "email": "fallback@example.com",
                    "avatar_url": "https://example.com/octocat.png",
                },
            ),
            FakeResponse(
                200,
                [
                    {
                        "email": "verified-primary@example.com",
                        "primary": True,
                        "verified": True,
                    },
                    {
                        "email": "secondary@example.com",
                        "primary": False,
                        "verified": True,
                    },
                ],
            ),
        ]
    )

    async def fake_get_http_client():
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    user_info = await provider.get_user_info("github-access-token")

    assert user_info.provider_user_id == "12345"
    assert user_info.email == "verified-primary@example.com"
    assert user_info.email_verified is True
    assert user_info.name == "The Octocat"
    assert client.calls[0][1] == provider.user_info_url
    assert client.calls[1][1] == provider.user_emails_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_facebook_provider_get_user_info_maps_graph_fields(monkeypatch: pytest.MonkeyPatch):
    provider = FacebookProvider(
        client_id="facebook-app-id",
        client_secret="facebook-app-secret",
    )
    client = FakeClient(
        [
            FakeResponse(
                200,
                {
                    "id": "facebook-user-123",
                    "name": "Facebook User",
                    "email": "facebook@example.com",
                    "first_name": "Facebook",
                    "last_name": "User",
                    "verified": True,
                    "picture": {
                        "data": {
                            "url": "https://example.com/facebook.png",
                        }
                    },
                },
            )
        ]
    )

    async def fake_get_http_client():
        return client

    monkeypatch.setattr(provider, "get_http_client", fake_get_http_client)

    user_info = await provider.get_user_info("facebook-access-token")

    assert user_info.provider_user_id == "facebook-user-123"
    assert user_info.email == "facebook@example.com"
    assert user_info.email_verified is True
    assert user_info.given_name == "Facebook"
    assert user_info.family_name == "User"
    assert user_info.picture == "https://example.com/facebook.png"
    assert client.calls[0][1] == provider.user_info_url
