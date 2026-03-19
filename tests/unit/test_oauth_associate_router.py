from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException

import outlabs_auth.routers.oauth_associate as oauth_associate_module
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.oauth.state import decode_state_token, generate_state_token
from outlabs_auth.routers.oauth_associate import (
    _append_auth_method,
    _normalize_expires_at,
    _to_social_account_response,
    get_oauth_associate_router,
)


class DummyOAuthClient:
    def __init__(self, name: str = "github") -> None:
        self.name = name
        self.calls: list[tuple[str, str, list[str] | None]] = []

    async def get_authorization_url(
        self,
        redirect_url: str,
        state: str,
        scopes: list[str] | None,
    ) -> str:
        self.calls.append((redirect_url, state, scopes))
        return f"https://oauth.example/{self.name}?redirect_uri={redirect_url}&state={state}"


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class DummySession:
    def __init__(self, execute_results=None) -> None:
        self._execute_results = list(execute_results or [])
        self.execute = AsyncMock(side_effect=self._next_execute_result)
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.add = Mock()

    async def _next_execute_result(self, stmt):
        return self._execute_results.pop(0)


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _make_auth() -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(store_oauth_provider_tokens=False),
        deps=SimpleNamespace(require_auth=lambda **kwargs: lambda: None),
        uow=None,
        user_service=SimpleNamespace(
            get_user_by_id=AsyncMock(),
            on_after_oauth_associate=AsyncMock(),
        ),
    )


@pytest.fixture(autouse=True)
def stub_httpx_oauth_fastapi_integration(monkeypatch: pytest.MonkeyPatch):
    class DummyOAuth2AuthorizeCallback:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        async def __call__(self, *args, **kwargs):
            raise AssertionError("OAuth2AuthorizeCallback should not run in direct endpoint tests")

    httpx_oauth_module = ModuleType("httpx_oauth")
    integrations_module = ModuleType("httpx_oauth.integrations")
    fastapi_module = ModuleType("httpx_oauth.integrations.fastapi")
    fastapi_module.OAuth2AuthorizeCallback = DummyOAuth2AuthorizeCallback
    integrations_module.fastapi = fastapi_module
    httpx_oauth_module.integrations = integrations_module

    monkeypatch.setitem(sys.modules, "httpx_oauth", httpx_oauth_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations", integrations_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations.fastapi", fastapi_module)


@pytest.mark.unit
def test_oauth_associate_helpers_normalize_and_map_response():
    naive_dt = datetime(2026, 3, 19, 12, 0, 0)
    aware_dt = datetime(2026, 3, 19, 9, 0, 0, tzinfo=timezone.utc)

    assert _normalize_expires_at(None) is None
    assert _normalize_expires_at("bad-value") is None
    assert _normalize_expires_at(1_900_000_000) == datetime.fromtimestamp(
        1_900_000_000, tz=timezone.utc
    )
    assert _normalize_expires_at(naive_dt) == naive_dt.replace(tzinfo=timezone.utc)
    assert _normalize_expires_at(aware_dt) == aware_dt

    user = SimpleNamespace(auth_methods=["PASSWORD"])
    _append_auth_method(user, "github")
    _append_auth_method(user, "github")
    assert user.auth_methods == ["PASSWORD", "GITHUB"]

    account = SocialAccount(
        user_id=uuid4(),
        provider="github",
        provider_user_id="provider-user-123",
        provider_email="linked@example.com",
        provider_email_verified=True,
        display_name="Linked User",
        avatar_url="https://avatar.example.com/u.png",
    )
    account.last_login_at = aware_dt

    response = _to_social_account_response(account)

    assert response.provider == "github"
    assert response.provider_user_id == "provider-user-123"
    assert response.email == "linked@example.com"
    assert response.last_used_at == aware_dt.isoformat()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_associate_authorize_uses_route_name_when_redirect_url_missing():
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_associate_router(
        oauth_client,
        _make_auth(),
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
    )
    authorize = _endpoint(router, "/v1/oauth-associate/github/authorize", "GET")

    request = SimpleNamespace(
        url_for=lambda route_name: (
            "https://app.example.com/v1/oauth-associate/github/callback"
            if route_name == "oauth-associate:github.callback"
            else None
        )
    )

    response = await authorize(
        request=request,
        auth_context={"user_id": str(uuid4())},
        scopes=["user:email"],
    )

    state = parse_qs(urlparse(response.authorization_url).query)["state"][0]
    decoded = decode_state_token(state, "oauth-associate-secret")

    assert oauth_client.calls == [
        (
            "https://app.example.com/v1/oauth-associate/github/callback",
            state,
            ["user:email"],
        )
    ]
    assert decoded.get("aud") == "outlabs-auth:oauth-state"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_associate_callback_rejects_invalid_state_and_invalid_authenticated_user(
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    auth = _make_auth()
    router = get_oauth_associate_router(
        oauth_client,
        auth,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="provider-user-123",
            email="linked@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    with pytest.raises(HTTPException) as invalid_state_exc_info:
        await callback(
            request=SimpleNamespace(),
            session=DummySession(),
            auth_context={"user_id": str(uuid4())},
            access_token_state=(
                {"access_token": "provider-access-token"},
                "not-a-valid-state",
            ),
        )

    assert invalid_state_exc_info.value.status_code == 400
    assert invalid_state_exc_info.value.detail == "Invalid OAuth state token"

    bad_user_id = "not-a-uuid"
    state = generate_state_token(
        {"sub": bad_user_id},
        "oauth-associate-secret",
        lifetime_seconds=600,
    )

    with pytest.raises(HTTPException) as invalid_user_exc_info:
        await callback(
            request=SimpleNamespace(),
            session=DummySession(),
            auth_context={"user_id": bad_user_id},
            access_token_state=(
                {"access_token": "provider-access-token"},
                state,
            ),
        )

    assert invalid_user_exc_info.value.status_code == 400
    assert invalid_user_exc_info.value.detail == "Invalid authenticated user ID"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_associate_callback_rejects_missing_user(
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    auth = _make_auth()
    auth.user_service.get_user_by_id.return_value = None
    router = get_oauth_associate_router(
        oauth_client,
        auth,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")
    user_id = str(uuid4())

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="provider-user-123",
            email="linked@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    with pytest.raises(HTTPException) as exc_info:
        await callback(
            request=SimpleNamespace(),
            session=DummySession(),
            auth_context={"user_id": user_id},
            access_token_state=(
                {"access_token": "provider-access-token"},
                generate_state_token(
                    {"sub": user_id},
                    "oauth-associate-secret",
                    lifetime_seconds=600,
                ),
            ),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_associate_callback_updates_existing_linked_account_for_same_user(
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    auth = _make_auth()
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, auth_methods=["PASSWORD"])
    auth.user_service.get_user_by_id.return_value = user
    router = get_oauth_associate_router(
        oauth_client,
        auth,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    linked_account = SocialAccount(
        user_id=user_id,
        provider="github",
        provider_user_id="provider-user-123",
        provider_email="old@example.com",
        provider_email_verified=False,
    )
    session = DummySession(execute_results=[ScalarResult(linked_account)])

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="provider-user-123",
            email="new@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    response = await callback(
        request=SimpleNamespace(),
        session=session,
        auth_context={"user_id": str(user_id)},
        access_token_state=(
            {
                "access_token": "provider-access-token",
                "refresh_token": "provider-refresh-token",
                "expires_at": 1_900_000_000,
            },
            generate_state_token(
                {"sub": str(user_id)},
                "oauth-associate-secret",
                lifetime_seconds=600,
            ),
        ),
    )

    assert response.email == "new@example.com"
    assert linked_account.provider_email_verified is True
    assert linked_account.access_token is None
    assert linked_account.refresh_token is None
    assert "GITHUB" in user.auth_methods
    session.commit.assert_awaited_once()
    auth.user_service.on_after_oauth_associate.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_associate_callback_rejects_different_existing_account_for_same_provider(
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    auth = _make_auth()
    user_id = uuid4()
    auth.user_service.get_user_by_id.return_value = SimpleNamespace(
        id=user_id,
        auth_methods=[],
    )
    router = get_oauth_associate_router(
        oauth_client,
        auth,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    existing_provider_account = SocialAccount(
        user_id=user_id,
        provider="github",
        provider_user_id="provider-user-999",
        provider_email="existing@example.com",
        provider_email_verified=True,
    )
    session = DummySession(
        execute_results=[
            ScalarResult(None),
            ScalarResult(existing_provider_account),
        ]
    )

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="provider-user-123",
            email="new@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    with pytest.raises(HTTPException) as exc_info:
        await callback(
            request=SimpleNamespace(),
            session=session,
            auth_context={"user_id": str(user_id)},
            access_token_state=(
                {"access_token": "provider-access-token"},
                generate_state_token(
                    {"sub": str(user_id)},
                    "oauth-associate-secret",
                    lifetime_seconds=600,
                ),
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "A different account for this provider is already linked"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oauth_associate_callback_updates_existing_provider_account_branch(
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    auth = _make_auth()
    user_id = uuid4()
    user = SimpleNamespace(id=user_id, auth_methods=[])
    auth.user_service.get_user_by_id.return_value = user
    router = get_oauth_associate_router(
        oauth_client,
        auth,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    existing_provider_account = SocialAccount(
        user_id=user_id,
        provider="github",
        provider_user_id="provider-user-123",
        provider_email="existing@example.com",
        provider_email_verified=False,
    )
    session = DummySession(
        execute_results=[
            ScalarResult(None),
            ScalarResult(existing_provider_account),
        ]
    )

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="provider-user-123",
            email="updated@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    response = await callback(
        request=SimpleNamespace(),
        session=session,
        auth_context={"user_id": str(user_id)},
        access_token_state=(
            {
                "access_token": "provider-access-token",
                "refresh_token": "provider-refresh-token",
                "expires_at": 1_900_000_000,
            },
            generate_state_token(
                {"sub": str(user_id)},
                "oauth-associate-secret",
                lifetime_seconds=600,
            ),
        ),
    )

    assert response.email == "updated@example.com"
    assert existing_provider_account.provider_email_verified is True
    assert "GITHUB" in user.auth_methods
    auth.user_service.on_after_oauth_associate.assert_awaited_once()
    session.commit.assert_awaited_once()
