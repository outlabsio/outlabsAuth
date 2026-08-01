"""Transactional mail orchestration for auth lifecycle events."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Union

from outlabs_auth.frontend.errors import (
    FrontendConfigurationError,
    FrontendResolutionError,
)
from outlabs_auth.frontend.resolution import (
    FrontendProfileResolver,
    FrontendResolution,
    FrontendResolutionContext,
)
from outlabs_auth.frontend.types import FrontendFlow
from outlabs_auth.mail.composer import AuthMailComposer
from outlabs_auth.mail.providers import TransactionalMailProvider
from outlabs_auth.mail.types import (
    AccessGrantedMailIntent,
    AuthMailMessage,
    ForgotPasswordMailIntent,
    InviteMailIntent,
    MailDeliveryResult,
    PasswordResetConfirmationMailIntent,
)

logger = logging.getLogger("outlabs_auth.mail")

_MailIntent = Union[
    InviteMailIntent,
    ForgotPasswordMailIntent,
    PasswordResetConfirmationMailIntent,
    AccessGrantedMailIntent,
]


class ComposedAuthMailService:
    """
    Compose auth mail messages and dispatch them through a provider.

    Two construction forms:

    - ``ComposedAuthMailService(provider=..., composer=...)`` — the original
      single-composer form. Behavior is byte-identical: every send method
      uses that composer, no resolution happens.
    - ``ComposedAuthMailService(provider=..., composers={...}, resolver=...,
      default=...)`` — the multi-frontend form (DD-059). Each send resolves
      the intent to a registered frontend profile once and composes with that
      profile's composer. Resolution failures fail closed: no message is
      sent, a structured ``MailDeliveryResult`` records the reason, and the
      outward behavior of enumeration-resistant endpoints stays opaque.
    """

    def __init__(
        self,
        *,
        provider: TransactionalMailProvider,
        composer: Optional[AuthMailComposer] = None,
        composers: Optional[Mapping[str, AuthMailComposer]] = None,
        resolver: Optional[FrontendProfileResolver] = None,
        default: Optional[str] = None,
    ) -> None:
        self.provider = provider
        if composer is not None:
            if composers is not None or resolver is not None or default is not None:
                raise FrontendConfigurationError(
                    "ComposedAuthMailService takes either composer= (single-frontend) or "
                    "composers=/resolver=/default= (multi-frontend), not both"
                )
            self.composer: Optional[AuthMailComposer] = composer
            self.composers: Optional[dict[str, AuthMailComposer]] = None
            self.frontend_resolver: Optional[FrontendProfileResolver] = None
            return

        if not composers:
            raise FrontendConfigurationError(
                "ComposedAuthMailService requires composer= or a non-empty composers= mapping"
            )
        if resolver is None:
            raise FrontendConfigurationError(
                "Multi-frontend mail requires a resolver=FrontendProfileResolver so sends "
                "resolve to a registered profile"
            )
        if not isinstance(resolver, FrontendProfileResolver):
            raise FrontendConfigurationError(
                "resolver must be a FrontendProfileResolver (the canonical resolution component)"
            )

        registry = resolver.registry
        composer_map = dict(composers)
        for key in composer_map:
            registry.get(key)  # every composer key must be a registered profile

        if default is not None:
            resolver = resolver.with_default(default)
        declared_default = resolver.default_key
        if declared_default is not None:
            # The default profile backs genuinely unambiguous contexts for any
            # mail flow, so it must support every routable mail flow and have
            # a composer configured.
            if declared_default not in composer_map:
                raise FrontendConfigurationError(
                    f"Default frontend profile {declared_default!r} has no composer configured"
                )
            default_profile = registry.get(declared_default)
            for flow in (
                FrontendFlow.INVITE,
                FrontendFlow.PASSWORD_RESET,
                FrontendFlow.ACCESS_GRANTED,
            ):
                if default_profile.routes.route_for(flow) is None:
                    raise FrontendConfigurationError(
                        f"Default frontend profile {declared_default!r} does not support flow "
                        f"{flow.value!r}; the default profile must support every routable mail flow"
                    )

        self.composer = None
        self.composers = composer_map
        self.frontend_resolver = resolver

    async def send_invite(self, intent: InviteMailIntent) -> MailDeliveryResult:
        selected = await self._select_composer(intent, FrontendFlow.INVITE)
        if isinstance(selected, MailDeliveryResult):
            return selected
        return await self._compose_and_send(await selected.compose_invite(intent))

    async def send_forgot_password(self, intent: ForgotPasswordMailIntent) -> MailDeliveryResult:
        selected = await self._select_composer(intent, FrontendFlow.PASSWORD_RESET)
        if isinstance(selected, MailDeliveryResult):
            return selected
        return await self._compose_and_send(await selected.compose_forgot_password(intent))

    async def send_password_reset_confirmation(
        self,
        intent: PasswordResetConfirmationMailIntent,
    ) -> MailDeliveryResult:
        selected = await self._select_composer(intent, FrontendFlow.PASSWORD_RESET_CONFIRMATION)
        if isinstance(selected, MailDeliveryResult):
            return selected
        return await self._compose_and_send(await selected.compose_password_reset_confirmation(intent))

    async def send_access_granted(self, intent: AccessGrantedMailIntent) -> MailDeliveryResult:
        selected = await self._select_composer(intent, FrontendFlow.ACCESS_GRANTED)
        if isinstance(selected, MailDeliveryResult):
            return selected
        return await self._compose_and_send(await selected.compose_access_granted(intent))

    async def _select_composer(
        self,
        intent: _MailIntent,
        flow: FrontendFlow,
    ) -> Union[AuthMailComposer, MailDeliveryResult]:
        """
        The one internal selection method behind every send.

        Single-composer mode returns the stored composer untouched. Multi-
        frontend mode resolves the intent's profile once, then validates that
        the profile supports this flow and has a composer. Any failure
        produces a structured delivery-failure result (and a log record) —
        never a send, never a guessed brand.
        """
        if self.composer is not None:
            return self.composer

        assert self.composers is not None and self.frontend_resolver is not None
        resolver = self.frontend_resolver
        provider_name = getattr(self.provider, "provider_name", self.provider.__class__.__name__.lower())

        context = FrontendResolutionContext(
            flow=flow,
            recipient_user_id=intent.recipient.user_id,
            recipient_email=intent.recipient.email,
            root_entity_id=intent.root_entity_id,
            root_entity_slug=intent.root_entity_slug,
            root_entity_type=intent.root_entity_type,
            actor_user_id=_metadata_str(intent.metadata, "inviter_user_id"),
            actor_email=_metadata_str(intent.metadata, "inviter_email"),
            target_entity_id=_metadata_str(intent.metadata, "target_entity_id"),
            target_entity_type=_metadata_str(intent.metadata, "target_entity_type"),
            requested_profile_key=intent.profile_id,
            request_origin=intent.request_base_url,
            metadata=intent.metadata,
        )
        resolution: Optional[FrontendResolution] = None
        fallback_to_default_notice = False
        try:
            resolution = await resolver.resolve(context)
        except FrontendResolutionError as exc:
            if flow is FrontendFlow.PASSWORD_RESET_CONFIRMATION and resolver.default_key is not None:
                # Post-change security notice: fall back to the declared default
                # profile's neutral, link-free confirmation rather than dropping
                # the security signal (DD-059 §8.3). Never a navigation link.
                fallback_to_default_notice = True
            else:
                logger.warning(
                    "frontend_mail_resolution_failed",
                    extra={"flow": flow.value, "reason": exc.reason, **exc.details},
                )
                return MailDeliveryResult.failed(
                    provider_name,
                    f"frontend_resolution_failed:{exc.reason}",
                    details={"flow": flow.value, "reason": exc.reason, **exc.details},
                )

        if fallback_to_default_notice:
            profile_key = resolver.default_key
            assert profile_key is not None
        else:
            assert resolution is not None
            profile_key = resolution.profile_key

        profile = resolver.registry.get(profile_key)

        if flow is not FrontendFlow.PASSWORD_RESET_CONFIRMATION and profile.routes.route_for(flow) is None:
            logger.warning(
                "frontend_mail_flow_unsupported",
                extra={"flow": flow.value, "profile": profile_key},
            )
            return MailDeliveryResult.failed(
                provider_name,
                "frontend_flow_unsupported",
                details={"flow": flow.value, "profile": profile_key},
            )

        composer = self.composers.get(profile_key)
        if composer is None:
            logger.warning(
                "frontend_mail_composer_missing",
                extra={"flow": flow.value, "profile": profile_key},
            )
            return MailDeliveryResult.failed(
                provider_name,
                "frontend_composer_missing",
                details={"flow": flow.value, "profile": profile_key},
            )
        return composer

    async def _compose_and_send(self, message: AuthMailMessage | None) -> MailDeliveryResult:
        if message is None:
            return MailDeliveryResult.skipped_result(
                getattr(self.provider, "provider_name", self.provider.__class__.__name__.lower()),
                "composer returned no message",
            )
        return await self.provider.send(message)

    async def aclose(self) -> None:
        """Release the provider's pooled HTTP client (application shutdown)."""
        aclose = getattr(self.provider, "aclose", None)
        if aclose is not None:
            await aclose()


def _metadata_str(metadata: Mapping[str, Any], key: str) -> Optional[str]:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)
