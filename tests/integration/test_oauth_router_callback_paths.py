from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

import outlabs_auth.routers.oauth as oauth_router_module
import outlabs_auth.routers.oauth_associate as oauth_associate_module
from outlabs_auth import SimpleRBAC
from outlabs_auth.core.exceptions import AccountLockedError
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.oauth.state import decode_state_token, generate_state_token
from outlabs_auth.routers.oauth import get_oauth_router
from outlabs_auth.routers.oauth_associate import get_oauth_associate_router


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
        query = {
            "redirect_uri": redirect_url,
            "state": state,
        }
        if scopes:
            query["scope"] = " ".join(scopes)
        encoded = urlencode(query)
        return f"https://oauth.example/{self.name}?{encoded}"


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
    )


@pytest.fixture(autouse=True)
def stub_httpx_oauth_fastapi_integration(monkeypatch: pytest.MonkeyPatch):
    class DummyOAuth2AuthorizeCallback:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        async def __call__(self, *args, **kwargs):
            raise AssertionError("OAuth2AuthorizeCallback dependency should not run in direct callback tests")

    httpx_oauth_module = ModuleType("httpx_oauth")
    integrations_module = ModuleType("httpx_oauth.integrations")
    fastapi_module = ModuleType("httpx_oauth.integrations.fastapi")
    fastapi_module.OAuth2AuthorizeCallback = DummyOAuth2AuthorizeCallback
    integrations_module.fastapi = fastapi_module
    httpx_oauth_module.integrations = integrations_module

    monkeypatch.setitem(sys.modules, "httpx_oauth", httpx_oauth_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations", integrations_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations.fastapi", fastapi_module)


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=15,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_authorize_returns_signed_state_and_callback_creates_user(
    auth_instance: SimpleRBAC,
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-state-secret",
        prefix="/v1/oauth/github",
        redirect_url="https://app.example.com/oauth/github/callback",
        is_verified_by_default=True,
    )
    authorize = _endpoint(router, "/v1/oauth/github/authorize", "GET")
    callback = _endpoint(router, "/v1/oauth/github/callback", "GET")

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="github-user-123",
            email=f"oauth-{uuid4().hex[:8]}@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_router_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    authorize_response = await authorize(
        request=SimpleNamespace(),
        scopes=["user:email", "read:user"],
    )
    parsed = urlparse(authorize_response.authorization_url)
    params = parse_qs(parsed.query)
    state = params["state"][0]
    decoded = decode_state_token(state, "oauth-state-secret")
    assert decoded.get("aud") == "outlabs-auth:oauth-state"
    assert decoded.get("sub") is None
    assert params["redirect_uri"] == ["https://app.example.com/oauth/github/callback"]
    assert params["scope"] == ["user:email read:user"]

    callback_result = None
    email = None
    async with auth_instance.get_session() as session:
        callback_result = await callback(
            request=_request(),
            session=session,
            access_token_state=(
                {
                    "access_token": "provider-access-token",
                    "refresh_token": "provider-refresh-token",
                    "expires_at": 1_900_000_000,
                },
                state,
            ),
        )

    assert callback_result["access_token"]
    assert callback_result["refresh_token"]

    async with auth_instance.get_session() as session:
        social_account = (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.provider == "github",
                    SocialAccount.provider_user_id == "github-user-123",
                )
            )
        ).scalar_one()
        user = await auth_instance.user_service.get_user_by_id(session, social_account.user_id)
        assert user is not None
        email = user.email
        assert user.email_verified is True
        assert "GITHUB" in (user.auth_methods or [])
        assert social_account.provider_email == email
        assert social_account.provider_email_verified is True

    assert email is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_callback_rejects_invalid_state_token(
    auth_instance: SimpleRBAC,
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-state-secret",
        prefix="/v1/oauth/github",
        redirect_url="https://app.example.com/oauth/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth/github/callback", "GET")

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="github-user-456",
            email=f"oauth-invalid-{uuid4().hex[:8]}@example.com",
            email_verified=True,
        )

    monkeypatch.setattr(
        oauth_router_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    async with auth_instance.get_session() as session:
        with pytest.raises(HTTPException) as exc_info:
            await callback(
                request=_request(),
                session=session,
                access_token_state=(
                    {"access_token": "provider-access-token"},
                    "not-a-valid-state-token",
                ),
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid OAuth state token"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_associate_authorize_embeds_authenticated_user_in_state(
    auth_instance: SimpleRBAC,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_associate_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    authorize = _endpoint(router, "/v1/oauth-associate/github/authorize", "GET")
    user_id = str(uuid4())

    response = await authorize(
        request=SimpleNamespace(),
        auth_context={"user_id": user_id},
        scopes=["user:email"],
    )
    params = parse_qs(urlparse(response.authorization_url).query)
    state = params["state"][0]
    decoded = decode_state_token(state, "oauth-associate-secret")

    assert decoded["sub"] == user_id
    assert params["redirect_uri"] == [
        "https://app.example.com/oauth/associate/github/callback"
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_associate_callback_links_account_for_authenticated_user(
    auth_instance: SimpleRBAC,
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_associate_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"associate-{uuid4().hex[:8]}@example.com",
            password="AssociatePass123!",
            first_name="Associate",
            last_name="Target",
        )
        await session.commit()
        user_id = str(user.id)
        user_uuid = user.id

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="github-associated-user",
            email=f"associated-{uuid4().hex[:8]}@example.com",
            email_verified=True,
            display_name="Associated User",
            avatar_url="https://avatar.example.com/github-associated-user.png",
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    state = generate_state_token({"sub": user_id}, "oauth-associate-secret", lifetime_seconds=600)

    async with auth_instance.get_session() as session:
        result = await callback(
            request=_request(),
            session=session,
            auth_context={"user_id": user_id},
            access_token_state=(
                {
                    "access_token": "associate-access-token",
                    "refresh_token": "associate-refresh-token",
                    "expires_at": 1_900_000_100,
                },
                state,
            ),
        )

    assert result.provider == "github"
    assert result.provider_user_id == "github-associated-user"
    assert result.email_verified is True

    async with auth_instance.get_session() as session:
        linked_account = (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.user_id == user_uuid,
                    SocialAccount.provider == "github",
                )
            )
        ).scalar_one()
        user = await auth_instance.user_service.get_user_by_id(session, linked_account.user_id)
        assert user is not None
        assert "GITHUB" in (user.auth_methods or [])
        assert linked_account.provider_user_id == "github-associated-user"
        assert linked_account.provider_email_verified is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_associate_callback_rejects_state_user_mismatch(
    auth_instance: SimpleRBAC,
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_associate_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="github-user-mismatch",
            email=f"mismatch-{uuid4().hex[:8]}@example.com",
            email_verified=True,
            display_name=None,
            avatar_url=None,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"mismatch-owner-{uuid4().hex[:8]}@example.com",
            password="AssociatePass123!",
        )
        await session.commit()

    state = generate_state_token(
        {"sub": str(uuid4())},
        "oauth-associate-secret",
        lifetime_seconds=600,
    )

    async with auth_instance.get_session() as session:
        with pytest.raises(HTTPException) as exc_info:
            await callback(
                request=_request(),
                session=session,
                auth_context={"user_id": str(user.id)},
                access_token_state=(
                    {"access_token": "associate-access-token"},
                    state,
                ),
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "OAuth state user mismatch (security)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_associate_callback_rejects_provider_account_linked_to_another_user(
    auth_instance: SimpleRBAC,
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_associate_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-associate-secret",
        prefix="/v1/oauth-associate/github",
        redirect_url="https://app.example.com/oauth/associate/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth-associate/github/callback", "GET")

    async with auth_instance.get_session() as session:
        owner = await auth_instance.user_service.create_user(
            session=session,
            email=f"owner-{uuid4().hex[:8]}@example.com",
            password="AssociatePass123!",
        )
        other_user = await auth_instance.user_service.create_user(
            session=session,
            email=f"other-{uuid4().hex[:8]}@example.com",
            password="AssociatePass123!",
        )
        session.add(
            SocialAccount(
                user_id=other_user.id,
                provider="github",
                provider_user_id="github-linked-elsewhere",
                provider_email=other_user.email,
                provider_email_verified=True,
            )
        )
        await session.commit()
        owner_id = str(owner.id)

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="github-linked-elsewhere",
            email=f"collision-{uuid4().hex[:8]}@example.com",
            email_verified=True,
            display_name=None,
            avatar_url=None,
        )

    monkeypatch.setattr(
        oauth_associate_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    state = generate_state_token({"sub": owner_id}, "oauth-associate-secret", lifetime_seconds=600)

    async with auth_instance.get_session() as session:
        with pytest.raises(HTTPException) as exc_info:
            await callback(
                request=_request(),
                session=session,
                auth_context={"user_id": owner_id},
                access_token_state=(
                    {"access_token": "associate-access-token"},
                    state,
                ),
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "This OAuth account is already linked to another user"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oauth_callback_rejects_locked_existing_user(
    auth_instance: SimpleRBAC,
    monkeypatch: pytest.MonkeyPatch,
):
    oauth_client = DummyOAuthClient("github")
    router = get_oauth_router(
        oauth_client,
        auth_instance,
        state_secret="oauth-state-secret",
        prefix="/v1/oauth/github",
        redirect_url="https://app.example.com/oauth/github/callback",
    )
    callback = _endpoint(router, "/v1/oauth/github/callback", "GET")

    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"oauth-locked-{uuid4().hex[:8]}@example.com",
            password="LockedPass123!",
        )
        user.failed_login_attempts = auth_instance.config.max_login_attempts
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        session.add(
            SocialAccount(
                user_id=user.id,
                provider="github",
                provider_user_id="github-locked-user",
                provider_email=user.email,
                provider_email_verified=True,
            )
        )
        await session.commit()

    async def fake_get_oauth_user_info(oauth_client, token):
        return SimpleNamespace(
            provider_user_id="github-locked-user",
            email="",
            email_verified=False,
        )

    monkeypatch.setattr(
        oauth_router_module,
        "get_oauth_user_info",
        fake_get_oauth_user_info,
    )

    state = generate_state_token({}, "oauth-state-secret", lifetime_seconds=600)

    async with auth_instance.get_session() as session:
        with pytest.raises(AccountLockedError):
            await callback(
                request=_request(),
                session=session,
                access_token_state=(
                    {"access_token": "provider-access-token"},
                    state,
                ),
            )
