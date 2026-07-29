"""Integration tests for DD-059 slice 4: azp provenance + audience-gated sign-in.

Partitioned profiles reject off-audience sign-ins with a stable 403
``wrong_application`` at every minting path; sessions carry the profile key
as the ``azp`` claim, preserved and re-gated across refresh rotation; and
``require_app`` enforces app-scoped endpoint families.
"""

import uuid
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.frontend import (
    FrontendProfile,
    FrontendProfileRegistry,
    FrontendProfileResolver,
    FrontendRoutes,
    require_app,
    route_by_root_entity_slug,
)
from outlabs_auth.messaging.types import MessageDeliveryResult
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.utils.jwt import verify_token

SECRET = "test-secret-key-do-not-use-in-production-12345678"


class CapturingMessagingService:
    def __init__(self) -> None:
        self.intents: list[Any] = []

    async def send_auth_challenge(self, intent: Any) -> MessageDeliveryResult:
        self.intents.append(intent)
        return MessageDeliveryResult.queued("capture")


def _registry() -> FrontendProfileRegistry:
    routes = FrontendRoutes(
        login="/login",
        password_reset="/recovery/{token}",
        magic_link="/auth/magic-link?token={token}",
    )
    return FrontendProfileRegistry(
        [
            FrontendProfile(
                key="console",
                app_name="Console",
                public_origins=("https://console.example.com",),
                routes=routes,
                accepted_audiences=("console",),
            ),
            FrontendProfile(
                key="portal",
                app_name="Portal",
                public_origins=("https://portal.example.com",),
                routes=routes,
                accepted_audiences=("portal",),
            ),
            FrontendProfile(
                key="shared",
                app_name="Shared",
                public_origins=("https://shared.example.com",),
                routes=routes,
                # no accepted_audiences: the shared/SSO mode accepts everyone
            ),
        ]
    )


@pytest_asyncio.fixture
async def gated_auth(test_engine) -> EnterpriseRBAC:
    messaging = CapturingMessagingService()
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key=SECRET,
        access_token_expire_minutes=15,
        enable_token_cleanup=False,
        enable_magic_links=True,
        transactional_messaging_service=messaging,
        frontend_resolver=FrontendProfileResolver(
            _registry(),
            route_by_root_entity_slug({"internal-org": "console", "agent-practice": "portal"}),
        ),
    )
    await auth.initialize()
    auth.test_messaging = messaging
    yield auth
    await auth.shutdown()


def _app(auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))

    scoped_dependency = require_app(auth, "console")

    @app.get("/console-only")
    async def console_only(_ctx: Any = Depends(scoped_dependency)) -> dict[str, bool]:
        return {"ok": True}

    return app


async def _seed_users(auth: EnterpriseRBAC) -> dict[str, dict[str, str]]:
    suffix = uuid.uuid4().hex[:8]
    users = {
        "admin": {"email": f"admin-{suffix}@example.com", "password": "AdminPass123!"},
        "agent": {"email": f"agent-{suffix}@example.com", "password": "AgentPass123!"},
    }
    async with auth.get_session() as session:
        internal = await auth.entity_service.create_entity(
            session=session,
            name=f"internal-org-{suffix}",
            display_name="Internal Org",
            slug="internal-org",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        practice = await auth.entity_service.create_entity(
            session=session,
            name=f"agent-practice-{suffix}",
            display_name="Agent Practice",
            slug="agent-practice",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        admin = await auth.user_service.create_user(
            session=session, email=users["admin"]["email"], password=users["admin"]["password"]
        )
        agent = await auth.user_service.create_user(
            session=session, email=users["agent"]["email"], password=users["agent"]["password"]
        )
        membership_service = MembershipService(auth.config)
        await membership_service.add_member(session=session, entity_id=internal.id, user_id=admin.id)
        await membership_service.add_member(session=session, entity_id=practice.id, user_id=agent.id)
        await session.commit()
    return users


def _azp(token: str) -> Any:
    payload = verify_token(token, SECRET, "HS256", expected_type="access", audience="outlabs-auth")
    return payload.get("azp")


async def _login(client, creds: dict[str, str], app_key=None):
    body = {"email": creds["email"], "password": creds["password"]}
    if app_key is not None:
        body["app"] = app_key
    return await client.post("/v1/auth/login", json=body)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_partitioned_login_gates_and_stamps_azp(gated_auth):
    auth = gated_auth
    users = await _seed_users(auth)
    transport = httpx.ASGITransport(app=_app(auth))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await _login(client, users["admin"], "console")
        assert ok.status_code == 200, ok.text
        assert _azp(ok.json()["access_token"]) == "console"

        rejected = await _login(client, users["agent"], "console")
        assert rejected.status_code == 403, rejected.text
        # register_exception_handlers envelopes dict details under "details".
        assert rejected.json()["details"]["code"] == "wrong_application"

        own_app = await _login(client, users["agent"], "portal")
        assert own_app.status_code == 200, own_app.text
        assert _azp(own_app.json()["access_token"]) == "portal"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_appless_and_shared_modes_accept_everyone(gated_auth):
    auth = gated_auth
    users = await _seed_users(auth)
    transport = httpx.ASGITransport(app=_app(auth))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        legacy = await _login(client, users["agent"])
        assert legacy.status_code == 200
        assert _azp(legacy.json()["access_token"]) is None

        shared = await _login(client, users["agent"], "shared")
        assert shared.status_code == 200
        assert _azp(shared.json()["access_token"]) == "shared"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_rotation_preserves_and_regates_azp(gated_auth):
    auth = gated_auth
    users = await _seed_users(auth)
    transport = httpx.ASGITransport(app=_app(auth))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await _login(client, users["admin"], "console")
        assert login.status_code == 200
        refreshed = await client.post(
            "/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
        )
        assert refreshed.status_code == 200, refreshed.text
        assert _azp(refreshed.json()["access_token"]) == "console"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_magic_link_verify_mints_challenge_bound_azp(gated_auth):
    auth = gated_auth
    users = await _seed_users(auth)
    transport = httpx.ASGITransport(app=_app(auth))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        request = await client.post(
            "/v1/auth/magic-link/request",
            json={"email": users["admin"]["email"], "app": "console"},
        )
        assert request.status_code == 204, request.text
        assert len(auth.test_messaging.intents) == 1
        secret = auth.test_messaging.intents[0].secret

        verify = await client.post("/v1/auth/magic-link/verify", json={"token": secret})
        assert verify.status_code == 200, verify.text
        assert _azp(verify.json()["access_token"]) == "console"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_require_app_enforces_app_scoped_endpoints(gated_auth):
    auth = gated_auth
    users = await _seed_users(auth)
    transport = httpx.ASGITransport(app=_app(auth))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        console_token = (await _login(client, users["admin"], "console")).json()["access_token"]
        portal_token = (await _login(client, users["agent"], "portal")).json()["access_token"]
        appless_token = (await _login(client, users["admin"])).json()["access_token"]

        allowed = await client.get(
            "/console-only", headers={"Authorization": f"Bearer {console_token}"}
        )
        assert allowed.status_code == 200, allowed.text

        wrong_app = await client.get(
            "/console-only", headers={"Authorization": f"Bearer {portal_token}"}
        )
        assert wrong_app.status_code == 403
        assert wrong_app.json()["details"]["code"] == "wrong_application"

        appless = await client.get(
            "/console-only", headers={"Authorization": f"Bearer {appless_token}"}
        )
        assert appless.status_code == 403
