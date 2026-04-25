"""
Simple in-memory rate limiter for password reset endpoints.

This is a basic implementation suitable for single-instance deployments.
For production multi-instance deployments, use Redis-based rate limiting.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple


class RateLimiter:
    """
    Simple in-memory rate limiter with sliding window.

    Thread-safe for async operations.
    """

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_rate_limited(
        self,
        key: str,
        max_requests: int = 3,
        window_seconds: int = 300,  # 5 minutes
    ) -> Tuple[bool, int]:
        """
        Check if a key is rate limited.

        Args:
            key: Identifier (e.g., email address or IP)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_limited, seconds_until_reset)
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(seconds=window_seconds)

            # Remove old requests outside the window
            self._requests[key] = [req_time for req_time in self._requests[key] if req_time > window_start]

            # Check if limit exceeded
            if len(self._requests[key]) >= max_requests:
                # Calculate time until oldest request expires
                oldest_request = min(self._requests[key])
                reset_time = oldest_request + timedelta(seconds=window_seconds)
                seconds_until_reset = int((reset_time - now).total_seconds())
                return True, max(seconds_until_reset, 1)

            # Record this request
            self._requests[key].append(now)
            return False, 0

    async def cleanup(self):
        """Clean up old entries (call periodically)."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            # Remove keys with no recent requests (older than 1 hour)
            cutoff = now - timedelta(hours=1)
            keys_to_remove = []

            for key, times in self._requests.items():
                if not times or max(times) < cutoff:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._requests[key]


# Global rate limiter instance
_rate_limiter = RateLimiter()


async def check_forgot_password_rate_limit(
    email: str,
    redis_client: Any = None,
    *,
    max_requests: int = 3,
    window_seconds: int = 300,
) -> Tuple[bool, int]:
    """
    Check if email has exceeded forgot password rate limit.

    Limit: 3 requests per 5 minutes per email.

    Args:
        email: Email address

    Returns:
        Tuple of (is_limited, seconds_until_reset)
    """
    rate_limit_key = f"forgot_password:{email.lower()}"

    if redis_client is not None and getattr(redis_client, "is_available", False):
        count = await redis_client.increment_with_ttl(
            rate_limit_key,
            amount=1,
            ttl=window_seconds,
        )
        if count is not None and count > max_requests:
            # Redis-backed mode does not currently compute exact reset time.
            return True, window_seconds
        return False, 0

    return await _rate_limiter.is_rate_limited(
        key=rate_limit_key,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )


async def check_magic_link_rate_limit(
    email: str,
    redis_client: Any = None,
    *,
    max_requests: int = 3,
    window_seconds: int = 300,
) -> Tuple[bool, int]:
    """
    Check if email has exceeded magic-link request rate limits.
    """
    rate_limit_key = f"magic_link:{email.lower()}"

    if redis_client is not None and getattr(redis_client, "is_available", False):
        count = await redis_client.increment_with_ttl(
            rate_limit_key,
            amount=1,
            ttl=window_seconds,
        )
        if count is not None and count > max_requests:
            return True, window_seconds
        return False, 0

    return await _rate_limiter.is_rate_limited(
        key=rate_limit_key,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )


async def cleanup_rate_limiter():
    """Cleanup old rate limit entries."""
    await _rate_limiter.cleanup()
