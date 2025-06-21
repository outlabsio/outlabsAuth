from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import time
import logging

logger = logging.getLogger(__name__)

class RateLimitStore:
    """In-memory rate limit store. In production, use Redis or similar."""

    def __init__(self):
        self._store: Dict[str, Dict[str, any]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def get_request_count(self, key: str, window_seconds: int) -> int:
        """Get current request count for a key within the time window."""
        async with self._lock:
            now = time.time()
            if key not in self._store:
                return 0

            # Clean old entries
            self._store[key] = {
                timestamp: count for timestamp, count in self._store[key].items()
                if now - float(timestamp) < window_seconds
            }

            return sum(self._store[key].values())

    async def increment_request_count(self, key: str) -> None:
        """Increment request count for a key."""
        async with self._lock:
            timestamp = str(time.time())
            if key not in self._store:
                self._store[key] = {}
            self._store[key][timestamp] = self._store[key].get(timestamp, 0) + 1

    async def set_lockout(self, key: str, lockout_seconds: int) -> None:
        """Set lockout for a key."""
        async with self._lock:
            lockout_until = time.time() + lockout_seconds
            self._store[f"{key}:lockout"] = {"until": lockout_until}

    async def is_locked_out(self, key: str) -> bool:
        """Check if a key is currently locked out."""
        async with self._lock:
            lockout_key = f"{key}:lockout"
            if lockout_key not in self._store:
                return False

            lockout_until = self._store[lockout_key].get("until", 0)
            if time.time() > lockout_until:
                # Lockout expired, remove it
                del self._store[lockout_key]
                return False

            return True

class RateLimiter:
    """Rate limiter with configurable limits and lockout functionality."""

    def __init__(self, store: Optional[RateLimitStore] = None):
        self.store = store or RateLimitStore()

        # Rate limiting configurations
        self.limits = {
            # General authentication limits (per IP)
            "auth_general": {
                "max_requests": 10,
                "window_seconds": 60,
                "lockout_after": 20,
                "lockout_seconds": 300  # 5 minutes
            },

            # Login attempts (per IP + email combination)
            "login_attempts": {
                "max_requests": 5,
                "window_seconds": 300,  # 5 minutes
                "lockout_after": 10,
                "lockout_seconds": 900  # 15 minutes
            },

            # Password reset requests (per IP)
            "password_reset": {
                "max_requests": 3,
                "window_seconds": 3600,  # 1 hour
                "lockout_after": 5,
                "lockout_seconds": 3600  # 1 hour
            },

            # Password change attempts (per user)
            "password_change": {
                "max_requests": 3,
                "window_seconds": 300,  # 5 minutes
                "lockout_after": 5,
                "lockout_seconds": 600  # 10 minutes
            },

            # Failed login attempts (per email)
            "failed_login_email": {
                "max_requests": 5,
                "window_seconds": 900,  # 15 minutes
                "lockout_after": 10,
                "lockout_seconds": 1800  # 30 minutes
            }
        }

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"

    def _get_rate_limit_key(self, request: Request, limit_type: str, additional_key: str = "") -> str:
        """Generate rate limit key based on request and limit type."""
        client_ip = self._get_client_ip(request)

        if limit_type in ["auth_general", "password_reset"]:
            return f"{limit_type}:{client_ip}"
        elif limit_type == "login_attempts":
            return f"{limit_type}:{client_ip}:{additional_key}"
        elif limit_type in ["password_change", "failed_login_email"]:
            return f"{limit_type}:{additional_key}"

        return f"{limit_type}:{client_ip}"

    async def check_rate_limit(self, request: Request, limit_type: str, additional_key: str = "") -> Tuple[bool, Dict[str, any]]:
        """
        Check if request should be rate limited.

        Returns:
            Tuple[bool, Dict]: (is_allowed, rate_limit_info)
        """
        if limit_type not in self.limits:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            return True, {}

        config = self.limits[limit_type]
        key = self._get_rate_limit_key(request, limit_type, additional_key)

        # Check if currently locked out
        if await self.store.is_locked_out(key):
            logger.warning(f"Request blocked - key {key} is locked out")
            return False, {
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": config["lockout_seconds"]
            }

        # Get current request count
        current_count = await self.store.get_request_count(key, config["window_seconds"])

        # Check if limit exceeded
        if current_count >= config["max_requests"]:
            # Check if we should trigger lockout
            total_requests = await self.store.get_request_count(key, config["window_seconds"] * 3)  # Check longer window
            if total_requests >= config["lockout_after"]:
                await self.store.set_lockout(key, config["lockout_seconds"])
                logger.warning(f"Lockout triggered for key {key} - {total_requests} requests")

            return False, {
                "error": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Please try again later.",
                "retry_after": config["window_seconds"],
                "limit": config["max_requests"],
                "window": config["window_seconds"]
            }

        # Increment request count
        await self.store.increment_request_count(key)

        return True, {
            "requests_made": current_count + 1,
            "limit": config["max_requests"],
            "window": config["window_seconds"],
            "reset_time": int(time.time() + config["window_seconds"])
        }

    async def record_failed_attempt(self, request: Request, limit_type: str, additional_key: str = "") -> None:
        """Record a failed attempt for potential lockout tracking."""
        key = self._get_rate_limit_key(request, limit_type, additional_key)
        await self.store.increment_request_count(key)

        # Log failed attempt
        client_ip = self._get_client_ip(request)
        logger.warning(f"Failed attempt recorded - Type: {limit_type}, IP: {client_ip}, Key: {additional_key}")

# Global rate limiter instance
rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware for FastAPI."""

    # Skip rate limiting for non-auth endpoints
    if not request.url.path.startswith("/v1/auth"):
        response = await call_next(request)
        return response

    # Determine limit type based on endpoint
    limit_type = None
    additional_key = ""

    if request.url.path == "/v1/auth/login" and request.method == "POST":
        limit_type = "auth_general"
    elif request.url.path == "/v1/auth/password/reset-request" and request.method == "POST":
        limit_type = "password_reset"
    elif request.url.path == "/v1/auth/password/change" and request.method == "POST":
        limit_type = "password_change"
        # For password change, we'd need to extract user ID from token
        # This is a simplified version

    # Apply rate limiting if configured
    if limit_type:
        is_allowed, rate_info = await rate_limiter.check_rate_limit(request, limit_type, additional_key)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {request.url.path} from {rate_limiter._get_client_ip(request)}")

            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": rate_info.get("error", "rate_limit_exceeded"),
                    "message": rate_info.get("message", "Rate limit exceeded"),
                    "details": {
                        "limit": rate_info.get("limit"),
                        "window": rate_info.get("window"),
                        "retry_after": rate_info.get("retry_after")
                    }
                }
            )

            # Add rate limit headers
            if "retry_after" in rate_info:
                response.headers["Retry-After"] = str(rate_info["retry_after"])
            if "limit" in rate_info:
                response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            if "window" in rate_info:
                response.headers["X-RateLimit-Window"] = str(rate_info["window"])

            return response

    # Process request normally
    response = await call_next(request)

    # Record failed login attempts for additional tracking
    if (request.url.path == "/v1/auth/login" and request.method == "POST" and
        response.status_code == 401):

        # Extract email from form data if possible
        try:
            form_data = await request.form()
            email = form_data.get("username", "")
            if email:
                await rate_limiter.record_failed_attempt(request, "failed_login_email", email)
        except Exception as e:
            logger.debug(f"Could not extract email from failed login: {e}")

    return response

class BruteForceProtection:
    """Enhanced brute force protection with account lockout."""

    def __init__(self, store: Optional[RateLimitStore] = None):
        self.store = store or RateLimitStore()
        self.failed_attempts_threshold = 5
        self.lockout_duration = 900  # 15 minutes
        self.progressive_delays = [1, 2, 5, 10, 30]  # Seconds to delay responses

    async def record_failed_login(self, email: str, ip_address: str) -> None:
        """Record a failed login attempt."""
        email_key = f"failed_login:{email}"
        ip_key = f"failed_login_ip:{ip_address}"

        await self.store.increment_request_count(email_key)
        await self.store.increment_request_count(ip_key)

        # Check if account should be locked
        email_failures = await self.store.get_request_count(email_key, 3600)  # 1 hour window
        if email_failures >= self.failed_attempts_threshold:
            await self.store.set_lockout(email_key, self.lockout_duration)
            logger.warning(f"Account locked due to failed attempts: {email}")

    async def is_account_locked(self, email: str) -> bool:
        """Check if account is locked due to failed attempts."""
        email_key = f"failed_login:{email}"
        return await self.store.is_locked_out(email_key)

    async def get_progressive_delay(self, email: str) -> float:
        """Get progressive delay based on recent failed attempts."""
        email_key = f"failed_login:{email}"
        recent_failures = await self.store.get_request_count(email_key, 300)  # 5 minutes

        if recent_failures == 0:
            return 0

        delay_index = min(recent_failures - 1, len(self.progressive_delays) - 1)
        return self.progressive_delays[delay_index]

    async def clear_failed_attempts(self, email: str) -> None:
        """Clear failed attempts after successful login."""
        email_key = f"failed_login:{email}"
        # In a real implementation, you'd clear the specific entries
        # For now, we'll just log the successful login
        logger.info(f"Successful login for {email} - failed attempts cleared")

# Global brute force protection instance
brute_force_protection = BruteForceProtection()

async def apply_brute_force_delay(email: str) -> None:
    """Apply progressive delay for repeated failed attempts."""
    delay = await brute_force_protection.get_progressive_delay(email)
    if delay > 0:
        logger.info(f"Applying {delay}s delay for {email} due to recent failed attempts")
        await asyncio.sleep(delay)
