"""
Token Cleanup Worker

Background worker to clean up expired and old revoked refresh tokens from MongoDB.

This prevents the refresh_tokens collection from growing indefinitely by removing:
1. Expired tokens (past their expires_at date)
2. Old revoked tokens (revoked > 7 days ago)

Run this periodically (daily recommended) via scheduler:
- APScheduler
- Celery Beat
- System cron
- Cloud scheduler (AWS EventBridge, GCP Scheduler, etc.)
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict

from outlabs_auth.models.token import RefreshTokenModel

logger = logging.getLogger(__name__)


async def cleanup_expired_refresh_tokens(
    revoked_retention_days: int = 7
) -> Dict[str, int]:
    """
    Clean up expired and old revoked refresh tokens.

    Args:
        revoked_retention_days: Days to retain revoked tokens (default: 7)

    Returns:
        Dict[str, int]: Cleanup statistics
            - expired: Number of expired tokens deleted
            - revoked: Number of old revoked tokens deleted
            - total: Total tokens deleted

    Example:
        >>> # In your scheduler
        >>> from outlabs_auth.workers.token_cleanup import cleanup_expired_refresh_tokens
        >>>
        >>> # Run daily at 3 AM
        >>> scheduler.add_job(
        ...     cleanup_expired_refresh_tokens,
        ...     'cron',
        ...     hour=3,
        ...     minute=0
        ... )
        >>>
        >>> # Or run manually
        >>> stats = await cleanup_expired_refresh_tokens()
        >>> print(f"Cleaned up {stats['total']} tokens")
    """
    now = datetime.now(timezone.utc)
    logger.info("Starting refresh token cleanup...")

    try:
        # Delete expired tokens (past their expires_at date)
        expired_result = await RefreshTokenModel.find(
            RefreshTokenModel.expires_at < now
        ).delete()
        expired_count = expired_result.deleted_count if expired_result else 0

        # Delete old revoked tokens (revoked > retention days ago)
        retention_cutoff = now - timedelta(days=revoked_retention_days)
        revoked_result = await RefreshTokenModel.find(
            RefreshTokenModel.is_revoked == True,
            RefreshTokenModel.revoked_at < retention_cutoff
        ).delete()
        revoked_count = revoked_result.deleted_count if revoked_result else 0

        total_count = expired_count + revoked_count

        logger.info(
            f"Token cleanup complete: {expired_count} expired, "
            f"{revoked_count} old revoked, {total_count} total"
        )

        return {
            "expired": expired_count,
            "revoked": revoked_count,
            "total": total_count
        }

    except Exception as e:
        logger.error(f"Error during token cleanup: {e}")
        return {
            "expired": 0,
            "revoked": 0,
            "total": 0,
            "error": str(e)
        }


async def cleanup_expired_oauth_states(
    retention_hours: int = 1
) -> Dict[str, int]:
    """
    Clean up expired OAuth state records.

    OAuth state records are short-lived (used during OAuth flow).
    Clean up states older than retention period.

    Args:
        retention_hours: Hours to retain OAuth states (default: 1)

    Returns:
        Dict[str, int]: Cleanup statistics
            - deleted: Number of OAuth states deleted

    Example:
        >>> # Run every hour
        >>> scheduler.add_job(
        ...     cleanup_expired_oauth_states,
        ...     'interval',
        ...     hours=1
        ... )
    """
    try:
        from outlabs_auth.models.oauth_state import OAuthState

        cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)

        result = await OAuthState.find(
            OAuthState.created_at < cutoff
        ).delete()

        deleted_count = result.deleted_count if result else 0

        logger.info(f"OAuth state cleanup: {deleted_count} states deleted")

        return {"deleted": deleted_count}

    except ImportError:
        # OAuth not installed
        logger.debug("OAuth module not available, skipping OAuth state cleanup")
        return {"deleted": 0}
    except Exception as e:
        logger.error(f"Error during OAuth state cleanup: {e}")
        return {"deleted": 0, "error": str(e)}


async def cleanup_all() -> Dict[str, Dict[str, int]]:
    """
    Run all cleanup tasks.

    Returns:
        Dict containing results from all cleanup tasks

    Example:
        >>> # Run all cleanup tasks daily
        >>> scheduler.add_job(
        ...     cleanup_all,
        ...     'cron',
        ...     hour=3,
        ...     minute=0
        ... )
    """
    logger.info("Running all cleanup tasks...")

    results = {
        "refresh_tokens": await cleanup_expired_refresh_tokens(),
        "oauth_states": await cleanup_expired_oauth_states()
    }

    total_deleted = (
        results["refresh_tokens"]["total"] +
        results["oauth_states"]["deleted"]
    )

    logger.info(f"All cleanup tasks complete. Total records deleted: {total_deleted}")

    return results
