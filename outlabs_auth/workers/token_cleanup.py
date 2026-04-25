"""
Token Cleanup Worker

Background cleanup tasks for PostgreSQL/SQLModel.

Removes:
1. Expired refresh tokens (past expires_at)
2. Old revoked refresh tokens (revoked_at older than retention window)
3. Expired OAuth state rows (optional)
4. Expired or consumed auth challenges
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, cast
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.oauth_state import OAuthState
from outlabs_auth.models.sql.auth_challenge import AuthChallenge
from outlabs_auth.models.sql.token import RefreshToken

logger = logging.getLogger(__name__)


async def cleanup_expired_refresh_tokens(
    session: AsyncSession,
    *,
    revoked_retention_days: int = 7,
) -> Dict[str, int]:
    """
    Clean up expired and old revoked refresh tokens.
    """
    now = datetime.now(timezone.utc)
    expires_at_col = cast(Any, RefreshToken.expires_at)
    is_revoked_col = cast(Any, RefreshToken.is_revoked)
    revoked_at_col = cast(Any, RefreshToken.revoked_at)

    # Delete expired tokens
    expired_stmt = sql_delete(RefreshToken).where(expires_at_col < now)
    expired_result = await session.execute(expired_stmt)
    expired_count = int(getattr(expired_result, "rowcount", 0) or 0)

    # Delete old revoked tokens
    retention_cutoff = now - timedelta(days=revoked_retention_days)
    revoked_stmt = sql_delete(RefreshToken).where(
        is_revoked_col.is_(True),
        revoked_at_col.is_not(None),
        revoked_at_col < retention_cutoff,
    )
    revoked_result = await session.execute(revoked_stmt)
    revoked_count = int(getattr(revoked_result, "rowcount", 0) or 0)

    total_count = expired_count + revoked_count
    logger.info(
        "refresh_token_cleanup_complete",
        extra={
            "expired": expired_count,
            "revoked": revoked_count,
            "total": total_count,
        },
    )
    return {"expired": expired_count, "revoked": revoked_count, "total": total_count}


async def cleanup_expired_oauth_states(
    session: AsyncSession,
    *,
    retention_hours: int = 1,
) -> Dict[str, int]:
    """
    Clean up expired OAuth state rows.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    stmt = sql_delete(OAuthState).where(cast(Any, OAuthState.created_at) < cutoff)
    result = await session.execute(stmt)
    deleted = int(getattr(result, "rowcount", 0) or 0)
    logger.info("oauth_state_cleanup_complete", extra={"deleted": deleted})
    return {"deleted": deleted}


async def cleanup_auth_challenges(
    session: AsyncSession,
    *,
    used_retention_hours: int = 24,
) -> Dict[str, int]:
    """
    Clean up expired or already-consumed auth challenges.
    """
    now = datetime.now(timezone.utc)
    used_cutoff = now - timedelta(hours=used_retention_hours)
    expires_at_col = cast(Any, AuthChallenge.expires_at)
    used_at_col = cast(Any, AuthChallenge.used_at)

    expired_stmt = sql_delete(AuthChallenge).where(expires_at_col < now)
    expired_result = await session.execute(expired_stmt)
    expired = int(getattr(expired_result, "rowcount", 0) or 0)

    used_stmt = sql_delete(AuthChallenge).where(
        used_at_col.is_not(None),
        used_at_col < used_cutoff,
    )
    used_result = await session.execute(used_stmt)
    used = int(getattr(used_result, "rowcount", 0) or 0)

    total = expired + used
    logger.info("auth_challenge_cleanup_complete", extra={"expired": expired, "used": used, "total": total})
    return {"expired": expired, "used": used, "total": total}


async def cleanup_all(session: AsyncSession) -> Dict[str, Dict[str, int]]:
    """
    Run all cleanup tasks within the provided session.
    """
    return {
        "refresh_tokens": await cleanup_expired_refresh_tokens(session),
        "oauth_states": await cleanup_expired_oauth_states(session),
        "auth_challenges": await cleanup_auth_challenges(session),
    }
