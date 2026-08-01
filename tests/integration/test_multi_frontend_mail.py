"""Integration tests for DD-059 slice 1: per-audience mail from one mount.

One outlabsAuth mount, two registered frontend profiles; forgot-password mail
lands on the frontend the recipient's root entity routes to, and unresolved
audiences fail closed internally while the outward response stays an opaque
204.
"""

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

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
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router
from outlabs_auth.services.membership import MembershipService


class RecordingProvider(TransactionalMailProvider):
    provider_name = "recording"

    def __init__(self) -> None:
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return MailDeliveryResult.queued(self.provider_name, provider_message_id="msg-1")


def _registry() -> FrontendProfileRegistry:
    return FrontendProfileRegistry(
        [
            FrontendProfile(
                key="console",
                app_name="ACME Console",
                public_origins=("https://console.example.com",),
                routes=FrontendRoutes(
                    login="/login",
                    password_reset="/recovery/{token}",
                    accept_invite="/accept-invite?token={token}",
                ),
                support_email="support@example.com",
            ),
            FrontendProfile(
                key="portal",
                app_name="Agent Portal",
                public_origins=("https://portal.example.com",),
                routes=FrontendRoutes(
                    login="/sign-in",
                    password_reset="/recovery/{token}",
                    accept_invite=None,
                ),
            ),
        ]
    )


@pytest_asyncio.fixture
async def multi_frontend_auth(test_engine) -> EnterpriseRBAC:
    registry = _registry()
    provider = RecordingProvider()
    mail_service = ComposedAuthMailService(
        provider=provider,
        composers={
            "console": DefaultAuthMailComposer.from_profile(registry.get("console")),
            "portal": DefaultAuthMailComposer.from_profile(registry.get("portal")),
        },
        resolver=FrontendProfileResolver(
            registry,
            route_by_root_entity_slug({"internal-org": "console", "agent-practice": "portal"}),
        ),
    )
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        transactional_mail_service=mail_service,
    )
    await auth.initialize()
    auth.test_mail_provider = provider  # test handle
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
            name="internal-org",
            display_name="Internal Org",
            slug=f"internal-org",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        practice = await auth.entity_service.create_entity(
            session=session,
            name="agent-practice",
            display_name="Agent Practice",
            slug=f"agent-practice",
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_produces_per_audience_links_from_one_mount(multi_frontend_auth):
    auth = multi_frontend_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        admin_response = await client.post("/v1/auth/forgot-password", json={"email": emails["admin"]})
        agent_response = await client.post("/v1/auth/forgot-password", json={"email": emails["agent"]})

    assert admin_response.status_code == 204, admin_response.text
    assert agent_response.status_code == 204, agent_response.text

    provider = auth.test_mail_provider
    assert len(provider.messages) == 2
    by_recipient = {message.to_email: message for message in provider.messages}

    admin_msg = by_recipient[emails["admin"]]
    assert "https://console.example.com/recovery/" in admin_msg.text_body
    assert "ACME Console" in admin_msg.subject
    assert admin_msg.reply_to == "support@example.com"

    agent_msg = by_recipient[emails["agent"]]
    assert "https://portal.example.com/recovery/" in agent_msg.text_body
    assert "Agent Portal" in agent_msg.subject

    # Tokens differ per user and both placements are real, non-empty links.
    admin_link = next(line for line in admin_msg.text_body.splitlines() if line.startswith("https://"))
    agent_link = next(line for line in agent_msg.text_body.splitlines() if line.startswith("https://"))
    assert admin_link != agent_link


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_unresolved_audience_fails_closed_with_opaque_response(multi_frontend_auth):
    auth = multi_frontend_auth
    emails = await _seed_users(auth)
    app = _app(auth)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # User with no root entity: the slug resolver has no opinion, no
        # default is declared — delivery must fail closed...
        noroot_response = await client.post("/v1/auth/forgot-password", json={"email": emails["noroot"]})
        # ...while unknown accounts and unresolved accounts look identical.
        ghost_response = await client.post(
            "/v1/auth/forgot-password", json={"email": f"ghost-{uuid.uuid4().hex[:6]}@example.com"}
        )

    assert noroot_response.status_code == 204, noroot_response.text
    assert ghost_response.status_code == 204, ghost_response.text
    assert auth.test_mail_provider.messages == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invite_email_populates_entity_inviter_and_role_metadata(multi_frontend_auth):
    """The default composer reads target_entity_name/inviter_email/role_names —
    the library invite path now produces them from persisted invite state."""
    auth = multi_frontend_auth
    suffix = uuid.uuid4().hex[:8]
    inviter_email = f"owner-{suffix}@example.com"
    invitee_email = f"invitee-{suffix}@example.com"

    async with auth.get_session() as session:
        practice = await auth.entity_service.create_entity(
            session=session,
            name="acme-practice",
            display_name="Acme Practice",
            slug="internal-org",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        role = await auth.role_service.create_role(
            session=session,
            name="agent",
            display_name="Agent",
            description="Agent role",
        )
        inviter = await auth.user_service.create_user(session=session, email=inviter_email, password="OwnerPass123!")
        invitee, plain_token = await auth.user_service.invite_user(
            session,
            email=invitee_email,
            invited_by_id=inviter.id,
        )
        membership_service = MembershipService(auth.config)
        await membership_service.add_member(
            session=session,
            entity_id=practice.id,
            user_id=invitee.id,
            role_ids=[role.id],
            joined_by_id=inviter.id,
        )
        await session.commit()

    sent = await auth.user_service.send_invitation_email(invitee, plain_token)

    assert sent is True
    provider = auth.test_mail_provider
    assert len(provider.messages) == 1
    message = provider.messages[0]
    assert "Acme Practice" in message.text_body
    assert "Roles: agent" in message.text_body
    assert inviter_email in message.text_body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_minimal_host_without_profiles_sees_zero_behavior_change(test_engine):
    provider = RecordingProvider()
    composer = DefaultAuthMailComposer(
        app_name="Solo App",
        invite_url_builder=lambda token: f"https://solo.example.com/accept?token={token}",
        password_reset_url_builder=lambda token: f"https://solo.example.com/reset?token={token}",
    )
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
        transactional_mail_service=ComposedAuthMailService(provider=provider, composer=composer),
    )
    await auth.initialize()
    try:
        suffix = uuid.uuid4().hex[:8]
        email = f"solo-{suffix}@example.com"
        async with auth.get_session() as session:
            await auth.user_service.create_user(session=session, email=email, password="SoloPass123!")
            await session.commit()

        app = _app(auth)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/auth/forgot-password", json={"email": email})
        assert response.status_code == 204, response.text
        assert len(provider.messages) == 1
        assert "https://solo.example.com/reset?token=" in provider.messages[0].text_body
    finally:
        await auth.shutdown()
