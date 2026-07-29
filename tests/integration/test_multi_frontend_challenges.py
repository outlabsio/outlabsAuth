"""Integration tests for DD-059 slice 2: challenge flows with frontend profiles.

Magic-link and access-code requests resolve a frontend profile at request
time; the resolved profile + canonical return target persist on the challenge
row, reach the delivery intent, and come back from verification as
``next_url``. Fail-closed outcomes skip generation and delivery while the
outward 204 stays opaque. Hosts without profiles keep today's behavior.
"""

import uuid
from typing import Any, cast

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.frontend import (
    FrontendProfile,
    FrontendProfileRegistry,
    FrontendProfileResolver,
    FrontendRoutes,
    route_by_root_entity_slug,
)
from outlabs_auth.mail import (
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    MailDeliveryResult,
    TransactionalMailProvider,
)
from outlabs_auth.messaging.types import MessageDeliveryResult
from outlabs_auth.models.sql.auth_challenge import AuthChallenge
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router
from outlabs_auth.services.membership import MembershipService


class CapturingMessagingService:
    def __init__(self) -> None:
        self.intents: list[Any] = []

    async def send_auth_challenge(self, intent: Any) -> MessageDeliveryResult:
        self.intents.append(intent)
        return MessageDeliveryResult.queued("capture")


class RecordingMailProvider(TransactionalMailProvider):
    provider_name = "recording"

    def __init__(self) -> None:
        self.messages: list[Any] = []

    async def send(self, message: Any) -> MailDeliveryResult:
        self.messages.append(message)
        return MailDeliveryResult.queued(self.provider_name)


def _registry() -> FrontendProfileRegistry:
    return FrontendProfileRegistry(
        [
            FrontendProfile(
                key="console",
                app_name="Diverse Console",
                public_origins=("https://console.example.com",),
                routes=FrontendRoutes(
                    login="/login",
                    password_reset="/recovery/{token}",
                    accept_invite="/accept-invite?token={token}",
                    magic_link="/auth/magic-link?token={token}",
                ),
            ),
            FrontendProfile(
                key="portal",
                app_name="Agent Portal",
                public_origins=("https://portal.example.com",),
                routes=FrontendRoutes(
                    login="/sign-in",
                    password_reset="/recovery/{token}",
                    accept_invite=None,
                    magic_link=None,  # deliberately unsupported: dead-link guard
                ),
            ),
        ]
    )


@pytest_asyncio.fixture
async def challenge_auth(test_engine) -> EnterpriseRBAC:
    registry = _registry()
    resolver = FrontendProfileResolver(
        registry,
        route_by_root_entity_slug({"internal-org": "console", "agent-practice": "portal"}),
    )
    mail_provider = RecordingMailProvider()
    mail_service = ComposedAuthMailService(
        provider=mail_provider,
        composers={
            "console": DefaultAuthMailComposer.from_profile(registry.get("console")),
            "portal": DefaultAuthMailComposer.from_profile(registry.get("portal")),
        },
        resolver=resolver,
    )
    messaging = CapturingMessagingService()
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        enable_magic_links=True,
        enable_access_codes=True,
        transactional_mail_service=mail_service,
        transactional_messaging_service=messaging,
    )
    await auth.initialize()
    auth.test_messaging = messaging  # test handles
    auth.test_mail_provider = mail_provider
    yield auth
    await auth.shutdown()


def _app(auth: EnterpriseRBAC) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    return app


async def _seed_users(auth: EnterpriseRBAC) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    emails = {
        "admin": f"admin-{suffix}@example.com",
        "agent": f"agent-{suffix}@example.com",
        "noroot": f"noroot-{suffix}@example.com",
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
        admin = await auth.user_service.create_user(session=session, email=emails["admin"], password="AdminPass123!")
        agent = await auth.user_service.create_user(session=session, email=emails["agent"], password="AgentPass123!")
        await auth.user_service.create_user(session=session, email=emails["noroot"], password="NoRootPass123!")
        membership_service = MembershipService(auth.config)
        await membership_service.add_member(session=session, entity_id=internal.id, user_id=admin.id)
        await membership_service.add_member(session=session, entity_id=practice.id, user_id=agent.id)
        await session.commit()
    return emails


async def _challenge_rows_for(auth: EnterpriseRBAC, email: str) -> list[AuthChallenge]:
    async with auth.get_session() as session:
        result = await session.execute(
            select(AuthChallenge).where(cast(Any, AuthChallenge.recipient) == email)
        )
        return list(result.scalars().all())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_magic_link_resolves_profile_persists_and_returns_next_url(challenge_auth):
    auth = challenge_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/magic-link/request",
            json={"email": emails["admin"], "app": "console", "redirect_url": "/dashboard?tab=1"},
        )
        assert response.status_code == 204, response.text

        # Delivery intent carries the resolved profile + canonical target.
        assert len(auth.test_messaging.intents) == 1
        intent = auth.test_messaging.intents[0]
        assert intent.profile_id == "console"
        assert intent.next_url == "https://console.example.com/dashboard?tab=1"
        assert intent.root_entity_slug == "internal-org"

        # The challenge row persists both.
        rows = await _challenge_rows_for(auth, emails["admin"])
        assert len(rows) == 1
        assert rows[0].profile_id == "console"
        assert rows[0].next_url == "https://console.example.com/dashboard?tab=1"

        # Verification returns the canonical next_url with the tokens.
        verify = await client.post(
            "/v1/auth/magic-link/verify", json={"token": intent.secret}
        )
        assert verify.status_code == 200, verify.text
        payload = verify.json()
        assert payload["access_token"]
        assert payload["next_url"] == "https://console.example.com/dashboard?tab=1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_magic_link_disallowed_redirect_fails_closed(challenge_auth):
    auth = challenge_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/magic-link/request",
            json={"email": emails["admin"], "redirect_url": "https://evil.example/phish"},
        )
    assert response.status_code == 204
    assert auth.test_messaging.intents == []
    assert await _challenge_rows_for(auth, emails["admin"]) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_magic_link_unsupported_flow_and_unknown_app_fail_closed(challenge_auth):
    auth = challenge_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Portal user: profile resolves, but the portal declares no magic-link
        # landing route — a guaranteed dead link, so nothing is sent.
        portal_response = await client.post(
            "/v1/auth/magic-link/request", json={"email": emails["agent"]}
        )
        # Unknown requested app key: fails closed identically.
        unknown_response = await client.post(
            "/v1/auth/magic-link/request",
            json={"email": emails["admin"], "app": "nope"},
        )

    assert portal_response.status_code == 204
    assert unknown_response.status_code == 204
    assert auth.test_messaging.intents == []
    assert await _challenge_rows_for(auth, emails["agent"]) == []
    assert await _challenge_rows_for(auth, emails["admin"]) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_code_flow_returns_next_url_on_verify(challenge_auth):
    auth = challenge_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/access-code/request",
            json={"email": emails["admin"], "app": "console", "redirect_url": "/billing"},
        )
        assert response.status_code == 204, response.text
        assert len(auth.test_messaging.intents) == 1
        intent = auth.test_messaging.intents[0]
        assert intent.profile_id == "console"
        assert intent.next_url == "https://console.example.com/billing"

        verify = await client.post(
            "/v1/auth/access-code/verify",
            json={"email": emails["admin"], "code": intent.secret},
        )
        assert verify.status_code == 200, verify.text
        assert verify.json()["next_url"] == "https://console.example.com/billing"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_app_hint_selects_and_mismatch_fails_closed(challenge_auth):
    auth = challenge_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # No-root user naming a registered app: the requested key is honored
        # when identity has no opinion, so mail goes out console-branded.
        honored = await client.post(
            "/v1/auth/forgot-password", json={"email": emails["noroot"], "app": "console"}
        )
        # Identity-mapped user naming the CONTRADICTING app: hard mismatch,
        # fail closed, opaque 204.
        mismatch = await client.post(
            "/v1/auth/forgot-password", json={"email": emails["admin"], "app": "portal"}
        )

    assert honored.status_code == 204
    assert mismatch.status_code == 204
    provider = auth.test_mail_provider
    assert len(provider.messages) == 1
    assert provider.messages[0].to_email == emails["noroot"]
    assert "https://console.example.com/recovery/" in provider.messages[0].text_body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_host_without_profiles_keeps_raw_redirect_and_no_next_url(test_engine):
    messaging = CapturingMessagingService()
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        enable_magic_links=True,
        transactional_messaging_service=messaging,
    )
    await auth.initialize()
    try:
        suffix = uuid.uuid4().hex[:8]
        email = f"legacy-{suffix}@example.com"
        async with auth.get_session() as session:
            await auth.user_service.create_user(session=session, email=email, password="LegacyPass123!")
            await session.commit()

        app = _app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/auth/magic-link/request",
                json={"email": email, "redirect_url": "https://anything.example/raw"},
            )
            assert response.status_code == 204
            assert len(messaging.intents) == 1
            intent = messaging.intents[0]
            assert intent.redirect_url == "https://anything.example/raw"
            assert intent.next_url is None
            assert intent.profile_id is None

            rows = await _challenge_rows_for(auth, email)
            assert len(rows) == 1
            assert rows[0].redirect_url == "https://anything.example/raw"
            assert rows[0].next_url is None

            verify = await client.post("/v1/auth/magic-link/verify", json={"token": intent.secret})
            assert verify.status_code == 200
            assert verify.json()["next_url"] is None
    finally:
        await auth.shutdown()
