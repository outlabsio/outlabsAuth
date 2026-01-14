"""
Token Cleanup Worker

Background cleanup tasks for PostgreSQL/SQLModel.

Removes:
1. Expired refresh tokens (past expires_at)
2. Old revoked refresh tokens (revoked_at older than retention window)
3. Expired OAuth state rows (optional)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.oauth_state import OAuthState
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

    # Delete expired tokens
    expired_stmt = sql_delete(RefreshToken).where(RefreshToken.expires_at < now)
    expired_result = await session.execute(expired_stmt)
    expired_count = expired_result.rowcount or 0

    # Delete old revoked tokens
    retention_cutoff = now - timedelta(days=revoked_retention_days)
    revoked_stmt = sql_delete(RefreshToken).where(
        RefreshToken.is_revoked.is_(True),
        RefreshToken.revoked_at.is_not(None),
        RefreshToken.revoked_at < retention_cutoff,
    )
    revoked_result = await session.execute(revoked_stmt)
    revoked_count = revoked_result.rowcount or 0

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
    stmt = sql_delete(OAuthState).where(OAuthState.created_at < cutoff)
    result = await session.execute(stmt)
    deleted = result.rowcount or 0
    logger.info("oauth_state_cleanup_complete", extra={"deleted": deleted})
    return {"deleted": deleted}


async def cleanup_all(session: AsyncSession) -> Dict[str, Dict[str, int]]:
    """
    Run all cleanup tasks within the provided session.
    """
    return {
        "refresh_tokens": await cleanup_expired_refresh_tokens(session),
        "oauth_states": await cleanup_expired_oauth_states(session),
    }
