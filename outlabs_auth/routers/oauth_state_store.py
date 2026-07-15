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


def oauth_state_cookie_name(provider: str, flow: str) -> str:
    """Return a stable, safe cookie name scoped to an OAuth flow and provider."""
    safe_provider = re.sub(r"[^a-zA-Z0-9_-]", "_", provider)
    safe_flow = re.sub(r"[^a-zA-Z0-9_-]", "_", flow)
    return f"outlabs_auth_oauth_{safe_flow}_{safe_provider}"


async def issue_oauth_state(
    *,
    session: AsyncSession,
    response: Response,
    state: str,
    provider: str,
    flow: str,
    user_id: Optional[UUID] = None,
) -> None:
    """Persist a one-time state record and set its HttpOnly browser binding."""
    binding = secrets.token_urlsafe(32)
    session.add(
        OAuthState(
            state=state,
            provider=provider,
            user_id=user_id,
            nonce=binding,
        )
    )
    # Authorize is a GET route and the regular UoW intentionally rolls GET
    # transactions back. Persist the anti-CSRF record explicitly.
    await session.commit()
    response.set_cookie(
        key=oauth_state_cookie_name(provider, flow),
        value=binding,
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=True,
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
) -> OAuthState:
    """Atomically validate and burn a state record before OAuth account work."""
    cookie_name = oauth_state_cookie_name(provider, flow)
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
