import uuid
from typing import Type

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from outlabs_auth import EnterpriseRBAC, SimpleRBAC
from outlabs_auth.core.auth import OutlabsAuth
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.models.sql.auth_challenge import AuthChallenge
from outlabs_auth.routers import get_auth_router, get_users_router


def _build_app(auth: OutlabsAuth) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    return app


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_cls", "preset"),
    [(SimpleRBAC, "SimpleRBAC"), (EnterpriseRBAC, "EnterpriseRBAC")],
)
async def test_magic_link_request_and_verify_flow_works_for_presets(
    test_engine,
    auth_cls: Type[OutlabsAuth],
    preset: str,
):
    auth = auth_cls(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_magic_links=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        captured: dict[str, str] = {}

        async def capture_magic_link(user, token, request=None, redirect_url=None):
            captured["user_id"] = str(user.id)
            captured["email"] = user.email
            captured["token"] = token
            captured["redirect_url"] = redirect_url

        auth.user_service.on_after_magic_link_requested = capture_magic_link

        async with auth.get_session() as session:
            user = await auth.user_service.create_user(
                session=session,
                email=f"magic-{preset.lower()}-{uuid.uuid4().hex[:8]}@example.com",
                password="MagicPass123!",
                first_name="Magic",
                last_name="User",
            )
            await session.commit()
            user_email = user.email
            user_id = str(user.id)

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            config_response = await client.get("/v1/auth/config")
            assert config_response.status_code == 200, config_response.text
            config_payload = config_response.json()
            assert config_payload["preset"] == preset
            assert config_payload["features"]["magic_links"] is True
            assert config_payload["auth_methods"]["password"] is True
            assert config_payload["auth_methods"]["magic_link"] is True

            request_response = await client.post(
                "/v1/auth/magic-link/request",
                json={
                    "email": user_email,
                    "redirect_url": "/app/dashboard",
                },
            )
            assert request_response.status_code == 204, request_response.text
            assert captured["user_id"] == user_id
            assert captured["email"] == user_email
            assert captured["token"]
            assert captured["redirect_url"] == "/app/dashboard"

            verify_response = await client.post(
                "/v1/auth/magic-link/verify",
                json={"token": captured["token"]},
            )
            assert verify_response.status_code == 200, verify_response.text
            tokens = verify_response.json()
            assert tokens["access_token"]
            assert tokens["refresh_token"]

            current_user_response = await client.get(
                "/v1/users/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            assert current_user_response.status_code == 200, current_user_response.text
            assert current_user_response.json()["email"] == user_email

            replay_response = await client.post(
                "/v1/auth/magic-link/verify",
                json={"token": captured["token"]},
            )
            assert replay_response.status_code == 401, replay_response.text

        async with auth.get_session() as session:
            refreshed_user = await auth.user_service.get_user_by_email(session, user_email)
            assert refreshed_user is not None
            assert refreshed_user.email_verified is True
            assert "MAGIC_LINK" in refreshed_user.auth_methods
            assert refreshed_user.last_login is not None

            challenges = (
                (await session.execute(select(AuthChallenge).where(AuthChallenge.user_id == refreshed_user.id)))
                .scalars()
                .all()
            )
            assert len(challenges) == 1
            assert challenges[0].used_at is not None
            assert challenges[0].token_hash != captured["token"]
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_magic_link_disabled_is_not_advertised_or_usable(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            config_response = await client.get("/v1/auth/config")
            assert config_response.status_code == 200, config_response.text
            config_payload = config_response.json()
            assert config_payload["features"]["magic_links"] is False
            assert config_payload["auth_methods"]["magic_link"] is False

            request_response = await client.post(
                "/v1/auth/magic-link/request",
                json={"email": "disabled@example.com"},
            )
            assert request_response.status_code == 404, request_response.text

            verify_response = await client.post(
                "/v1/auth/magic-link/verify",
                json={"token": "not-enabled"},
            )
            assert verify_response.status_code == 404, verify_response.text
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_magic_link_request_does_not_reveal_unknown_or_inactive_accounts(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_magic_links=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        captured: list[str] = []

        async def capture_magic_link(user, token, request=None, redirect_url=None):
            captured.append(token)

        auth.user_service.on_after_magic_link_requested = capture_magic_link

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            missing_response = await client.post(
                "/v1/auth/magic-link/request",
                json={"email": "missing@example.com"},
            )
            assert missing_response.status_code == 204, missing_response.text
            assert captured == []
    finally:
        await auth.shutdown()
