"""Request-time frontend dispatch for challenge flows (DD-059 slice 2).

The bundled request routers resolve the frontend profile ONCE, at request
time, where the user and the caller's session are both in hand. The result
is persisted on the challenge row, threaded to the delivery intent, and
surfaced again at verification as the canonical ``next_url``.

Hook signatures are frozen (DD-059), so values that must travel from a
router to a send site — or out of a verify call without changing its return
shape — ride the request-scoped cache. Every carrier is consume-once and
task-local, so nothing leaks across requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from outlabs_auth.frontend.errors import FrontendResolutionError
from outlabs_auth.frontend.resolution import (
    FrontendProfileResolver,
    FrontendResolutionContext,
)
from outlabs_auth.frontend.types import FrontendFlow
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.services import request_cache

logger = logging.getLogger("outlabs_auth.frontend")

_SEND_PROFILE_KEY = ("frontend", "send_profile")
_SEND_NEXT_URL_KEY = ("frontend", "send_next_url")
_VERIFIED_CHALLENGE_KEY = ("frontend", "verified_challenge")


@dataclass(frozen=True, slots=True)
class ChallengeFrontendDispatch:
    """
    Outcome of request-time resolution for a challenge request.

    ``deliver=False`` means fail closed: no challenge is generated and no
    delivery happens, while the endpoint's outward response stays opaque.
    ``reason`` carries the stable machine-readable cause for logs/audit.
    """

    deliver: bool
    profile_id: Optional[str] = None
    next_url: Optional[str] = None
    reason: Optional[str] = None


async def prepare_challenge_dispatch(
    resolver: Optional[FrontendProfileResolver],
    session: Any,
    user: Any,
    *,
    flow: FrontendFlow,
    requested_app: Optional[str] = None,
    redirect_url: Optional[str] = None,
) -> ChallengeFrontendDispatch:
    """
    Resolve the frontend profile and canonical return target for a challenge.

    With no resolver configured the host keeps today's behavior verbatim:
    delivery proceeds, the raw ``redirect_url`` flows through unvalidated
    (compat window), and a supplied ``app`` is ignored with a log record.

    With a resolver configured, resolution failures, unknown/mismatched
    requested keys, unsupported flows, and return targets outside the
    resolved profile's redirect policy all fail closed.
    """
    if resolver is None:
        if requested_app:
            logger.info(
                "frontend_app_ignored_no_registry",
                extra={"flow": flow.value, "requested_app": requested_app},
            )
        return ChallengeFrontendDispatch(deliver=True)

    root_entity_id, root_slug, root_type = await _root_context(session, user)
    context = FrontendResolutionContext(
        flow=flow,
        recipient_user_id=str(user.id),
        recipient_email=getattr(user, "email", None),
        root_entity_id=root_entity_id,
        root_entity_slug=root_slug,
        root_entity_type=root_type,
        requested_profile_key=(requested_app or None),
        session=session,
    )
    try:
        resolution = await resolver.resolve(context)
    except FrontendResolutionError as exc:
        logger.warning(
            "frontend_challenge_resolution_failed",
            extra={"flow": flow.value, "reason": exc.reason, **exc.details},
        )
        return ChallengeFrontendDispatch(deliver=False, reason=exc.reason)

    profile = resolver.registry.get(resolution.profile_key)

    # A magic-link email is a link by definition; a profile with no declared
    # magic-link landing route guarantees a dead link — fail closed. Access
    # codes are typed, not followed, so a missing route is not fatal there.
    if flow is FrontendFlow.MAGIC_LINK and profile.routes.magic_link is None:
        logger.warning(
            "frontend_challenge_flow_unsupported",
            extra={"flow": flow.value, "profile": profile.key},
        )
        return ChallengeFrontendDispatch(
            deliver=False, profile_id=profile.key, reason="frontend_flow_unsupported"
        )

    provided = (redirect_url or "").strip() or None
    canonical = profile.redirect_policy.normalize_return_target(profile, provided)
    if provided is not None and canonical is None:
        logger.warning(
            "frontend_invalid_return_target",
            extra={"flow": flow.value, "profile": profile.key},
        )
        return ChallengeFrontendDispatch(
            deliver=False, profile_id=profile.key, reason="invalid_return_target"
        )

    return ChallengeFrontendDispatch(deliver=True, profile_id=profile.key, next_url=canonical)


async def _root_context(
    session: Any, user: Any
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Root-entity id/slug/type via the caller's session + request cache."""
    root_entity_id = getattr(user, "root_entity_id", None)
    if root_entity_id is None:
        return None, None, None
    key = ("entity", root_entity_id)
    if request_cache.contains(key):
        entity = request_cache.get(key)
    else:
        entity = await session.get(Entity, root_entity_id)
        request_cache.set_value(key, entity)
    return (
        str(root_entity_id),
        getattr(entity, "slug", None) if entity is not None else None,
        getattr(entity, "entity_type", None) if entity is not None else None,
    )


# ---------------------------------------------------------------------------
# Request-scoped carriers (consume-once; hook signatures stay frozen)
# ---------------------------------------------------------------------------


def stash_send_profile(profile_key: Optional[str]) -> None:
    """Record the profile key the current request's send should carry."""
    request_cache.set_value(_SEND_PROFILE_KEY, profile_key)


def consume_send_profile() -> Optional[str]:
    value = request_cache.get(_SEND_PROFILE_KEY)
    request_cache.set_value(_SEND_PROFILE_KEY, None)
    return value if isinstance(value, str) else None


def stash_send_next_url(next_url: Optional[str]) -> None:
    """Record the canonical return target for the current request's delivery."""
    request_cache.set_value(_SEND_NEXT_URL_KEY, next_url)


def consume_send_next_url() -> Optional[str]:
    value = request_cache.get(_SEND_NEXT_URL_KEY)
    request_cache.set_value(_SEND_NEXT_URL_KEY, None)
    return value if isinstance(value, str) else None


def stash_verified_challenge(profile_id: Optional[str], next_url: Optional[str]) -> None:
    """Record the consumed challenge's frontend context for the response layer."""
    request_cache.set_value(
        _VERIFIED_CHALLENGE_KEY, {"profile_id": profile_id, "next_url": next_url}
    )


def consume_verified_challenge() -> dict[str, Optional[str]]:
    """
    Return (and clear) the verified challenge's frontend context.

    Public on purpose: a host facade that calls ``verify_magic_link`` /
    ``verify_access_code`` directly can read the canonical ``next_url`` the
    same way the bundled routers do.
    """
    value = request_cache.get(_VERIFIED_CHALLENGE_KEY)
    request_cache.set_value(_VERIFIED_CHALLENGE_KEY, None)
    return value if isinstance(value, dict) else {}
