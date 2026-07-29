"""Transactional mail wiring for the EnterpriseRBAC example app.

Host-owned recipe, two-profile edition (DD-059): one outlabsAuth mount, two
first-party frontends.

- **console** — the OutlabsAuthUI-style admin console: query-token links
  (``?token={token}``), full flow support.
- **portal** — an agent-portal-style frontend: path-token links
  (``/recovery/{token}``) and **no invite page** (``accept_invite=None``), so
  invites routed to it fail closed instead of producing a guessed link.

The library owns profiles, resolution, intents, and provider transports; this
module owns the declarations: the two profiles, the resolver mapping, per-
profile branding/copy, provider selection, and the sandbox recipient
override. Single-frontend hosts can ignore all of this — the library's
single-composer construction is unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from html import escape
from typing import Optional

from outlabs_auth.frontend import (
    FrontendFlow,
    FrontendProfile,
    FrontendProfileRegistry,
    FrontendProfileResolver,
    FrontendRoutes,
    route_by_root_entity_slug,
)
from outlabs_auth.mail import (
    AccessGrantedMailIntent,
    AuthMailMessage,
    ComposedAuthMailService,
    DefaultAuthMailComposer,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailDeliveryResult,
    MailgunMailProvider,
    PasswordResetConfirmationMailIntent,
    PostmarkMailProvider,
    ResendMailProvider,
    SMTPMailProvider,
    SendGridMailProvider,
    TransactionalMailProvider,
    WebhookMailProvider,
)

APP_NAME = "Outlabs Auth"
PORTAL_APP_NAME = "Outlabs Auth Portal"
CONSOLE_PROFILE_KEY = "console"
PORTAL_PROFILE_KEY = "portal"
DEFAULT_MAILGUN_API_BASE_URL = "https://api.mailgun.net"

# Example audience mapping: users rooted at these entity slugs land on the
# portal; everyone else is console. Replace with your host's real predicate —
# the audits behind DD-059 found slug, type, role, and requested-key routing
# across four production hosts, which is why the resolver is host code.
ROOT_SLUG_ROUTES = {
    "internal": CONSOLE_PROFILE_KEY,
    "agent-practice": PORTAL_PROFILE_KEY,
}


def _trim_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def build_example_frontend_registry(
    *,
    console_url: str,
    portal_url: str,
) -> FrontendProfileRegistry:
    """
    Declare the example's two frontend profiles.

    Origins default to localhost over HTTP in development, so ``local_dev``
    is inferred from the declared origins — production HTTPS origins are
    validated strictly either way.
    """
    console_origin = _trim_trailing_slash(console_url)
    portal_origin = _trim_trailing_slash(portal_url)
    local_dev = console_origin.startswith("http://") or portal_origin.startswith("http://")
    return FrontendProfileRegistry(
        [
            FrontendProfile(
                key=CONSOLE_PROFILE_KEY,
                app_name=APP_NAME,
                public_origins=(console_origin,),
                routes=FrontendRoutes(
                    login="/auth/login",
                    password_reset="/auth/reset-password?token={token}",
                    accept_invite="/auth/accept-invite?token={token}",
                    magic_link="/auth/magic-link?token={token}",
                    access_code="/auth/access-code",
                    oauth_success="/auth/oauth/callback",
                    oauth_error="/auth/login",
                ),
                support_email=_env("MAIL_SUPPORT_EMAIL"),
            ),
            FrontendProfile(
                key=PORTAL_PROFILE_KEY,
                app_name=PORTAL_APP_NAME,
                public_origins=(portal_origin,),
                routes=FrontendRoutes(
                    login="/sign-in",
                    password_reset="/recovery/{token}",
                    accept_invite=None,  # the portal has no invite page —
                    # selecting it for invites fails closed, never a guessed link
                    magic_link="/auth/magic-link?token={token}",
                    oauth_success="/auth/oauth/callback",
                    oauth_error="/sign-in",
                ),
                support_email=_env("MAIL_SUPPORT_EMAIL"),
            ),
        ],
        local_dev=local_dev,
    )


def build_example_frontend_resolver(
    registry: FrontendProfileRegistry,
    *,
    default_key: str = CONSOLE_PROFILE_KEY,
) -> FrontendProfileResolver:
    """
    Resolve each operation to a registered profile.

    ``route_by_root_entity_slug`` honors a frontend-originated requested key
    when identity has no opinion and treats a requested key that contradicts
    the identity-derived profile as a hard mismatch. The declared ``default``
    is legitimate here because the example population is effectively
    single-frontend — it is a declaration for unambiguous contexts, never an
    exception fallback (resolver errors fail closed upstream).
    """
    return FrontendProfileResolver(
        registry,
        route_by_root_entity_slug(ROOT_SLUG_ROUTES),
        default=default_key,
    )


class ConsoleMailProvider(TransactionalMailProvider):
    """Development-friendly provider that prints transactional mail to stdout."""

    provider_name = "console"

    def __init__(self, *, output: Callable[[str], None] = print) -> None:
        self.output = output

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        lines = [
            "",
            "=" * 80,
            "TRANSACTIONAL EMAIL (Console Fallback)",
            "=" * 80,
            f"To: {message.to_email}",
            f"Subject: {message.subject}",
        ]
        if message.reply_to:
            lines.append(f"Reply-To: {message.reply_to}")
        if message.tags:
            lines.append(f"Tags: {', '.join(message.tags)}")
        lines.extend(["", message.text_body, "=" * 80, ""])
        self.output("\n".join(lines))
        return MailDeliveryResult.queued(self.provider_name)


class RecipientOverrideMailProvider(TransactionalMailProvider):
    """Redirect delivery to a sandbox address while preserving intended-recipient context."""

    def __init__(
        self,
        *,
        provider: TransactionalMailProvider,
        override_email: str,
    ) -> None:
        self.provider = provider
        self.provider_name = provider.provider_name
        self.override_email = override_email

    async def send(self, message: AuthMailMessage) -> MailDeliveryResult:
        note = f"Intended recipient: {message.to_email}\n" f"Sandbox override recipient: {self.override_email}\n\n"
        overridden = replace(
            message,
            to_email=self.override_email,
            to_name=None,
            text_body=f"{note}{message.text_body}",
            metadata={
                **message.metadata,
                "intended_recipient": message.to_email,
                "sandbox_recipient": self.override_email,
            },
        )
        return await self.provider.send(overridden)


class EnterpriseExampleMailComposer(DefaultAuthMailComposer):
    """Example-app composer showing host-owned copy on top of profile routing.

    URLs and branding come from the ``FrontendProfile`` — a profile, not the
    caller, owns link construction. This subclass only owns the message copy.
    """

    def __init__(
        self,
        *,
        profile: FrontendProfile,
        support_email: Optional[str] = None,
    ) -> None:
        self.profile = profile
        super().__init__(
            app_name=profile.app_name,
            invite_url_builder=lambda token: profile.render_url(FrontendFlow.INVITE, token),
            password_reset_url_builder=lambda token: profile.render_url(FrontendFlow.PASSWORD_RESET, token),
            login_url_builder=(
                (lambda: profile.render_url(FrontendFlow.ACCESS_GRANTED)) if profile.routes.login else None
            ),
            support_email=support_email or profile.support_email,
        )

    @classmethod
    def from_profile(cls, profile: FrontendProfile) -> "EnterpriseExampleMailComposer":
        """Build the example composer for one registered profile."""
        return cls(profile=profile)

    async def compose_invite(self, intent: InviteMailIntent) -> Optional[AuthMailMessage]:
        accept_link = self.invite_url_builder(intent.token)
        target_entity_name = str(intent.metadata.get("target_entity_name") or "your organization")
        recipient_name = intent.recipient.display_name
        role_names = sorted({str(role) for role in intent.metadata.get("role_names", []) or []})
        role_line = f"\nRoles: {', '.join(role_names)}" if role_names else ""
        text_body = (
            f"Hello {recipient_name},\n\n"
            f"You've been invited to join {target_entity_name} on {self.app_name}.{role_line}\n\n"
            "Click the link below to accept your invitation and set your password:\n\n"
            f"{accept_link}\n\n"
            f"{self._format_expiry(intent.expires_at)}"
        )
        html_body = (
            f"<p>Hello {escape(recipient_name)},</p>"
            f"<p>You've been invited to join <strong>{escape(target_entity_name)}</strong> on "
            f"<strong>{escape(self.app_name)}</strong>.</p>"
            f"{f'<p><strong>Roles:</strong> {escape(', '.join(role_names))}</p>' if role_names else ''}"
            f'<p><a href="{escape(accept_link)}">Accept your invitation</a> and set your password.</p>'
            f"<p>{escape(self._format_expiry(intent.expires_at))}</p>"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=recipient_name,
            subject=f"You're invited to {self.app_name}",
            text_body=text_body,
            html_body=html_body,
            reply_to=self.support_email,
            tags=("invite", "enterprise-example"),
            metadata={"intent": "invite", **intent.metadata},
        )

    async def compose_forgot_password(self, intent: ForgotPasswordMailIntent) -> Optional[AuthMailMessage]:
        reset_link = self.password_reset_url_builder(intent.token)
        text_body = (
            "Click the link below to reset your password:\n\n"
            f"{reset_link}\n\n"
            f"{self._format_expiry(intent.expires_at)}"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject="Reset your password",
            text_body=text_body,
            reply_to=self.support_email,
            tags=("password-reset", "enterprise-example"),
            metadata={"intent": "forgot-password", **intent.metadata},
        )

    async def compose_password_reset_confirmation(
        self,
        intent: PasswordResetConfirmationMailIntent,
    ) -> Optional[AuthMailMessage]:
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject="Password reset successful",
            text_body=(
                "Your password has been successfully reset.\n\n"
                "If you didn't make this change, please contact support immediately."
            ),
            reply_to=self.support_email,
            tags=("password-reset-confirmation", "enterprise-example"),
            metadata={"intent": "password-reset-confirmation", **intent.metadata},
        )

    async def compose_access_granted(self, intent: AccessGrantedMailIntent) -> Optional[AuthMailMessage]:
        login_link = self.login_url_builder() if self.login_url_builder else ""
        target_entity_name = str(intent.metadata.get("target_entity_name") or "your organization")
        role_names = sorted({str(role) for role in intent.metadata.get("role_names", []) or []})
        role_line = f"\nRoles: {', '.join(role_names)}" if role_names else ""
        text_body = (
            f"You now have access to {target_entity_name} on {self.app_name}.{role_line}\n\n"
            f"Log in here: {login_link}"
        )
        return AuthMailMessage(
            to_email=intent.recipient.email,
            to_name=intent.recipient.display_name,
            subject=f"You have access to a new {self.app_name} team",
            text_body=text_body,
            reply_to=self.support_email,
            tags=("access-granted", "enterprise-example"),
            metadata={"intent": "access-granted", **intent.metadata},
        )


def resolve_mail_provider_name(explicit: Optional[str] = None) -> str:
    """Resolve provider name: explicit arg, OUTLABS_AUTH_MAIL_PROVIDER, or auto."""
    name = (explicit or _env("OUTLABS_AUTH_MAIL_PROVIDER") or "auto").strip().lower()
    if name in {"", "auto"}:
        if _env("MAILGUN_DOMAIN") and _env("MAILGUN_API_KEY") and (_env("MAILGUN_FROM_EMAIL") or _env("MAIL_FROM")):
            return "mailgun"
        if _env("SENDGRID_API_KEY") and (_env("MAIL_FROM") or _env("SENDGRID_FROM_EMAIL")):
            return "sendgrid"
        if _env("POSTMARK_SERVER_TOKEN") and (_env("MAIL_FROM") or _env("POSTMARK_FROM_EMAIL")):
            return "postmark"
        if _env("RESEND_API_KEY") and (_env("MAIL_FROM") or _env("RESEND_FROM_EMAIL")):
            return "resend"
        if _env("SMTP_HOST") and (_env("MAIL_FROM") or _env("SMTP_FROM_EMAIL")):
            return "smtp"
        if _env("OUTLABS_AUTH_MAIL_WEBHOOK_URL"):
            return "webhook"
        return "console"
    return name


def build_enterprise_example_transactional_mail_service(
    *,
    frontend_url: str,
    portal_frontend_url: Optional[str] = None,
    mail_provider: Optional[str] = None,
    mailgun_api_base_url: str = DEFAULT_MAILGUN_API_BASE_URL,
    mailgun_domain: Optional[str] = None,
    mailgun_api_key: Optional[str] = None,
    mailgun_from_email: Optional[str] = None,
    mailgun_from_name: str = APP_NAME,
    mailgun_recipient_override: Optional[str] = None,
    recipient_override: Optional[str] = None,
    provider_override: Optional[TransactionalMailProvider] = None,
    console_output: Callable[[str], None] = print,
) -> ComposedAuthMailService:
    """
    Build the example's multi-frontend mail service.

    Two profiles (console + portal), one resolver, per-profile composers; the
    library selects the composer per send and fails closed on unknown or
    unsupported selections. ``frontend_url`` is the console origin;
    ``portal_frontend_url`` defaults to ``PORTAL_FRONTEND_URL`` /
    ``http://localhost:3001``. The returned service exposes
    ``frontend_resolver`` — OutlabsAuth picks it up automatically for
    challenge flows, OAuth, and the sign-in gate when this service is passed
    as ``transactional_mail_service``.
    """
    provider_name = resolve_mail_provider_name(mail_provider)
    from_email = (
        mailgun_from_email
        or _env("MAIL_FROM")
        or _env("MAILGUN_FROM_EMAIL")
        or _env("SENDGRID_FROM_EMAIL")
        or _env("POSTMARK_FROM_EMAIL")
        or _env("RESEND_FROM_EMAIL")
        or _env("SMTP_FROM_EMAIL")
    )
    from_name = _env("MAIL_FROM_NAME") or mailgun_from_name or APP_NAME

    provider = provider_override or _build_mail_provider(
        provider_name=provider_name,
        mailgun_api_base_url=mailgun_api_base_url,
        mailgun_domain=mailgun_domain or _env("MAILGUN_DOMAIN"),
        mailgun_api_key=mailgun_api_key or _env("MAILGUN_API_KEY"),
        from_email=from_email,
        from_name=from_name,
        console_output=console_output,
    )

    override = (
        recipient_override
        or mailgun_recipient_override
        or _env("MAIL_RECIPIENT_OVERRIDE")
        or _env("MAILGUN_RECIPIENT_OVERRIDE")
    )
    if override:
        provider = RecipientOverrideMailProvider(
            provider=provider,
            override_email=override,
        )

    registry = build_example_frontend_registry(
        console_url=frontend_url,
        portal_url=portal_frontend_url or _env("PORTAL_FRONTEND_URL") or "http://localhost:3001",
    )
    resolver = build_example_frontend_resolver(registry)
    composers = {key: EnterpriseExampleMailComposer.from_profile(registry.get(key)) for key in registry.keys()}
    return ComposedAuthMailService(
        provider=provider,
        composers=composers,
        resolver=resolver,
    )


def _require(value: Optional[str], name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} must be configured for the selected mail provider")
    return value


def _build_mail_provider(
    *,
    provider_name: str,
    mailgun_api_base_url: str,
    mailgun_domain: Optional[str],
    mailgun_api_key: Optional[str],
    from_email: Optional[str],
    from_name: Optional[str],
    console_output: Callable[[str], None],
) -> TransactionalMailProvider:
    if provider_name in {"none", "disabled", "off", "console"}:
        return ConsoleMailProvider(output=console_output)

    if provider_name == "mailgun":
        return MailgunMailProvider(
            api_key=_require(mailgun_api_key, "MAILGUN_API_KEY"),
            domain=_require(mailgun_domain, "MAILGUN_DOMAIN"),
            from_email=_require(from_email, "MAILGUN_FROM_EMAIL or MAIL_FROM"),
            from_name=from_name,
            base_url=_trim_trailing_slash(_env("MAILGUN_API_BASE_URL") or mailgun_api_base_url),
        )

    if provider_name == "sendgrid":
        return SendGridMailProvider(
            api_key=_require(_env("SENDGRID_API_KEY"), "SENDGRID_API_KEY"),
            from_email=_require(from_email, "MAIL_FROM or SENDGRID_FROM_EMAIL"),
            from_name=from_name,
        )

    if provider_name == "postmark":
        return PostmarkMailProvider(
            server_token=_require(_env("POSTMARK_SERVER_TOKEN"), "POSTMARK_SERVER_TOKEN"),
            from_email=_require(from_email, "MAIL_FROM or POSTMARK_FROM_EMAIL"),
            from_name=from_name,
            message_stream=_env("POSTMARK_MESSAGE_STREAM") or "outbound",
        )

    if provider_name == "resend":
        return ResendMailProvider(
            api_key=_require(_env("RESEND_API_KEY"), "RESEND_API_KEY"),
            from_email=_require(from_email, "MAIL_FROM or RESEND_FROM_EMAIL"),
            from_name=from_name,
        )

    if provider_name == "smtp":
        return SMTPMailProvider(
            host=_require(_env("SMTP_HOST"), "SMTP_HOST"),
            port=int(_env("SMTP_PORT") or "587"),
            user=_require(_env("SMTP_USER"), "SMTP_USER"),
            password=_require(_env("SMTP_PASSWORD"), "SMTP_PASSWORD"),
            from_email=_require(from_email, "MAIL_FROM or SMTP_FROM_EMAIL"),
            from_name=from_name,
            use_starttls=(_env("SMTP_USE_STARTTLS") or "true").lower() in {"1", "true", "yes", "on"},
            use_ssl_tls=(_env("SMTP_USE_SSL_TLS") or "false").lower() in {"1", "true", "yes", "on"},
        )

    if provider_name == "webhook":
        return WebhookMailProvider(
            url=_require(_env("OUTLABS_AUTH_MAIL_WEBHOOK_URL"), "OUTLABS_AUTH_MAIL_WEBHOOK_URL"),
            secret=_env("OUTLABS_AUTH_MAIL_WEBHOOK_SECRET"),
        )

    raise RuntimeError(
        f"Unsupported OUTLABS_AUTH_MAIL_PROVIDER={provider_name!r}. "
        "Use auto|mailgun|sendgrid|postmark|resend|smtp|webhook|console."
    )
