import uuid

import httpx
import pytest
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_audit_router, get_auth_router, get_users_router


def _build_app(auth) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_audit_router(auth, prefix="/v1/audit-events"))
    return app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_events_search_returns_scoped_events(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    try:
        password = "AuditPass123!"
        async with auth.get_session() as session:
            admin = await auth.user_service.create_user(
                session=session,
                email=f"audit-admin-{uuid.uuid4().hex[:8]}@example.com",
                password=password,
                first_name="Audit",
                last_name="Admin",
                is_superuser=True,
            )
            await session.commit()
            admin_email = admin.email
            admin_id = admin.id

            if getattr(auth, "user_audit_service", None):
                await auth.user_audit_service.record_event(
                    session,
                    event_category="authentication",
                    event_type="user.sessions_revoked",
                    event_source="test",
                    subject_user_id=admin_id,
                    subject_email_snapshot=admin_email,
                    actor_user_id=admin_id,
                    reason="test event",
                )
                await session.commit()

        app = _build_app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/v1/auth/login",
                json={"email": admin_email, "password": password},
            )
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]

            response = await client.get(
                "/v1/audit-events",
                headers={"Authorization": f"Bearer {token}"},
                params={"category": "authentication", "limit": 20},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["total"] >= 1
            assert any(
                item["event_type"] == "user.sessions_revoked"
                for item in payload["items"]
            )
    finally:
        await auth.shutdown()
