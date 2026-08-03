"""Integration tests for DD-059 slice 3: profile-bound OAuth state.

One router mount serves several frontends: ``/authorize`` accepts a
registered profile key, the key rides in the SIGNED state token and is
persisted on the state record, the binding cookie is per-profile so
concurrent same-provider flows do not clobber each other, and the callback
resolves the bound profile's declared success/error landings — with the
construction-time URLs as the legacy fallback.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Response
from sqlalchemy import select

import outlabs_auth.routers.oauth as oauth_router_module
import outlabs_auth.routers.oauth_associate as oauth_associate_module
from outlabs_auth import SimpleRBAC
from outlabs_auth.frontend import (
    FrontendProfile,
    FrontendProfileRegistry,
    FrontendProfileResolver,
    FrontendRoutes,
)
from outlabs_auth.models.sql.oauth_state import OAuthState
from outlabs_auth.oauth.state import decode_state_token
from outlabs_auth.routers.oauth import get_oauth_router
from outlabs_auth.routers.oauth_associate import get_oauth_associate_router
from outlabs_auth.routers.oauth_state_store import oauth_state_cookie_name

STATE_SECRET = "state-secret-for-tests-1234567890abcdef"


class DummyOAuthClient:
    def __init__(self, name: str = "github") -> None:
        self.name = name

    async def get_authorization_url(
        self,
        redirect_url,
        state=None,
        scope=None,
        code_challenge=None,
        code_challenge_method=None,
        extras_params=None,
    ):
        assert code_challenge
        assert code_challenge_method == "S256"
        query = {"redirect_uri": redirect_url, "state": state}
        return f"https://oauth.example/{self.name}?{urlencode(query)}"


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path.endswith(path) and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _request(cookies: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
        cookies=cookies or {},
    )


def _state_from(authorize_result) -> str:
    query = parse_qs(urlparse(authorize_result.authorization_url).query)
    return query["state"][0]


@pytest.fixture(autouse=True)
def stub_httpx_oauth_fastapi_integration(monkeypatch: pytest.MonkeyPatch):
    class DummyOAuth2AuthorizeCallback:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        async def __call__(self, *args, **kwargs):
            raise AssertionError("dependency should not run in direct callback tests")

    httpx_oauth_module = ModuleType("httpx_oauth")
    integrations_module = ModuleType("httpx_oauth.integrations")
    fastapi_module = ModuleType("httpx_oauth.integrations.fastapi")
    fastapi_module.OAuth2AuthorizeCallback = DummyOAuth2AuthorizeCallback
    integrations_module.fastapi = fastapi_module
    httpx_oauth_module.integrations = integrations_module
    monkeypatch.setitem(sys.modules, "httpx_oauth", httpx_oauth_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations", integrations_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations.fastapi", fastapi_module)


def _registry() -> FrontendProfileRegistry:
    return FrontendProfileRegistry(
        [
            FrontendProfile(
                key="console",
                app_name="Console",
                public_origins=("https://console.example.com",),
                routes=FrontendRoutes(
                    login="/login",
                    oauth_success="/auth/oauth/callback",
                    oauth_error="/auth/oauth/error",
                    oauth_associate_success="/settings/connections",
                ),
            ),
            FrontendProfile(
                key="portal",
                app_name="Portal",
                public_origins=("https://portal.example.com",),
                routes=FrontendRoutes(
                    login="/sign-in",
                    oauth_success="/oauth/done",
                    # no oauth_error: error landing falls back to login
                ),
            ),
            FrontendProfile(
                key="bare",
                app_name="Bare",
                public_origins=("https://bare.example.com",),
                routes=FrontendRoutes(login="/login"),
            ),
        ]
    )


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=15,
        enable_token_cleanup=False,
        frontend_resolver=FrontendProfileResolver(_registry()),
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


def _login_router(auth: SimpleRBAC):
    return get_oauth_router(
        DummyOAuthClient("github"),
        auth,
        STATE_SECRET,
        prefix="/v1/oauth/github",
        redirect_url="https://api.example/oauth/github/callback",
        success_redirect_url="https://legacy.example/success",
        error_redirect_url="https://legacy.example/error",
        associate_by_email=False,
        is_verified_by_default=True,
    )


async def _authorize(auth, router, app_key=None):
    authorize_ep = _endpoint(router, "/authorize", "GET")
    response = Response()
    async with auth.get_session() as session:
        result = await authorize_ep(request=_request(), response=response, session=session, scopes=None, app=app_key)
    return _state_from(result)


async def _cookies_for(auth, state: str, *, flow: str = "login", app_key=None) -> dict[str, str]:
    async with auth.get_session() as session:
        record = (await session.execute(select(OAuthState).where(OAuthState.state == state))).scalar_one()
    assert record.browser_binding is not None
    return {oauth_state_cookie_name("github", flow, app_key): record.browser_binding}


def _patch_user_info(monkeypatch, module, email: str, provider_user_id: str):
    async def fake_get_oauth_user_info(client, token):
        return SimpleNamespace(provider_user_id=provider_user_id, email=email, email_verified=True)

    monkeypatch.setattr(module, "get_oauth_user_info", fake_get_oauth_user_info)


async def _callback(auth, router, state: str, cookies: dict[str, str]):
    callback_ep = _endpoint(router, "/callback", "GET")
    token = {"access_token": "provider-token", "refresh_token": None, "expires_at": None}
    async with auth.get_session() as session:
        return await callback_ep(
            request=_request(cookies),
            response=Response(),
            session=session,
            access_token_state=(token, state),
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_mount_lands_each_profile_on_its_own_frontend(
    auth_instance: SimpleRBAC, monkeypatch: pytest.MonkeyPatch
):
    auth = auth_instance
    router = _login_router(auth)

    for app_key, expected_prefix, email in (
        ("console", "https://console.example.com/auth/oauth/callback#", "c1@example.com"),
        ("portal", "https://portal.example.com/oauth/done#", "p1@example.com"),
    ):
        state = await _authorize(auth, router, app_key=app_key)
        assert decode_state_token(state, STATE_SECRET)["app"] == app_key
        async with auth.get_session() as session:
            record = (await session.execute(select(OAuthState).where(OAuthState.state == state))).scalar_one()
        assert record.profile_id == app_key

        _patch_user_info(monkeypatch, oauth_router_module, email, f"gh-{email}")
        cookies = await _cookies_for(auth, state, app_key=app_key)
        result = await _callback(auth, router, state, cookies)
        location = result.headers["location"]
        assert location.startswith(expected_prefix), location
        assert "access_token=" in location


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_same_provider_flows_do_not_clobber(
    auth_instance: SimpleRBAC, monkeypatch: pytest.MonkeyPatch
):
    auth = auth_instance
    router = _login_router(auth)

    console_state = await _authorize(auth, router, app_key="console")
    portal_state = await _authorize(auth, router, app_key="portal")

    # One browser, both flows in flight: the per-profile cookie names coexist.
    cookies = {
        **(await _cookies_for(auth, console_state, app_key="console")),
        **(await _cookies_for(auth, portal_state, app_key="portal")),
    }
    assert len(cookies) == 2

    _patch_user_info(monkeypatch, oauth_router_module, "p2@example.com", "gh-p2")
    portal_result = await _callback(auth, router, portal_state, cookies)
    assert portal_result.headers["location"].startswith("https://portal.example.com/oauth/done#")

    _patch_user_info(monkeypatch, oauth_router_module, "c2@example.com", "gh-c2")
    console_result = await _callback(auth, router, console_state, cookies)
    assert console_result.headers["location"].startswith("https://console.example.com/auth/oauth/callback#")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_app_and_missing_oauth_route_rejected_at_authorize(
    auth_instance: SimpleRBAC,
):
    auth = auth_instance
    router = _login_router(auth)

    with pytest.raises(HTTPException) as unknown:
        await _authorize(auth, router, app_key="nope")
    assert unknown.value.status_code == 400

    with pytest.raises(HTTPException) as unsupported:
        await _authorize(auth, router, app_key="bare")
    assert unsupported.value.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_redirect_uses_profile_bound_target_after_trusted_decode(
    auth_instance: SimpleRBAC,
):
    auth = auth_instance
    router = _login_router(auth)

    state = await _authorize(auth, router, app_key="console")
    # Valid signed state, but no binding cookie (e.g. another browser): the
    # app claim is trusted, so the error lands on the profile's error route.
    result = await _callback(auth, router, state, cookies={})
    location = result.headers["location"]
    assert location == "https://console.example.com/auth/oauth/error?oauth_error=invalid_state"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_flow_without_app_uses_constructor_urls(
    auth_instance: SimpleRBAC, monkeypatch: pytest.MonkeyPatch
):
    auth = auth_instance
    router = _login_router(auth)

    state = await _authorize(auth, router, app_key=None)
    _patch_user_info(monkeypatch, oauth_router_module, "legacy@example.com", "gh-legacy")
    cookies = await _cookies_for(auth, state, app_key=None)
    result = await _callback(auth, router, state, cookies)
    assert result.headers["location"].startswith("https://legacy.example/success#")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_callback_route_names_are_unique_per_mount(auth_instance: SimpleRBAC):
    auth = auth_instance
    app = FastAPI()
    app.include_router(
        get_oauth_router(
            DummyOAuthClient("github"),
            auth,
            STATE_SECRET,
            prefix="/a",
            redirect_url="https://api.example/a/cb",
        )
    )
    app.include_router(
        get_oauth_router(
            DummyOAuthClient("github"),
            auth,
            STATE_SECRET,
            prefix="/b",
            redirect_url="https://api.example/b/cb",
        )
    )
    assert app.url_path_for("oauth:github:a.callback") == "/a/callback"
    assert app.url_path_for("oauth:github:b.callback") == "/b/callback"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_associate_flow_lands_on_profile_association_route(
    auth_instance: SimpleRBAC, monkeypatch: pytest.MonkeyPatch
):
    auth = auth_instance
    async with auth.get_session() as session:
        user = await auth.user_service.create_user(
            session=session, email="linker@example.com", password="LinkerPass123!"
        )
        await session.commit()
        user_id = str(user.id)

    router = get_oauth_associate_router(
        DummyOAuthClient("github"),
        auth,
        STATE_SECRET,
        prefix="/v1/oauth-associate/github",
        redirect_url="https://api.example/oauth-associate/github/callback",
        success_redirect_url="https://legacy.example/settings",
    )

    # A profile with no association landing is rejected up front.
    authorize_ep = _endpoint(router, "/authorize", "GET")
    with pytest.raises(HTTPException) as unsupported:
        async with auth.get_session() as session:
            await authorize_ep(
                request=_request(),
                response=Response(),
                session=session,
                auth_context={"user_id": user_id},
                scopes=None,
                app="portal",
            )
    assert unsupported.value.status_code == 400

    async with auth.get_session() as session:
        result = await authorize_ep(
            request=_request(),
            response=Response(),
            session=session,
            auth_context={"user_id": user_id},
            scopes=None,
            app="console",
        )
    state = _state_from(result)
    payload = decode_state_token(state, STATE_SECRET)
    assert payload["app"] == "console"
    assert payload["sub"] == user_id

    _patch_user_info(monkeypatch, oauth_associate_module, "linker@example.com", "gh-linker")
    cookies = await _cookies_for(auth, state, flow="associate", app_key="console")
    callback_ep = _endpoint(router, "/callback", "GET")
    token = {"access_token": "provider-token", "refresh_token": None, "expires_at": None}
    async with auth.get_session() as session:
        response = await callback_ep(
            request=_request(cookies),
            response=Response(),
            session=session,
            access_token_state=(token, state),
        )
    assert response.headers["location"] == "https://console.example.com/settings/connections?linked=github"
