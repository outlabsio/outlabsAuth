import uuid

import httpx
import pytest
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_auth_router, get_users_router


def _build_app(auth) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    return app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_and_revoke_user_sessions(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        store_refresh_tokens=True,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        password = "SessionPass123!"
        async with auth.get_session() as session:
            admin = await auth.user_service.create_user(
                session=session,
                email=f"sessions-admin-{uuid.uuid4().hex[:8]}@example.com",
                password=password,
                first_name="Session",
                last_name="Admin",
                is_superuser=True,
            )
            target = await auth.user_service.create_user(
                session=session,
                email=f"sessions-target-{uuid.uuid4().hex[:8]}@example.com",
                password=password,
                first_name="Session",
                last_name="Target",
            )
            await session.commit()
            admin_email = admin.email
            target_id = str(target.id)
            target_email = target.email

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            target_login = await client.post(
                "/v1/auth/login",
                json={"email": target_email, "password": password},
            )
            assert target_login.status_code == 200, target_login.text
            target_tokens = target_login.json()
            refresh_token = target_tokens["refresh_token"]

            me_sessions = await client.get(
                "/v1/users/me/sessions",
                headers={"Authorization": f"Bearer {target_tokens['access_token']}"},
            )
            assert me_sessions.status_code == 200, me_sessions.text
            me_items = me_sessions.json()
            assert len(me_items) >= 1
            session_id = me_items[0]["id"]
            assert "token_hash" not in me_items[0]

            admin_login = await client.post(
                "/v1/auth/login",
                json={"email": admin_email, "password": password},
            )
            assert admin_login.status_code == 200, admin_login.text
            admin_token = admin_login.json()["access_token"]

            admin_list = await client.get(
                f"/v1/users/{target_id}/sessions",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert admin_list.status_code == 200, admin_list.text
            assert any(item["id"] == session_id for item in admin_list.json())

            revoke = await client.delete(
                f"/v1/users/{target_id}/sessions/{session_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert revoke.status_code == 204, revoke.text

            refresh_after = await client.post(
                "/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            assert refresh_after.status_code == 401, refresh_after.text

            empty_list = await client.get(
                f"/v1/users/{target_id}/sessions",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert empty_list.status_code == 200, empty_list.text
            assert empty_list.json() == []

            # Create two sessions, then revoke all via /me
            login_a = await client.post(
                "/v1/auth/login",
                json={"email": target_email, "password": password},
            )
            login_b = await client.post(
                "/v1/auth/login",
                json={"email": target_email, "password": password},
            )
            assert login_a.status_code == 200
            assert login_b.status_code == 200
            access_b = login_b.json()["access_token"]

            listed = await client.get(
                "/v1/users/me/sessions",
                headers={"Authorization": f"Bearer {access_b}"},
            )
            assert listed.status_code == 200
            assert len(listed.json()) >= 2

            revoke_all = await client.delete(
                "/v1/users/me/sessions",
                headers={"Authorization": f"Bearer {access_b}"},
            )
            assert revoke_all.status_code == 204, revoke_all.text

            after_all = await client.get(
                f"/v1/users/{target_id}/sessions",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert after_all.status_code == 200
            assert after_all.json() == []
    finally:
        await auth.shutdown()
