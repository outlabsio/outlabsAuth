"""One-time, browser-bound OAuth state records used by OAuth router factories."""

import hmac
import re
import secrets
from typing import Any, Optional, cast
from uuid import UUID

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.oauth_state import OAuthState

OAUTH_STATE_TTL_SECONDS = 600


def oauth_state_cookie_name(provider: str, flow: str, app: Optional[str] = None) -> str:
    """
    Return a stable, safe cookie name scoped to an OAuth flow and provider.

    ``app`` (a registered frontend profile key, DD-059) adds a per-frontend
    segment so concurrent same-provider flows started from different
    frontends bind to different cookies instead of clobbering each other.
    """
    safe_provider = re.sub(r"[^a-zA-Z0-9_-]", "_", provider)
    safe_flow = re.sub(r"[^a-zA-Z0-9_-]", "_", flow)
    name = f"outlabs_auth_oauth_{safe_flow}_{safe_provider}"
    if app:
        safe_app = re.sub(r"[^a-zA-Z0-9_-]", "_", app)
        name = f"{name}_{safe_app}"
    return name


def oauth_callback_route_name(kind: str, provider: str, prefix: str) -> str:
    """
    Route name for an OAuth callback, unique per mount (DD-059).

    The provider-only names collided when one provider was mounted twice and
    ``url_for`` silently resolved every flow to the first mount. Prefixed
    mounts get a prefix-derived segment; an empty prefix keeps the historical
    name so existing single-mount reverse lookups keep working.
    """
    cleaned = prefix.strip("/").replace("/", ".")
    suffix = f":{cleaned}" if cleaned else ""
    return f"{kind}:{provider}{suffix}.callback"


async def issue_oauth_state(
    *,
    session: AsyncSession,
    response: Response,
    state: str,
    provider: str,
    flow: str,
    user_id: Optional[UUID] = None,
    app: Optional[str] = None,
    cookie_secure: bool = True,
) -> None:
    """Persist a one-time state record and set its HttpOnly browser binding.

    ``app`` binds the flow to a registered frontend profile (DD-059): it is
    persisted on the state record and scopes the binding cookie name.
    """
    binding = secrets.token_urlsafe(32)
    session.add(
        OAuthState(
            state=state,
            provider=provider,
            user_id=user_id,
            nonce=binding,
            profile_id=app,
        )
    )
    # Authorize is a GET route and the regular UoW intentionally rolls GET
    # transactions back. Persist the anti-CSRF record explicitly.
    await session.commit()
    response.set_cookie(
        key=oauth_state_cookie_name(provider, flow, app),
        value=binding,
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        path="/",
    )


async def consume_oauth_state(
    *,
    session: AsyncSession,
    request: Request,
    response: Response,
    state: str,
    provider: str,
    flow: str,
    expected_user_id: Optional[UUID] = None,
    app: Optional[str] = None,
) -> OAuthState:
    """Atomically validate and burn a state record before OAuth account work.

    ``app`` must match the profile the state was issued for: it selects the
    per-frontend binding cookie and is cross-checked against the persisted
    record, so a signed state cannot be replayed under a different profile.
    """
    cookie_name = oauth_state_cookie_name(provider, flow, app)
    cookies = getattr(request, "cookies", {})
    binding = cookies.get(cookie_name) if cookies else None
    if not binding:
        raise _invalid_state()

    result = await session.execute(
        select(OAuthState).where(
            cast(Any, OAuthState.state) == state,
            cast(Any, OAuthState.provider) == provider,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if (
        record is None
        or not record.is_valid()
        or record.nonce is None
        or not hmac.compare_digest(record.nonce, binding)
        or (expected_user_id is not None and record.user_id != expected_user_id)
        or (record.profile_id or None) != (app or None)
    ):
        raise _invalid_state()

    record.mark_used()
    # Burn a valid state even if the provider/user operation that follows fails;
    # this makes callback replay impossible after any accepted callback.
    await session.commit()
    response.delete_cookie(key=cookie_name, path="/")
    return record


def _invalid_state() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid, expired, replayed, or browser-mismatched OAuth state",
    )
