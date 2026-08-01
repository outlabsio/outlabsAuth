"""
Authorization security regression tests (privilege-escalation chain).

End-to-end HTTP coverage for the Critical/High findings patched from
docs/SECURITY_AUDIT_2026-06-10.md:

- SEC-2: assigning a role grants its permissions — a non-superuser may only
  assign a role whose permissions they already hold.
- SEC-3: a non-superuser may only attach permissions to a role that they
  themselves hold (no minting `*:*` onto a role you can edit).
- SEC-1: a refresh token must not authenticate as an access token.

The "limited admin" here models the dangerous real-world case: a scoped admin
who legitimately holds ``role:update`` / ``user:update`` but must not be able to
escalate to permissions they were never granted (e.g. ``user:delete``).
"""

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import (
    get_auth_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)
from outlabs_auth.utils.jwt import create_access_token, create_refresh_token

ALL_PERMISSIONS = [
    "user:read",
    "user:update",
    "user:delete",
    "role:read",
    "role:create",
    "role:update",
]

# Permissions the limited admin legitimately holds — note: NO user:delete.
LIMITED_ADMIN_PERMISSIONS = ["user:read", "user:update", "role:read", "role:create", "role:update"]


@pytest_asyncio.fixture
async def auth_instance(test_engine):
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
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
    app.include_router(get_roles_router(auth_instance, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth_instance, prefix="/v1/permissions"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


def _token(auth_instance: SimpleRBAC, user) -> str:
    return create_access_token(
        {"sub": str(user.id)},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )


@pytest_asyncio.fixture
async def scenario(auth_instance: SimpleRBAC) -> dict:
    """Seed permissions, a limited admin, a superuser, and roles/users to act on.

    Seeding goes through the services directly (not the HTTP guard), which is the
    intended bootstrap path — the guard only applies to runtime API callers.
    """
    async with auth_instance.get_session() as session:
        for name in ALL_PERMISSIONS:
            await auth_instance.permission_service.create_permission(
                session, name=name, display_name=name, description=name
            )

        # Limited admin: can manage roles + update users, but does NOT hold user:delete.
        admin_role = await auth_instance.role_service.create_role(
            session, name="limited_admin", display_name="Limited Admin", description="scoped admin"
        )
        await auth_instance.role_service.add_permissions_by_name(
            session, admin_role.id, LIMITED_ADMIN_PERMISSIONS
        )
        limited = await auth_instance.user_service.create_user(
            session=session,
            email="limited@example.com",
            password="TestPass123!",
            first_name="Limited",
            last_name="Admin",
            is_superuser=False,
        )
        await auth_instance.role_service.assign_role_to_user(session, limited.id, admin_role.id)

        superuser = await auth_instance.user_service.create_user(
            session=session,
            email="super@example.com",
            password="TestPass123!",
            first_name="Super",
            last_name="User",
            is_superuser=True,
        )

        # An empty role the limited admin will try to edit (SEC-3).
        target_role = await auth_instance.role_service.create_role(
            session, name="target_role", display_name="Target", description="editable role"
        )

        # A powerful role carrying user:delete — used for the assignment test (SEC-2).
        powerful_role = await auth_instance.role_service.create_role(
            session, name="powerful_role", display_name="Powerful", description="carries user:delete"
        )
        await auth_instance.role_service.add_permissions_by_name(
            session, powerful_role.id, ["user:delete"]
        )

        victim = await auth_instance.user_service.create_user(
            session=session,
            email="victim@example.com",
            password="TestPass123!",
            first_name="Victim",
            last_name="User",
            is_superuser=False,
        )

        await session.commit()

        return {
            "limited_token": _token(auth_instance, limited),
            "super_token": _token(auth_instance, superuser),
            "limited_id": str(limited.id),
            "target_role_id": str(target_role.id),
            "powerful_role_id": str(powerful_role.id),
            "victim_id": str(victim.id),
        }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# SEC-3 — role permission editing requires delegation containment
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_limited_admin_cannot_add_permission_they_lack(client, scenario):
    """A role:update holder cannot attach user:delete (which they do not hold)."""
    resp = await client.post(
        f"/v1/roles/{scenario['target_role_id']}/permissions",
        json=["user:delete"],
        headers=_auth(scenario["limited_token"]),
    )
    assert resp.status_code == 403
    # The response should tell the caller which permission they lacked.
    assert "user:delete" in resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_limited_admin_can_add_permission_they_hold(client, scenario):
    """Containment must not over-block: a held permission can still be granted."""
    resp = await client.post(
        f"/v1/roles/{scenario['target_role_id']}/permissions",
        json=["user:update"],
        headers=_auth(scenario["limited_token"]),
    )
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_add_any_permission(client, scenario):
    """Superusers bypass containment (get_user_permissions returns ['*:*'])."""
    resp = await client.post(
        f"/v1/roles/{scenario['target_role_id']}/permissions",
        json=["user:delete"],
        headers=_auth(scenario["super_token"]),
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SEC-2 — assigning a role requires holding the role's permissions
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_limited_admin_cannot_assign_role_carrying_unheld_permission(client, scenario):
    """user:update is not enough to assign a role that grants user:delete."""
    resp = await client.post(
        f"/v1/users/{scenario['victim_id']}/roles",
        json={"role_id": scenario["powerful_role_id"]},
        headers=_auth(scenario["limited_token"]),
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_superuser_can_assign_powerful_role(client, scenario):
    resp = await client.post(
        f"/v1/users/{scenario['victim_id']}/roles",
        json={"role_id": scenario["powerful_role_id"]},
        headers=_auth(scenario["super_token"]),
    )
    assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# SEC-1 — a refresh token must not authenticate as an access token
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_token_authenticates_control(client, scenario):
    """Control: the limited admin's access token is accepted on a protected route."""
    resp = await client.get("/v1/users/", headers=_auth(scenario["limited_token"]))
    assert resp.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_token_rejected_as_bearer(client, scenario, auth_instance):
    refresh = create_refresh_token(
        {"sub": scenario["limited_id"]},
        secret_key=auth_instance.config.secret_key,
        algorithm=auth_instance.config.algorithm,
    )
    resp = await client.get("/v1/users/", headers=_auth(refresh))
    assert resp.status_code == 401
