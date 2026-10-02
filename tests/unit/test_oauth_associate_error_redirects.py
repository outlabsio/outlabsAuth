"""OAuth account-link failures land back on the SPA (F-104).

Before 0.1.0a35 a failed associate callback answered raw JSON on the API
origin, stranding the browser. With a landing URL configured, failures now
redirect with ``?link_error=<code>&provider=<name>``; without one, API
clients keep the JSON errors.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

import outlabs_auth.routers.oauth_associate as oauth_associate_module
from outlabs_auth.oauth.state import generate_state_token
from outlabs_auth.routers.oauth_associate import get_oauth_associate_router

STATE_SECRET = "oauth-associate-secret"


class _OAuthClient:
    name = "github"

    async def get_authorization_url(self, *args, **kwargs) -> str:  # pragma: no cover - unused
        return "https://oauth.example/github"


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, execute_results=None) -> None:
        self._results = list(execute_results or [])
        self.execute = AsyncMock(side_effect=self._next)
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.add = Mock()

    async def _next(self, stmt):
        return self._results.pop(0)


def _auth(user=None) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(store_oauth_provider_tokens=False),
        deps=SimpleNamespace(require_auth=lambda **kwargs: lambda: None),
        uow=None,
        user_service=SimpleNamespace(
            get_user_by_id=AsyncMock(return_value=user),
            on_after_oauth_associate=AsyncMock(),
        ),
    )


def _callback(auth, **router_kwargs):
    router = get_oauth_associate_router(
        _OAuthClient(),
        auth,
        state_secret=STATE_SECRET,
        prefix="/v1/oauth-associate/github",
        redirect_url="https://api.example.com/v1/oauth-associate/github/callback",
        **router_kwargs,
    )
    for route in router.routes:
        if route.path == "/v1/oauth-associate/github/callback":
            return route.endpoint
    raise AssertionError("callback route missing")


def _state(user_id) -> str:
    return generate_state_token({"sub": str(user_id)}, STATE_SECRET, lifetime_seconds=600)


def _query(location: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(location).query)


@pytest.fixture(autouse=True)
def _stub_state_store_and_provider(monkeypatch: pytest.MonkeyPatch):
    fastapi_module = ModuleType("httpx_oauth.integrations.fastapi")
    fastapi_module.OAuth2AuthorizeCallback = object
    integrations_module = ModuleType("httpx_oauth.integrations")
    integrations_module.fastapi = fastapi_module
    httpx_oauth_module = ModuleType("httpx_oauth")
    httpx_oauth_module.integrations = integrations_module
    monkeypatch.setitem(sys.modules, "httpx_oauth", httpx_oauth_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations", integrations_module)
    monkeypatch.setitem(sys.modules, "httpx_oauth.integrations.fastapi", fastapi_module)
    monkeypatch.setattr(oauth_associate_module, "issue_oauth_state", AsyncMock())
    monkeypatch.setattr(oauth_associate_module, "consume_oauth_state", AsyncMock())

    async def _user_info(oauth_client, token):
        return SimpleNamespace(provider_user_id="provider-user", email="linked@example.com", email_verified=True)

    monkeypatch.setattr(oauth_associate_module, "get_oauth_user_info", _user_info)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_cancel_redirects_with_cancelled_code():
    callback = _callback(_auth(), success_redirect_url="https://app.example.com/app/account")
    response = await callback(
        request=SimpleNamespace(),
        response=Response(),
        session=_Session(),
        code=None,
        state=None,
        error="access_denied",
        access_token_state=None,
    )
    assert response.status_code == 302
    query = _query(response.headers["location"])
    assert query == {"link_error": ["cancelled"], "provider": ["github"]}
    assert response.headers["location"].startswith("https://app.example.com/app/account?")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_state_redirects_with_invalid_state_code():
    callback = _callback(_auth(), success_redirect_url="https://app.example.com/app/account")
    response = await callback(
        request=SimpleNamespace(),
        response=Response(),
        session=_Session(),
        access_token_state=({"access_token": "token"}, "not-a-valid-state"),
    )
    assert response.status_code == 302
    assert _query(response.headers["location"])["link_error"] == ["invalid_state"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_account_linked_to_another_user_redirects_with_already_linked():
    user = SimpleNamespace(id=uuid4(), auth_methods=["PASSWORD"])
    other_link = SimpleNamespace(user_id=uuid4())
    callback = _callback(
        _auth(user),
        success_redirect_url="https://app.example.com/app/account",
        error_redirect_url="https://app.example.com/app/account/linking-failed",
    )
    response = await callback(
        request=SimpleNamespace(),
        response=Response(),
        session=_Session(execute_results=[_Scalar(other_link)]),
        access_token_state=({"access_token": "token"}, _state(user.id)),
    )
    assert response.status_code == 302
    location = response.headers["location"]
    # The explicit error landing wins over the success landing.
    assert location.startswith("https://app.example.com/app/account/linking-failed?")
    assert _query(location)["link_error"] == ["already_linked"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_user_redirects_with_auth_code():
    callback = _callback(_auth(None), success_redirect_url="https://app.example.com/app/account?tab=security")
    response = await callback(
        request=SimpleNamespace(),
        response=Response(),
        session=_Session(),
        access_token_state=({"access_token": "token"}, _state(uuid4())),
    )
    assert response.status_code == 302
    query = _query(response.headers["location"])
    assert query["link_error"] == ["auth"]
    assert query["tab"] == ["security"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_without_landing_urls_errors_stay_json():
    callback = _callback(_auth(None))
    with pytest.raises(HTTPException) as exc_info:
        await callback(
            request=SimpleNamespace(),
            response=Response(),
            session=_Session(),
            access_token_state=({"access_token": "token"}, _state(uuid4())),
        )
    assert exc_info.value.status_code == 401
