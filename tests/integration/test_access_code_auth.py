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
from outlabs_auth.models.sql.enums import AuthChallengeType
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
async def test_access_code_request_and_verify_flow_works_for_presets(
    test_engine,
    auth_cls: Type[OutlabsAuth],
    preset: str,
):
    auth = auth_cls(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_access_codes=True,
        access_code_length=6,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        captured: dict[str, str] = {}

        async def capture_access_code(user, code, request=None, redirect_url=None):
            captured["user_id"] = str(user.id)
            captured["email"] = user.email
            captured["code"] = code
            captured["redirect_url"] = redirect_url

        auth.user_service.on_after_access_code_requested = capture_access_code

        async with auth.get_session() as session:
            user = await auth.user_service.create_user(
                session=session,
                email=f"access-code-{preset.lower()}-{uuid.uuid4().hex[:8]}@example.com",
                password="AccessCodePass123!",
                first_name="Access",
                last_name="Code",
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
            assert config_payload["features"]["access_codes"] is True
            assert config_payload["features"]["magic_links"] is False
            assert config_payload["auth_methods"]["password"] is True
            assert config_payload["auth_methods"]["access_code"] is True
            assert config_payload["auth_methods"]["magic_link"] is False

            request_response = await client.post(
                "/v1/auth/access-code/request",
                json={
                    "email": user_email,
                    "redirect_url": "/app/dashboard",
                },
            )
            assert request_response.status_code == 204, request_response.text
            assert captured["user_id"] == user_id
            assert captured["email"] == user_email
            assert captured["code"].isdigit()
            assert len(captured["code"]) == 6
            assert captured["redirect_url"] == "/app/dashboard"

            pasted_code = f"{captured['code'][:3]}-{captured['code'][3:]}"
            verify_response = await client.post(
                "/v1/auth/access-code/verify",
                json={"email": user_email, "code": pasted_code},
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
                "/v1/auth/access-code/verify",
                json={"email": user_email, "code": captured["code"]},
            )
            assert replay_response.status_code == 401, replay_response.text

        async with auth.get_session() as session:
            refreshed_user = await auth.user_service.get_user_by_email(session, user_email)
            assert refreshed_user is not None
            assert refreshed_user.email_verified is True
            assert "ACCESS_CODE" in refreshed_user.auth_methods
            assert refreshed_user.last_login is not None

            challenges = (
                (
                    await session.execute(
                        select(AuthChallenge).where(
                            AuthChallenge.user_id == refreshed_user.id,
                            AuthChallenge.challenge_type == AuthChallengeType.ACCESS_CODE.value,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(challenges) == 1
            assert challenges[0].used_at is not None
            assert challenges[0].token_hash != captured["code"]
            assert captured["code"] not in challenges[0].token_hash
            assert challenges[0].token_hash.startswith("v1:")
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_code_disabled_is_not_advertised_or_usable(test_engine):
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
            assert config_payload["features"]["access_codes"] is False
            assert config_payload["auth_methods"]["access_code"] is False

            request_response = await client.post(
                "/v1/auth/access-code/request",
                json={"email": "disabled@example.com"},
            )
            assert request_response.status_code == 404, request_response.text

            verify_response = await client.post(
                "/v1/auth/access-code/verify",
                json={"email": "disabled@example.com", "code": "123456"},
            )
            assert verify_response.status_code == 404, verify_response.text
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_code_request_rate_limit_returns_retry_metadata(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_access_codes=True,
        access_code_request_rate_limit_max=1,
        access_code_request_rate_limit_window_seconds=300,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        email = f"limited-access-code-{uuid.uuid4().hex[:8]}@example.com"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first_response = await client.post(
                "/v1/auth/access-code/request",
                json={"email": email},
            )
            assert first_response.status_code == 204, first_response.text

            limited_response = await client.post(
                "/v1/auth/access-code/request",
                json={"email": email},
            )
            assert limited_response.status_code == 429, limited_response.text
            assert limited_response.headers["Retry-After"]
            payload = limited_response.json()
            detail = payload.get("details") or payload.get("detail")
            assert detail["retry_after_seconds"] >= 1
            assert detail["retry_after_minutes"] > 0
    finally:
        await auth.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_code_request_does_not_reveal_unknown_or_inactive_accounts(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        enable_access_codes=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        captured: list[str] = []

        async def capture_access_code(user, code, request=None, redirect_url=None):
            captured.append(code)

        auth.user_service.on_after_access_code_requested = capture_access_code

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            missing_response = await client.post(
                "/v1/auth/access-code/request",
                json={"email": "missing@example.com"},
            )
            assert missing_response.status_code == 204, missing_response.text
            assert captured == []
    finally:
        await auth.shutdown()
