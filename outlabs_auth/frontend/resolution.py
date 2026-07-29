"""Frontend resolution (DD-059 §8.2): one component, every flow, resolved once.

The host supplies a resolver over a typed ``FrontendResolutionContext``. The
resolver may be async and may query host data (via the context's ``session``,
preferably the caller's existing session/UoW), but it returns only a
registered profile key — never a URL. ``FrontendProfileResolver`` is the
standalone, canonical pipeline entry point: ``ComposedAuthMailService``
consumes it, and host-custom mail services or facade endpoints call it
directly.

Failure policy (r2, fail closed):

- resolver exception → ``FrontendResolverFailedError`` — never default-eligible;
- user/profile mismatch or unknown requested key → hard failure — never
  default-eligible;
- clean unresolved (resolver returns ``None`` or raises
  ``FrontendUnresolvedError``) → the declared default profile applies when one
  exists, otherwise the resolution fails closed.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Optional, Union

from outlabs_auth.frontend.errors import (
    FrontendConfigurationError,
    FrontendProfileMismatchError,
    FrontendResolutionError,
    FrontendResolverFailedError,
    FrontendUnresolvedError,
    UnknownFrontendProfileError,
    UnknownRequestedProfileError,
)
from outlabs_auth.frontend.registry import FrontendProfileRegistry
from outlabs_auth.frontend.types import FrontendFlow

logger = logging.getLogger("outlabs_auth.frontend")


@dataclass(frozen=True, slots=True)
class FrontendResolutionContext:
    """
    Typed input to the host resolver.

    ``request_origin`` is evidence, never authority. ``session`` is the
    caller's existing session/UoW when one is available so the resolver can
    query host data without opening an unrelated connection.
    """

    flow: FrontendFlow
    recipient_user_id: Optional[str] = None
    recipient_email: Optional[str] = None
    root_entity_id: Optional[str] = None
    root_entity_slug: Optional[str] = None
    root_entity_type: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    target_entity_id: Optional[str] = None
    target_entity_type: Optional[str] = None
    requested_profile_key: Optional[str] = None
    request_origin: Optional[str] = None
    session: Any = field(default=None, compare=False, repr=False)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FrontendResolution:
    """
    The resolved outcome: a registered profile key plus optional audience.

    ``audience`` is the host's classification of the recipient (the same
    inputs that drive routing); profiles gate sign-in against their
    ``accepted_audiences`` with it. ``source`` records how the key was
    produced — ``resolver`` / ``requested`` / ``default`` / ``single``.
    """

    profile_key: str
    audience: Optional[str] = None
    source: str = "resolver"


HostResolverReturn = Union[None, str, FrontendResolution]
#: The host-supplied resolver callable: sync or async, over the typed context,
#: returning only a registered key (str), a ``FrontendResolution``, or ``None``.
HostResolverFn = Callable[[FrontendResolutionContext], Union[HostResolverReturn, Awaitable[HostResolverReturn]]]


class FrontendProfileResolver:
    """
    Canonical resolution component over a ``FrontendProfileRegistry``.

    ``resolver`` is the host-supplied callable (sync or async). ``default``
    declares the default profile for genuinely unambiguous contexts — it is
    applied only on clean unresolved outcomes, never after an exception.
    """

    def __init__(
        self,
        registry: FrontendProfileRegistry,
        resolver: Optional[Any] = None,
        *,
        default: Optional[str] = None,
    ) -> None:
        if default is not None and registry.default_key is not None and default != registry.default_key:
            raise FrontendConfigurationError(
                f"Conflicting default frontend profiles: registry declares {registry.default_key!r}, "
                f"resolver was given {default!r}"
            )
        effective_default = default or registry.default_key
        if effective_default is not None:
            registry.get(effective_default)  # raises when unregistered
        self._registry = registry
        self._resolver = resolver
        self._default_key = effective_default

    @property
    def registry(self) -> FrontendProfileRegistry:
        return self._registry

    @property
    def default_key(self) -> Optional[str]:
        return self._default_key

    def with_default(self, default: str) -> "FrontendProfileResolver":
        """Return a copy bound to ``default`` (used by mail-service construction)."""
        return type(self)(self._registry, self._resolver, default=default)

    async def resolve(self, context: FrontendResolutionContext) -> FrontendResolution:
        """
        Resolve ``context`` to a registered profile — once, fail closed.

        Raises ``FrontendResolutionError`` (or a subclass) on every failure;
        callers turn that into a structured delivery failure, never a send.
        """
        requested = self._validate_requested(context.requested_profile_key)

        if self._resolver is None:
            return self._resolve_without_host_fn(context, requested)

        try:
            outcome = self._resolver(context)
            if inspect.isawaitable(outcome):
                outcome = await outcome
        except FrontendUnresolvedError:
            outcome = None
        except (FrontendResolutionError, UnknownFrontendProfileError):
            raise
        except Exception as exc:
            logger.warning(
                "frontend_resolver_failed",
                extra={"flow": context.flow.value, "error": str(exc)},
                exc_info=True,
            )
            raise FrontendResolverFailedError(
                "Frontend resolver raised; failing closed",
                details={"flow": context.flow.value, "error_type": type(exc).__name__},
            ) from exc

        if outcome is None:
            return self._default_or_raise(context)

        if isinstance(outcome, FrontendResolution):
            key = outcome.profile_key
            audience = outcome.audience
        else:
            key = str(outcome)
            audience = None

        try:
            self._registry.get(key)
        except UnknownFrontendProfileError:
            raise FrontendResolutionError(
                "frontend_profile_unregistered",
                f"Frontend resolver returned unregistered profile key {key!r}",
                details={"flow": context.flow.value, "profile_key": key},
            ) from None

        return FrontendResolution(profile_key=key, audience=audience, source="resolver")

    def _validate_requested(self, requested: Optional[str]) -> Optional[str]:
        if requested is None:
            return None
        if requested not in self._registry:
            raise UnknownRequestedProfileError(
                f"Requested frontend profile {requested!r} is not registered",
                details={"profile_key": requested},
            )
        return requested

    def _resolve_without_host_fn(
        self,
        context: FrontendResolutionContext,
        requested: Optional[str],
    ) -> FrontendResolution:
        if requested is not None:
            return FrontendResolution(profile_key=requested, source="requested")
        if self._registry.is_single_profile:
            profile = self._registry.single_profile
            assert profile is not None
            return FrontendResolution(profile_key=profile.key, source="single")
        return self._default_or_raise(context)

    def _default_or_raise(self, context: FrontendResolutionContext) -> FrontendResolution:
        if self._default_key is not None:
            return FrontendResolution(profile_key=self._default_key, source="default")
        raise FrontendUnresolvedError(
            "Frontend profile could not be resolved and no default is declared",
            details={"flow": context.flow.value},
        )


def _requested_or_none(context: FrontendResolutionContext, honor_requested: bool) -> Optional[str]:
    if honor_requested and context.requested_profile_key:
        return context.requested_profile_key
    return None


def _identity_or_requested(
    context: FrontendResolutionContext,
    identity_key: Optional[str],
    *,
    honor_requested: bool,
    on_unresolved: Optional[str],
) -> Optional[str]:
    if identity_key is not None:
        requested = _requested_or_none(context, honor_requested)
        if requested is not None and requested != identity_key:
            raise FrontendProfileMismatchError(
                f"Requested profile {requested!r} contradicts identity-derived profile {identity_key!r}",
                details={
                    "flow": context.flow.value,
                    "requested": requested,
                    "identity_profile": identity_key,
                },
            )
        return identity_key
    requested = _requested_or_none(context, honor_requested)
    if requested is not None:
        return requested
    return on_unresolved


def route_by_root_entity_slug(
    mapping: Mapping[str, str],
    *,
    honor_requested: bool = True,
    on_unresolved: Optional[str] = None,
) -> HostResolverFn:
    """
    Convenience resolver: map root-entity slug → profile key.

    ``honor_requested`` lets a frontend-originated requested key stand when
    the identity has no mapping opinion (no root, unknown slug); a requested
    key that contradicts the identity-derived profile is a hard mismatch.
    ``on_unresolved`` names the declared profile for genuinely unresolvable
    contexts — ``None`` keeps the explicit fail-closed posture.
    """

    def resolve(context: FrontendResolutionContext) -> Optional[str]:
        slug = context.root_entity_slug
        identity_key = mapping.get(slug) if slug else None
        return _identity_or_requested(
            context,
            identity_key,
            honor_requested=honor_requested,
            on_unresolved=on_unresolved,
        )

    return resolve


def route_by_root_entity_type(
    mapping: Mapping[str, str],
    *,
    slug_overrides: Optional[Mapping[str, str]] = None,
    honor_requested: bool = True,
    on_unresolved: Optional[str] = None,
) -> HostResolverFn:
    """
    Convenience resolver: map root-entity type → profile key, with canonical
    slug overrides (e.g. the internal org slug) taking precedence over type.

    Use an explicit-unresolved posture for null roots, fallback slugs, and
    unknown types rather than guessing.
    """

    overrides = dict(slug_overrides or {})

    def resolve(context: FrontendResolutionContext) -> Optional[str]:
        slug = context.root_entity_slug
        identity_key: Optional[str] = None
        if slug and slug in overrides:
            identity_key = overrides[slug]
        elif context.root_entity_type:
            identity_key = mapping.get(context.root_entity_type)
        return _identity_or_requested(
            context,
            identity_key,
            honor_requested=honor_requested,
            on_unresolved=on_unresolved,
        )

    return resolve
