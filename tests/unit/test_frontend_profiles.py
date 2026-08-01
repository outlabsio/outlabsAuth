"""Unit tests for DD-059 frontend profiles, resolution, and multi-frontend mail."""

import logging
from datetime import datetime, timezone

import pytest

from outlabs_auth.frontend import (
    FrontendConfigurationError,
    FrontendFlow,
    FrontendProfile,
    FrontendProfileMismatchError,
    FrontendProfileRegistry,
    FrontendProfileResolver,
    FrontendResolution,
    FrontendResolutionContext,
    FrontendResolutionError,
    FrontendResolverFailedError,
    FrontendRouteUnsupportedError,
    FrontendRoutes,
    FrontendUnresolvedError,
    RedirectPolicy,
    UnknownFrontendProfileError,
    UnknownRequestedProfileError,
    route_by_root_entity_slug,
    route_by_root_entity_type,
)
from outlabs_auth.mail import (
    AuthMailComposer,
    AuthMailMessage,
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailDeliveryResult,
    MailRecipient,
    PasswordResetConfirmationMailIntent,
    TransactionalMailProvider,
)


class RecordingProvider(TransactionalMailProvider):
    provider_name = "recording"

    def __init__(self) -> None:
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return MailDeliveryResult.queued(self.provider_name, provider_message_id="msg-1")


def _profile(
    key: str,
    *,
    origin: str = "https://console.example.com",
    routes: FrontendRoutes | None = None,
    app_name: str | None = None,
    **kwargs,
) -> FrontendProfile:
    return FrontendProfile(
        key=key,
        app_name=app_name or f"{key.title()} App",
        public_origins=(origin,),
        routes=(
            routes
            if routes is not None
            else FrontendRoutes(
                login="/login",
                password_reset="/recovery/{token}",
                accept_invite="/auth/accept-invite?token={token}",
                magic_link="/auth/magic-link?token={token}",
                access_code="/auth/access-code",
                oauth_success="/auth/oauth/callback",
                oauth_error="/login",
            )
        ),
        **kwargs,
    )


def _full_routes() -> FrontendRoutes:
    return FrontendRoutes(
        login="/login",
        password_reset="/recovery/{token}",
        accept_invite="/auth/accept-invite?token={token}",
        magic_link="/auth/magic-link?token={token}",
    )


# ---------------------------------------------------------------------------
# Registry and profile validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_registry_rejects_duplicate_keys():
    with pytest.raises(FrontendConfigurationError, match="Duplicate"):
        FrontendProfileRegistry([_profile("a"), _profile("a")])


@pytest.mark.unit
def test_registry_rejects_empty_registry():
    with pytest.raises(FrontendConfigurationError, match="at least one"):
        FrontendProfileRegistry([])


@pytest.mark.unit
def test_registry_rejects_unregistered_default():
    with pytest.raises(UnknownFrontendProfileError):
        FrontendProfileRegistry([_profile("a")], default="ghost")


@pytest.mark.unit
@pytest.mark.parametrize("bad_key", ["", "Console", "-bad", "has space", "under_score"])
def test_profile_key_validation(bad_key):
    with pytest.raises(FrontendConfigurationError):
        _profile(bad_key)


@pytest.mark.unit
def test_registry_rejects_non_https_origin_outside_local_dev():
    with pytest.raises(FrontendConfigurationError, match="HTTPS"):
        FrontendProfileRegistry([_profile("a", origin="http://app.example.com")])


@pytest.mark.unit
def test_registry_allows_localhost_http_in_local_dev():
    registry = FrontendProfileRegistry(
        [_profile("a", origin="http://localhost:3000/")],
        local_dev=True,
    )
    assert registry.get("a").public_origins == ("http://localhost:3000",)


@pytest.mark.unit
def test_registry_rejects_origin_with_path_or_credentials():
    with pytest.raises(FrontendConfigurationError):
        FrontendProfileRegistry([_profile("a", origin="https://app.example.com/path")])
    with pytest.raises(FrontendConfigurationError):
        FrontendProfileRegistry([_profile("a", origin="https://user:pw@app.example.com")])


@pytest.mark.unit
def test_registry_normalizes_trailing_slash_and_case():
    registry = FrontendProfileRegistry([_profile("a", origin="HTTPS://App.Example.com/")])
    assert registry.get("a").public_origins == ("https://app.example.com",)


@pytest.mark.unit
def test_routes_reject_token_placeholder_misuse():
    with pytest.raises(FrontendConfigurationError, match="exactly one"):
        FrontendRoutes(password_reset="/recovery")
    with pytest.raises(FrontendConfigurationError, match="exactly one"):
        FrontendRoutes(password_reset="/recovery/{token}?also={token}")
    with pytest.raises(FrontendConfigurationError, match="must not contain"):
        FrontendRoutes(login="/login/{token}")
    with pytest.raises(FrontendConfigurationError, match="starting with '/'"):
        FrontendRoutes(password_reset="recovery/{token}")


@pytest.mark.unit
def test_profile_requires_origin_and_app_name():
    with pytest.raises(FrontendConfigurationError):
        FrontendProfile(key="a", app_name="A", public_origins=())
    with pytest.raises(FrontendConfigurationError):
        FrontendProfile(key="a", app_name=" ", public_origins=("https://a.example.com",))


@pytest.mark.unit
def test_require_route_raises_for_none_route():
    registry = FrontendProfileRegistry([_profile("a", routes=FrontendRoutes(login="/login"))])
    assert registry.require_route("a", FrontendFlow.ACCESS_GRANTED) == "/login"
    with pytest.raises(FrontendRouteUnsupportedError):
        registry.require_route("a", FrontendFlow.PASSWORD_RESET)


@pytest.mark.unit
def test_public_origins_union_dedupes():
    registry = FrontendProfileRegistry(
        [
            _profile("a", origin="https://shared.example.com"),
            _profile("b", origin="https://b.example.com"),
            _profile("c", origin="https://shared.example.com"),
        ]
    )
    assert registry.public_origins_union() == ("https://shared.example.com", "https://b.example.com")


# ---------------------------------------------------------------------------
# URL rendering — both token placements + None-route rejection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_render_url_path_token_placement():
    profile = _profile("a", routes=FrontendRoutes(password_reset="/recovery/{token}"))
    assert profile.render_url(FrontendFlow.PASSWORD_RESET, "tok123") == "https://console.example.com/recovery/tok123"


@pytest.mark.unit
def test_render_url_query_token_placement():
    profile = _profile("a", routes=FrontendRoutes(password_reset="/auth/reset-password?token={token}"))
    assert (
        profile.render_url(FrontendFlow.PASSWORD_RESET, "tok123")
        == "https://console.example.com/auth/reset-password?token=tok123"
    )


@pytest.mark.unit
def test_render_url_escapes_token():
    profile = _profile("a", routes=FrontendRoutes(password_reset="/recovery/{token}"))
    assert profile.render_url(FrontendFlow.PASSWORD_RESET, "tok 123?") == (
        "https://console.example.com/recovery/tok%20123%3F"
    )


@pytest.mark.unit
def test_render_url_none_route_rejected():
    profile = _profile("a", routes=FrontendRoutes(login="/login", accept_invite=None))
    with pytest.raises(FrontendRouteUnsupportedError):
        profile.render_url(FrontendFlow.INVITE, "tok")


@pytest.mark.unit
def test_render_url_token_flow_requires_token():
    profile = _profile("a", routes=_full_routes())
    with pytest.raises(FrontendRouteUnsupportedError):
        profile.render_url(FrontendFlow.PASSWORD_RESET)


@pytest.mark.unit
def test_render_url_plain_flow():
    profile = _profile("a", routes=_full_routes())
    assert profile.render_url(FrontendFlow.ACCESS_GRANTED) == "https://console.example.com/login"


# ---------------------------------------------------------------------------
# RedirectPolicy return-target normalization
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_redirect_policy_relative_path_lands_on_primary_origin():
    profile = _profile("a")
    assert profile.redirect_policy.normalize_return_target(profile, "/dash?x=1") == (
        "https://console.example.com/dash?x=1"
    )


@pytest.mark.unit
def test_redirect_policy_absolute_url_must_match_registered_origin():
    profile = _profile("a")
    assert (
        profile.redirect_policy.normalize_return_target(profile, "https://console.example.com/app")
        == "https://console.example.com/app"
    )
    assert profile.redirect_policy.normalize_return_target(profile, "https://evil.example.com/app") is None


@pytest.mark.unit
def test_redirect_policy_rejects_protocol_relative_and_junk():
    profile = _profile("a")
    assert profile.redirect_policy.normalize_return_target(profile, "//evil.example.com") is None
    assert profile.redirect_policy.normalize_return_target(profile, "javascript:alert(1)") is None
    assert profile.redirect_policy.normalize_return_target(profile, "not-a-url") is None


@pytest.mark.unit
def test_redirect_policy_default_path_when_absent():
    profile = _profile("a", redirect_policy=RedirectPolicy(default_return_path="/home"))
    assert profile.redirect_policy.normalize_return_target(profile, None) == "https://console.example.com/home"
    assert profile.redirect_policy.normalize_return_target(profile, "  ") == "https://console.example.com/home"


@pytest.mark.unit
def test_redirect_policy_extra_origins_and_no_relative():
    profile = _profile(
        "a",
        redirect_policy=RedirectPolicy(
            allow_relative_paths=False,
            extra_allowed_origins=("https://alt.example.com",),
        ),
    )
    assert profile.redirect_policy.normalize_return_target(profile, "/dash") is None
    assert (
        profile.redirect_policy.normalize_return_target(profile, "https://alt.example.com/dash")
        == "https://alt.example.com/dash"
    )


# ---------------------------------------------------------------------------
# Resolution outcomes
# ---------------------------------------------------------------------------


def _context(**kwargs) -> FrontendResolutionContext:
    kwargs.setdefault("flow", FrontendFlow.PASSWORD_RESET)
    return FrontendResolutionContext(**kwargs)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_valid_requested_key_hint():
    registry = FrontendProfileRegistry([_profile("a"), _profile("b", origin="https://b.example.com")])
    resolver = FrontendProfileResolver(registry)
    resolution = await resolver.resolve(_context(requested_profile_key="b"))
    assert resolution.profile_key == "b"
    assert resolution.source == "requested"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_unknown_requested_key_fails_closed():
    registry = FrontendProfileRegistry([_profile("a")], default="a")
    resolver = FrontendProfileResolver(registry)
    with pytest.raises(UnknownRequestedProfileError):
        await resolver.resolve(_context(requested_profile_key="ghost"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_identity_derived_via_slug():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])
    resolver = FrontendProfileResolver(
        registry,
        route_by_root_entity_slug({"acme-internal": "console", "agent-practice": "portal"}),
    )
    resolution = await resolver.resolve(_context(root_entity_slug="agent-practice"))
    assert resolution.profile_key == "portal"
    assert resolution.source == "resolver"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_no_root_unresolved_fails_closed_without_default():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])
    resolver = FrontendProfileResolver(registry, route_by_root_entity_slug({"acme-internal": "console"}))
    with pytest.raises(FrontendUnresolvedError) as excinfo:
        await resolver.resolve(_context())
    assert excinfo.value.reason == "frontend_unresolved"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_no_root_uses_declared_default_only():
    registry = FrontendProfileRegistry(
        [_profile("console"), _profile("portal", origin="https://p.example.com")],
        default="console",
    )
    resolver = FrontendProfileResolver(registry, route_by_root_entity_slug({"x": "portal"}))
    resolution = await resolver.resolve(_context())
    assert resolution.profile_key == "console"
    assert resolution.source == "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_exception_fails_closed_and_never_defaults():
    registry = FrontendProfileRegistry([_profile("a"), _profile("b", origin="https://b.example.com")], default="a")

    async def boom(context):
        raise RuntimeError("db is down")

    resolver = FrontendProfileResolver(registry, boom)
    with pytest.raises(FrontendResolverFailedError) as excinfo:
        await resolver.resolve(_context())
    assert excinfo.value.reason == "frontend_resolver_failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_returning_unregistered_key_fails_closed():
    registry = FrontendProfileRegistry([_profile("a")], default="a")
    resolver = FrontendProfileResolver(registry, lambda context: "ghost")
    with pytest.raises(FrontendResolutionError) as excinfo:
        await resolver.resolve(_context())
    assert excinfo.value.reason == "frontend_profile_unregistered"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_requested_key_honored_when_identity_has_no_opinion():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])
    resolver = FrontendProfileResolver(registry, route_by_root_entity_slug({"acme-internal": "console"}))
    resolution = await resolver.resolve(_context(requested_profile_key="portal"))
    assert resolution.profile_key == "portal"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_requested_key_conflicting_identity_is_mismatch():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])
    resolver = FrontendProfileResolver(registry, route_by_root_entity_slug({"acme-internal": "console"}))
    with pytest.raises(FrontendProfileMismatchError):
        await resolver.resolve(_context(root_entity_slug="acme-internal", requested_profile_key="portal"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_by_root_entity_type_with_slug_override():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])
    resolver = FrontendProfileResolver(
        registry,
        route_by_root_entity_type(
            {"agent_practice": "portal", "brokerage": "portal"},
            slug_overrides={"acme-internal": "console"},
        ),
    )
    assert (
        await resolver.resolve(_context(root_entity_slug="acme-internal", root_entity_type="organization"))
    ).profile_key == "console"
    assert (
        await resolver.resolve(_context(root_entity_slug="acme", root_entity_type="brokerage"))
    ).profile_key == "portal"
    # Fallback/unknown types stay unresolved (fail closed without default).
    with pytest.raises(FrontendUnresolvedError):
        await resolver.resolve(_context(root_entity_slug="acme-general", root_entity_type="organization"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_async_host_fn_and_audience_result():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])

    async def host_resolver(context: FrontendResolutionContext):
        assert context.flow is FrontendFlow.MAGIC_LINK
        return FrontendResolution(profile_key="portal", audience="agent")

    resolver = FrontendProfileResolver(registry, host_resolver)
    resolution = await resolver.resolve(_context(flow=FrontendFlow.MAGIC_LINK))
    assert resolution.profile_key == "portal"
    assert resolution.audience == "agent"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_single_profile_host_resolves_without_fn():
    registry = FrontendProfileRegistry([_profile("only")])
    resolver = FrontendProfileResolver(registry)
    resolution = await resolver.resolve(_context())
    assert resolution.profile_key == "only"
    assert resolution.source == "single"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_multi_profile_without_fn_or_default_fails():
    registry = FrontendProfileRegistry([_profile("a"), _profile("b", origin="https://b.example.com")])
    resolver = FrontendProfileResolver(registry)
    with pytest.raises(FrontendUnresolvedError):
        await resolver.resolve(_context())


@pytest.mark.unit
def test_resolver_rejects_conflicting_default():
    registry = FrontendProfileRegistry([_profile("a"), _profile("b", origin="https://b.example.com")], default="a")
    with pytest.raises(FrontendConfigurationError, match="Conflicting default"):
        FrontendProfileResolver(registry, default="b")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_explicit_unresolved_posture_key():
    registry = FrontendProfileRegistry([_profile("console"), _profile("portal", origin="https://p.example.com")])
    resolver = FrontendProfileResolver(
        registry,
        route_by_root_entity_slug({"acme-internal": "console"}, on_unresolved="portal"),
    )
    resolution = await resolver.resolve(_context())
    assert resolution.profile_key == "portal"


# ---------------------------------------------------------------------------
# DefaultAuthMailComposer.from_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_from_profile_composer_renders_profile_urls_and_branding():
    profile = _profile(
        "portal",
        origin="https://portal.example.com",
        app_name="Agent Portal",
        routes=FrontendRoutes(
            login="/sign-in",
            password_reset="/recovery/{token}",
            accept_invite="/accept?token={token}",
        ),
        support_email="help@example.com",
    )
    composer = DefaultAuthMailComposer.from_profile(profile)
    message = await composer.compose_forgot_password(
        ForgotPasswordMailIntent(
            recipient=MailRecipient(user_id="u1", email="agent@example.com"),
            token="plain-token",
            expires_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        )
    )
    assert message is not None
    assert "https://portal.example.com/recovery/plain-token" in message.text_body
    assert "Agent Portal" in message.subject
    assert message.reply_to == "help@example.com"

    invite = await composer.compose_invite(
        InviteMailIntent(
            recipient=MailRecipient(user_id="u2", email="invitee@example.com"),
            token="invite-token",
            expires_at=None,
        )
    )
    assert invite is not None
    assert "https://portal.example.com/accept?token=invite-token" in invite.text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_from_profile_unsupported_flow_builder_raises():
    profile = _profile("portal", routes=FrontendRoutes(login="/login", accept_invite=None))
    composer = DefaultAuthMailComposer.from_profile(profile)
    with pytest.raises(FrontendRouteUnsupportedError):
        composer.invite_url_builder("tok")


# ---------------------------------------------------------------------------
# ComposedAuthMailService — multi-frontend form
# ---------------------------------------------------------------------------


def _two_profile_registry(**kwargs) -> FrontendProfileRegistry:
    return FrontendProfileRegistry(
        [
            _profile("console", app_name="Console", origin="https://console.example.com"),
            _profile(
                "portal",
                app_name="Portal",
                origin="https://portal.example.com",
                routes=FrontendRoutes(
                    login="/sign-in",
                    password_reset="/auth/reset?token={token}",
                    accept_invite="/accept?token={token}",
                ),
            ),
        ],
        **kwargs,
    )


def _mail_service(
    provider: RecordingProvider,
    resolver_fn=None,
    *,
    registry: FrontendProfileRegistry | None = None,
    default=None,
) -> ComposedAuthMailService:
    registry = registry or _two_profile_registry()
    composers = {
        "console": DefaultAuthMailComposer.from_profile(registry.get("console")),
        "portal": DefaultAuthMailComposer.from_profile(registry.get("portal")),
    }
    return ComposedAuthMailService(
        provider=provider,
        composers=composers,
        resolver=FrontendProfileResolver(registry, resolver_fn),
        default=default,
    )


def _forgot_intent(email: str, **kwargs) -> ForgotPasswordMailIntent:
    return ForgotPasswordMailIntent(
        recipient=MailRecipient(user_id="u1", email=email),
        token="plain-token",
        expires_at=None,
        **kwargs,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_routes_reset_mail_per_audience_from_one_service():
    provider = RecordingProvider()
    service = _mail_service(
        provider,
        route_by_root_entity_slug({"acme-internal": "console", "agent-practice": "portal"}),
    )

    result_a = await service.send_forgot_password(
        _forgot_intent("admin@example.com", root_entity_slug="acme-internal")
    )
    result_b = await service.send_forgot_password(
        _forgot_intent("agent@example.com", root_entity_slug="agent-practice")
    )

    assert result_a.accepted and result_b.accepted
    assert len(provider.messages) == 2
    console_msg, portal_msg = provider.messages
    assert "https://console.example.com/recovery/plain-token" in console_msg.text_body
    assert "Console" in console_msg.subject
    assert "https://portal.example.com/auth/reset?token=plain-token" in portal_msg.text_body
    assert "Portal" in portal_msg.subject


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_requested_key_selects_composer():
    provider = RecordingProvider()
    service = _mail_service(provider, None)
    result = await service.send_forgot_password(_forgot_intent("user@example.com", profile_id="portal"))
    assert result.accepted
    assert "https://portal.example.com/auth/reset?token=plain-token" in provider.messages[0].text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_unknown_requested_key_fails_closed():
    provider = RecordingProvider()
    service = _mail_service(provider, None, default="console")
    result = await service.send_forgot_password(_forgot_intent("user@example.com", profile_id="ghost"))
    assert not result.accepted
    assert result.error == "frontend_resolution_failed:frontend_profile_unknown"
    assert provider.messages == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_unresolved_fails_closed_with_structured_result():
    provider = RecordingProvider()
    service = _mail_service(provider, route_by_root_entity_slug({"acme-internal": "console"}))
    result = await service.send_forgot_password(_forgot_intent("nobody@example.com"))
    assert not result.accepted
    assert result.error == "frontend_resolution_failed:frontend_unresolved"
    assert result.details["flow"] == "password_reset"
    assert provider.messages == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_resolver_exception_fails_closed_never_defaults():
    provider = RecordingProvider()

    async def boom(context):
        raise RuntimeError("db down")

    service = _mail_service(provider, boom, default="console")
    result = await service.send_forgot_password(_forgot_intent("user@example.com", root_entity_slug="acme-internal"))
    assert not result.accepted
    assert result.error == "frontend_resolution_failed:frontend_resolver_failed"
    assert provider.messages == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_default_applies_to_clean_unresolved():
    provider = RecordingProvider()
    service = _mail_service(provider, route_by_root_entity_slug({"acme-internal": "console"}), default="console")
    result = await service.send_forgot_password(_forgot_intent("user@example.com"))
    assert result.accepted
    assert "https://console.example.com/recovery/plain-token" in provider.messages[0].text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_unsupported_flow_fails_closed():
    provider = RecordingProvider()
    registry = FrontendProfileRegistry(
        [
            _profile("console"),
            _profile(
                "portal",
                origin="https://portal.example.com",
                routes=FrontendRoutes(login="/sign-in", password_reset=None),
            ),
        ]
    )
    composers = {
        "console": DefaultAuthMailComposer.from_profile(registry.get("console")),
        "portal": DefaultAuthMailComposer.from_profile(registry.get("portal")),
    }
    service = ComposedAuthMailService(
        provider=provider,
        composers=composers,
        resolver=FrontendProfileResolver(registry, route_by_root_entity_slug({"agent": "portal"})),
    )
    result = await service.send_forgot_password(_forgot_intent("agent@example.com", root_entity_slug="agent"))
    assert not result.accepted
    assert result.error == "frontend_flow_unsupported"
    assert provider.messages == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_reset_confirmation_falls_back_to_neutral_default_notice():
    provider = RecordingProvider()
    service = _mail_service(provider, route_by_root_entity_slug({"acme-internal": "console"}), default="console")
    intent = PasswordResetConfirmationMailIntent(
        recipient=MailRecipient(user_id="u1", email="user@example.com"),
        changed_at=None,
    )
    result = await service.send_password_reset_confirmation(intent)
    # Unresolved audience: the neutral, link-free default notice is still sent.
    assert result.accepted
    assert len(provider.messages) == 1
    assert "password has been changed" in provider.messages[0].text_body
    assert "http" not in provider.messages[0].text_body  # link-free


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_invite_uses_profile_template_and_metadata():
    provider = RecordingProvider()
    service = _mail_service(provider, route_by_root_entity_slug({"agent-practice": "portal"}))
    result = await service.send_invite(
        InviteMailIntent(
            recipient=MailRecipient(user_id="u2", email="invitee@example.com"),
            token="invite-token",
            expires_at=None,
            root_entity_slug="agent-practice",
            metadata={"target_entity_name": "Acme Practice", "role_names": ["agent"]},
        )
    )
    assert result.accepted
    message = provider.messages[0]
    assert "https://portal.example.com/accept?token=invite-token" in message.text_body
    assert "Acme Practice" in message.text_body
    assert "Portal" in message.subject


@pytest.mark.unit
def test_multi_frontend_construction_validation():
    provider = RecordingProvider()
    registry = _two_profile_registry()
    composers = {
        "console": DefaultAuthMailComposer.from_profile(registry.get("console")),
        "portal": DefaultAuthMailComposer.from_profile(registry.get("portal")),
    }
    resolver = FrontendProfileResolver(registry)

    # composer= and composers= are mutually exclusive
    with pytest.raises(FrontendConfigurationError):
        ComposedAuthMailService(
            provider=provider, composer=composers["console"], composers=composers, resolver=resolver
        )
    # multi-frontend requires a resolver
    with pytest.raises(FrontendConfigurationError):
        ComposedAuthMailService(provider=provider, composers=composers)
    # composer keys must be registered profiles
    with pytest.raises(UnknownFrontendProfileError):
        ComposedAuthMailService(
            provider=provider,
            composers={**composers, "ghost": composers["console"]},
            resolver=resolver,
        )
    # a declared default must have a composer and full mail-flow support
    with pytest.raises(FrontendConfigurationError, match="no composer"):
        ComposedAuthMailService(
            provider=provider,
            composers={"console": composers["console"]},
            resolver=resolver,
            default="portal",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_composer_construction_behavior_unchanged():
    provider = RecordingProvider()
    composer = DefaultAuthMailComposer(
        app_name="Outlabs Auth",
        invite_url_builder=lambda token: f"https://ui.example.com/accept-invite?token={token}",
        password_reset_url_builder=lambda token: f"https://ui.example.com/reset-password?token={token}",
    )
    service = ComposedAuthMailService(provider=provider, composer=composer)
    assert service.frontend_resolver is None
    result = await service.send_forgot_password(_forgot_intent("user@example.com", root_entity_slug="anything"))
    assert result.accepted
    assert "https://ui.example.com/reset-password?token=plain-token" in provider.messages[0].text_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_frontend_resolution_failure_logs_record():
    provider = RecordingProvider()
    service = _mail_service(provider, route_by_root_entity_slug({"acme-internal": "console"}))
    mail_logger = logging.getLogger("outlabs_auth.mail")
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture(level=logging.WARNING)
    previous_level = mail_logger.level
    previous_disabled = mail_logger.disabled
    previous_manager_disable = mail_logger.manager.disable
    mail_logger.addHandler(handler)
    mail_logger.setLevel(logging.WARNING)
    # Order-independence: earlier tests may have disabled this logger (or all
    # logging) via their own logging configuration; undo that for the capture.
    mail_logger.disabled = False
    logging.disable(logging.NOTSET)
    try:
        result = await service.send_forgot_password(_forgot_intent("user@example.com"))
    finally:
        mail_logger.removeHandler(handler)
        mail_logger.setLevel(previous_level)
        mail_logger.disabled = previous_disabled
        logging.disable(previous_manager_disable)
    assert not result.accepted
    # getMessage(): raw records only carry .message after a formatter ran.
    assert any(record.getMessage() == "frontend_mail_resolution_failed" for record in records)
