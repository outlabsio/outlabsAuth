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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, status

from outlabs_auth.frontend.errors import (
    FrontendResolutionError,
    WrongApplicationError,
)
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
    """Root-entity id/slug/type via the caller's session + request cache.

    The cache stores plain VALUES, never ORM instances: a cached Entity can
    outlive the session that loaded it (post-commit attribute expiry;
    shared-task test transports) and then raises DetachedInstanceError on
    attribute access.
    """
    root_entity_id = getattr(user, "root_entity_id", None)
    if root_entity_id is None:
        return None, None, None
    key = ("frontend_root", root_entity_id)
    cached = request_cache.get(key)
    if isinstance(cached, tuple):
        slug, entity_type = cached
    else:
        entity = await session.get(Entity, root_entity_id)
        slug = getattr(entity, "slug", None) if entity is not None else None
        entity_type = getattr(entity, "entity_type", None) if entity is not None else None
        request_cache.set_value(key, (slug, entity_type))
    return (str(root_entity_id), slug, entity_type)


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


# ---------------------------------------------------------------------------
# Sign-in gating (DD-059 slice 4)
# ---------------------------------------------------------------------------


async def enforce_sign_in_gate(
    resolver: Optional[FrontendProfileResolver],
    session: Any,
    user: Any,
    *,
    app: Optional[str],
    flow: FrontendFlow = FrontendFlow.SIGN_IN,
) -> None:
    """
    Raise ``WrongApplicationError`` when ``user`` may not authenticate
    through the frontend profile ``app``.

    STANDING OBLIGATION (DD-059): every path that mints platform credentials
    must consult this gate — today: password login, magic-link verify,
    access-code verify, OAuth callback, invite-accept auto-login (all via
    ``create_tokens_for_user`` or an inline gate), and refresh rotation. A
    new minting path that skips it makes the gate porous.

    Semantics: no resolver or no bound app → allowed (legacy / app-less
    session). A profile with empty ``accepted_audiences`` accepts everyone —
    the shared/SSO mode — with no resolver call. A partitioned profile runs
    the host resolver with the requested key; resolution failures (mismatch,
    unknown, unresolved, resolver error) reject, and the resolved audience
    (the explicit ``FrontendResolution.audience``, else the resolved profile
    key) must appear in ``accepted_audiences``.
    """
    if resolver is None or not isinstance(app, str) or not app:
        return
    registry = resolver.registry
    if app not in registry:
        raise WrongApplicationError(
            f"Unknown application {app!r}", details={"app": app}
        )
    profile = registry.get(app)
    if not profile.accepted_audiences:
        return

    root_entity_id, root_slug, root_type = await _root_context(session, user)
    context = FrontendResolutionContext(
        flow=flow,
        recipient_user_id=str(user.id),
        recipient_email=getattr(user, "email", None),
        root_entity_id=root_entity_id,
        root_entity_slug=root_slug,
        root_entity_type=root_type,
        requested_profile_key=app,
        session=session,
    )
    try:
        resolution = await resolver.resolve(context)
    except WrongApplicationError:
        raise
    except FrontendResolutionError as exc:
        logger.warning(
            "sign_in_gate_rejected",
            extra={"app": app, "reason": exc.reason, "user_id": str(user.id)},
        )
        raise WrongApplicationError(
            f"Account is not eligible to sign in to application {app!r}",
            details={"app": app, "reason": exc.reason},
        ) from exc

    audience = resolution.audience or resolution.profile_key
    if audience not in profile.accepted_audiences:
        logger.warning(
            "sign_in_gate_rejected",
            extra={"app": app, "audience": audience, "user_id": str(user.id)},
        )
        raise WrongApplicationError(
            f"Account audience {audience!r} is not accepted by application {app!r}",
            details={"app": app, "audience": audience},
        )


def require_app(auth: Any, *allowed_apps: str) -> Callable[..., Any]:
    """
    FastAPI dependency factory: the request's session must carry an ``azp``
    claim naming one of ``allowed_apps`` (DD-059 slice 4).

    Where a host declares an endpoint family app-scoped, this check is
    enforcement, not advice: app-less sessions and sessions minted for other
    profiles get a stable 403 ``wrong_application``. Layered on top of the
    host's normal ``require_auth`` dependency, which still performs full
    authentication.
    """
    if not allowed_apps:
        raise ValueError("require_app needs at least one allowed profile key")
    base_dependency = auth.deps.require_auth()

    async def _require_app(
        auth_context: Any = Depends(base_dependency),
    ) -> Any:
        azp = auth_context.get("azp") if isinstance(auth_context, Mapping) else None
        if azp not in allowed_apps:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "wrong_application",
                    "message": "This session was not issued for this application.",
                },
            )
        return auth_context

    return _require_app
