from __future__ import annotations

import pytest

import outlabs_auth.oauth.provider_factories as oauth_factories
import outlabs_auth.oauth.providers as oauth_providers


@pytest.mark.unit
@pytest.mark.parametrize(
    ("factory_name", "kwargs"),
    [
        ("get_google_client", {}),
        ("get_facebook_client", {}),
        ("get_github_client", {}),
        ("get_microsoft_client", {"tenant": "tenant-123"}),
        ("get_discord_client", {}),
    ],
)
def test_oauth_provider_factories_require_httpx_oauth(
    monkeypatch: pytest.MonkeyPatch,
    factory_name: str,
    kwargs: dict[str, object],
):
    monkeypatch.setattr(oauth_factories, "HTTPX_OAUTH_AVAILABLE", False)

    with pytest.raises(ImportError, match="httpx-oauth is required for OAuth support"):
        getattr(oauth_factories, factory_name)("client-id", "client-secret", **kwargs)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("factory_name", "class_name", "kwargs", "expected_kwargs"),
    [
        (
            "get_google_client",
            "GoogleOAuth2",
            {},
            {"scopes": ["openid", "email", "profile"]},
        ),
        (
            "get_facebook_client",
            "FacebookOAuth2",
            {},
            {"scopes": ["email", "public_profile"]},
        ),
        (
            "get_github_client",
            "GitHubOAuth2",
            {},
            {"scopes": ["user:email"]},
        ),
        (
            "get_microsoft_client",
            "MicrosoftGraphOAuth2",
            {"tenant": "tenant-123"},
            {"tenant": "tenant-123", "scopes": ["User.Read"]},
        ),
        (
            "get_discord_client",
            "DiscordOAuth2",
            {},
            {"scopes": ["identify", "email"]},
        ),
    ],
)
def test_oauth_provider_factories_build_clients_with_default_scopes(
    monkeypatch: pytest.MonkeyPatch,
    factory_name: str,
    class_name: str,
    kwargs: dict[str, object],
    expected_kwargs: dict[str, object],
):
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, *args: object, **init_kwargs: object) -> None:
            captured["args"] = args
            captured["kwargs"] = init_kwargs

    monkeypatch.setattr(oauth_factories, "HTTPX_OAUTH_AVAILABLE", True)
    monkeypatch.setattr(oauth_factories, class_name, DummyClient, raising=False)

    client = getattr(oauth_factories, factory_name)("client-id", "client-secret", **kwargs)

    assert isinstance(client, DummyClient)
    assert captured["args"] == ("client-id", "client-secret")
    assert captured["kwargs"] == expected_kwargs


@pytest.mark.unit
def test_oauth_provider_factories_pass_through_custom_google_scopes(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, *args: object, **init_kwargs: object) -> None:
            captured["args"] = args
            captured["kwargs"] = init_kwargs

    monkeypatch.setattr(oauth_factories, "HTTPX_OAUTH_AVAILABLE", True)
    monkeypatch.setattr(oauth_factories, "GoogleOAuth2", DummyClient, raising=False)

    oauth_factories.get_google_client(
        "client-id",
        "client-secret",
        scopes=["openid", "email"],
    )

    assert captured["args"] == ("client-id", "client-secret")
    assert captured["kwargs"] == {"scopes": ["openid", "email"]}


@pytest.mark.unit
def test_oauth_providers_package_reexports_factory_helpers():
    assert oauth_providers.get_google_client is oauth_factories.get_google_client
    assert oauth_providers.get_facebook_client is oauth_factories.get_facebook_client
    assert oauth_providers.get_github_client is oauth_factories.get_github_client
    assert oauth_providers.get_microsoft_client is oauth_factories.get_microsoft_client
    assert oauth_providers.get_discord_client is oauth_factories.get_discord_client
