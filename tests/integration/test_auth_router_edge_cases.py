import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_auth_router, get_users_router


class FakeRedis:
    def __init__(self) -> None:
        self.is_available = True
        self.calls: list[tuple[str, str, int | None]] = []

    async def set(self, key: str, value: str, ttl: int | None = None):
        self.calls.append((key, value, ttl))
        return True

    async def disconnect(self) -> None:
        return None


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
        enable_token_cleanup=False,
        enable_token_blacklist=True,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def app(auth_instance: SimpleRBAC) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


async def _create_user(auth_instance: SimpleRBAC, *, email_prefix: str = "edge") -> dict:
    password = "TestPass123!"
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session,
            email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
            password=password,
            first_name="Edge",
            last_name="Case",
        )
        await session.commit()
        return {"id": str(user.id), "email": user.email, "password": password}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_can_revoke_one_session_without_touching_another(
    client: httpx.AsyncClient,
    auth_instance: SimpleRBAC,
):
    fake_redis = FakeRedis()
    auth_instance.redis_client = fake_redis
    user = await _create_user(auth_instance, email_prefix="single-logout")

    first_login = await client.post(
        "/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert first_login.status_code == 200, first_login.text
    first_tokens = first_login.json()

    second_login = await client.post(
        "/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert second_login.status_code == 200, second_login.text
    second_tokens = second_login.json()

    logout_response = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
        json={"refresh_token": first_tokens["refresh_token"], "immediate": True},
    )
    assert logout_response.status_code == 204, logout_response.text
    assert len(fake_redis.calls) == 1
    assert fake_redis.calls[0][0].startswith("blacklist:jwt:")

    revoked_refresh = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": first_tokens["refresh_token"]},
    )
    assert revoked_refresh.status_code == 401, revoked_refresh.text

    still_valid_refresh = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": second_tokens["refresh_token"]},
    )
    assert still_valid_refresh.status_code == 200, still_valid_refresh.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logout_all_sessions_immediate_blacklists_current_access_token(
    client: httpx.AsyncClient,
    auth_instance: SimpleRBAC,
):
    fake_redis = FakeRedis()
    auth_instance.redis_client = fake_redis
    user = await _create_user(auth_instance, email_prefix="all-logout")

    login_response = await client.post(
        "/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert login_response.status_code == 200, login_response.text
    tokens = login_response.json()

    logout_response = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"immediate": True},
    )
    assert logout_response.status_code == 204, logout_response.text
    assert len(fake_redis.calls) == 1
    assert fake_redis.calls[0][0].startswith("blacklist:jwt:")

    refresh_response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401, refresh_response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_is_silent_for_unknown_users_and_hook_failures(
    client: httpx.AsyncClient,
    auth_instance: SimpleRBAC,
):
    unknown_response = await client.post(
        "/v1/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert unknown_response.status_code == 204, unknown_response.text

    user = await _create_user(auth_instance, email_prefix="forgot-hook")

    async def fail_after_forgot_password(user_obj, token, request=None):
        raise RuntimeError("email backend unavailable")

    auth_instance.user_service.on_after_forgot_password = fail_after_forgot_password

    failing_hook_response = await client.post(
        "/v1/auth/forgot-password",
        json={"email": user["email"]},
    )
    assert failing_hook_response.status_code == 204, failing_hook_response.text

    async with auth_instance.get_session() as session:
        stored_user = await auth_instance.user_service.get_user_by_email(session, user["email"])
        assert stored_user is not None
        assert stored_user.password_reset_token is not None
        assert stored_user.password_reset_expires is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_returns_retry_metadata_when_rate_limited(
    client: httpx.AsyncClient,
    monkeypatch,
):
    async def fake_rate_limit(email: str, redis_client=None):
        return True, 90

    monkeypatch.setattr("outlabs_auth.routers.auth.check_forgot_password_rate_limit", fake_rate_limit)

    response = await client.post(
        "/v1/auth/forgot-password",
        json={"email": "limited@example.com"},
    )
    assert response.status_code == 429, response.text
    payload = response.json()
    assert payload["details"]["retry_after_seconds"] == 90
    assert payload["details"]["retry_after_minutes"] == 1.5
