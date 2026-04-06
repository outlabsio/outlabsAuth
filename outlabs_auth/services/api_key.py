"""
API Key Service

Handles API key management and validation with Redis counter pattern for usage tracking.
Uses SQLAlchemy for PostgreSQL backend.
"""

from dataclasses import dataclass
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    InvalidInputError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.api_key import APIKey, APIKeyIPWhitelist, APIKeyScope
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.integration_principal import IntegrationPrincipal
from outlabs_auth.models.sql.enums import APIKeyKind, APIKeyStatus
from outlabs_auth.models.sql.user import User
from outlabs_auth.services.base import BaseService

if TYPE_CHECKING:
    from outlabs_auth.observability.service import ObservabilityService
    from outlabs_auth.services.api_key_policy import APIKeyPolicyService
    from outlabs_auth.services.redis_client import RedisClient
    from outlabs_auth.services.user_audit import UserAuditService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ResolvedAPIKeyOwner:
    """Resolved concrete owner for an API key."""

    owner_type: str
    user: Optional[User] = None
    integration_principal: Optional[IntegrationPrincipal] = None

    @property
    def owner_id(self) -> UUID:
        if self.integration_principal is not None:
            return self.integration_principal.id
        if self.user is not None:
            return self.user.id
        raise RuntimeError("API key owner resolution is missing both user and integration principal")


class APIKeyService(BaseService[APIKey]):
    """
    API key management service with Redis counter pattern.

    Features:
    - API key CRUD operations
    - Fast validation with Redis counters
    - Rate limiting
    - Usage tracking (99% fewer DB writes via Redis)
    - Background sync to database
    """

    def __init__(
        self,
        config: AuthConfig,
        redis_client: Optional["RedisClient"] = None,
        policy_service: Optional["APIKeyPolicyService"] = None,
        user_audit_service: Optional["UserAuditService"] = None,
        observability: Optional["ObservabilityService"] = None,
    ):
        """
        Initialize APIKeyService.

        Args:
            config: Authentication configuration
            redis_client: Optional Redis client for counters
        """
        super().__init__(APIKey)
        self.config = config
        self.redis_client = redis_client
        self.policy_service = policy_service
        self.user_audit_service = user_audit_service
        self.observability = observability

    async def resolve_api_key_owner(
        self,
        session: AsyncSession,
        api_key: APIKey,
    ) -> Optional[ResolvedAPIKeyOwner]:
        """Resolve the concrete owner record for a stored API key."""
        if api_key.integration_principal_id is not None:
            principal = await session.get(IntegrationPrincipal, api_key.integration_principal_id)
            if principal is None:
                return None
            return ResolvedAPIKeyOwner(owner_type="integration_principal", integration_principal=principal)

        if api_key.owner_id is not None:
            user = await session.get(User, api_key.owner_id)
            if user is None:
                return None
            return ResolvedAPIKeyOwner(owner_type="user", user=user)

        return None

    async def resolve_requested_owner(
        self,
        session: AsyncSession,
        *,
        owner_id: Optional[UUID] = None,
        integration_principal_id: Optional[UUID] = None,
    ) -> ResolvedAPIKeyOwner:
        """Resolve a requested API key owner for create/rotate flows."""
        if (owner_id is None) == (integration_principal_id is None):
            raise InvalidInputError(
                message="Exactly one API key owner must be specified",
                details={
                    "owner_id": str(owner_id) if owner_id else None,
                    "integration_principal_id": str(integration_principal_id) if integration_principal_id else None,
                },
            )

        if integration_principal_id is not None:
            principal = await session.get(IntegrationPrincipal, integration_principal_id)
            if principal is None:
                raise InvalidInputError(
                    message="Integration principal not found",
                    details={"integration_principal_id": str(integration_principal_id)},
                )
            return ResolvedAPIKeyOwner(owner_type="integration_principal", integration_principal=principal)

        user = await session.get(User, owner_id)
        if user is None:
            raise UserNotFoundError(message="User not found", details={"user_id": str(owner_id)})
        return ResolvedAPIKeyOwner(owner_type="user", user=user)

    async def create_api_key(
        self,
        session: AsyncSession,
        *,
        owner_id: Optional[UUID] = None,
        integration_principal_id: Optional[UUID] = None,
        name: str,
        scopes: Optional[List[str]] = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: Optional[int] = None,
        rate_limit_per_day: Optional[int] = None,
        entity_id: Optional[UUID] = None,
        inherit_from_tree: bool = False,
        key_kind: APIKeyKind = APIKeyKind.PERSONAL,
        ip_whitelist: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        description: Optional[str] = None,
        prefix_type: str = "sk_live",
        actor_user_id: Optional[UUID] = None,
        event_source: str = "api_key_service.create_api_key",
        record_audit: bool = True,
        record_observability: bool = True,
    ) -> tuple[str, APIKey]:
        """
        Create a new API key.

        Args:
            session: Database session
            owner_id: Human user owner for personal keys
            integration_principal_id: Non-human owner for system integration keys
            name: Human-readable key name
            scopes: Allowed permissions (None = all)
            rate_limit_per_minute: Max requests per minute
            rate_limit_per_hour: Max requests per hour
            rate_limit_per_day: Max requests per day
            entity_id: Scope to specific entity (EnterpriseRBAC)
            inherit_from_tree: Allow access to descendant entities (EnterpriseRBAC)
            ip_whitelist: Allowed IP addresses
            expires_in_days: Days until expiration
            description: Optional description
            prefix_type: Key prefix (sk_live, sk_test)

        Returns:
            tuple[str, APIKey]: (full_api_key, api_key_model)
                WARNING: full_api_key is only returned once!

        Raises:
            UserNotFoundError: If owner doesn't exist
        """
        resolved_owner = await self.resolve_requested_owner(
            session,
            owner_id=owner_id,
            integration_principal_id=integration_principal_id,
        )
        owner = resolved_owner.user
        integration_principal = resolved_owner.integration_principal
        effective_actor_user_id = actor_user_id or (owner.id if owner is not None else None)

        if resolved_owner.owner_type == "user" and key_kind != APIKeyKind.PERSONAL:
            raise InvalidInputError(
                message="Human users may only own personal API keys",
                details={"key_kind": key_kind.value},
            )
        if resolved_owner.owner_type == "integration_principal" and key_kind != APIKeyKind.SYSTEM_INTEGRATION:
            raise InvalidInputError(
                message="Integration principals may only own system integration API keys",
                details={"key_kind": key_kind.value},
            )

        if integration_principal is not None:
            entity_id = integration_principal.anchor_entity_id
            inherit_from_tree = integration_principal.inherit_from_tree

        if self.policy_service is not None:
            await self.policy_service.validate_create(
                session,
                actor_user_id=effective_actor_user_id,
                owner=owner,
                integration_principal=integration_principal,
                key_kind=key_kind,
                scopes=scopes,
                entity_id=entity_id,
                inherit_from_tree=inherit_from_tree,
            )

        # Generate API key
        full_key, prefix = APIKey.generate_key(prefix_type)
        key_hash = APIKey.hash_key(full_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create API key model
        api_key = APIKey(
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            owner_id=owner.id if owner is not None else None,
            integration_principal_id=(integration_principal.id if integration_principal is not None else None),
            key_kind=key_kind,
            status=APIKeyStatus.ACTIVE,
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            rate_limit_per_day=rate_limit_per_day,
            entity_id=entity_id,
            inherit_from_tree=inherit_from_tree,
            description=description,
        )

        session.add(api_key)
        await session.flush()

        # Add scopes via junction table
        if scopes:
            for scope in scopes:
                scope_entry = APIKeyScope(
                    api_key_id=api_key.id,
                    scope=scope,
                )
                session.add(scope_entry)

        # Add IP whitelist
        if ip_whitelist:
            for ip in ip_whitelist:
                ip_entry = APIKeyIPWhitelist(
                    api_key_id=api_key.id,
                    ip_address=ip,
                )
                session.add(ip_entry)

        await session.flush()
        await session.refresh(api_key)

        if record_audit and owner is not None:
            await self._record_api_key_audit_event(
                session,
                owner=owner,
                api_key=api_key,
                event_type="user.api_key_created",
                event_source=event_source,
                actor_user_id=effective_actor_user_id,
                after=self._build_api_key_audit_snapshot(
                    api_key,
                    scopes=scopes,
                    ip_whitelist=ip_whitelist,
                ),
                metadata={"created_via": "service"},
                occurred_at=api_key.created_at,
            )

        logger.info("Created API key '%s' for %s %s with prefix %s", name, resolved_owner.owner_type, resolved_owner.owner_id, prefix)
        if record_observability:
            self._log_api_key_lifecycle(
                operation="created",
                api_key=api_key,
                actor_user_id=effective_actor_user_id,
                event_source=event_source,
            )

        # Return full key (only time it's ever shown!)
        return full_key, api_key

    async def verify_api_key(
        self,
        session: AsyncSession,
        api_key_string: str,
        required_scope: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[Optional[APIKey], int]:
        """
        Verify API key and track usage with Redis counter.

        This is the core method for API key authentication.
        Uses Redis INCR for fast, low-latency usage tracking.

        Args:
            session: Database session
            api_key_string: Full API key string
            required_scope: Optional required permission
            entity_id: Optional entity ID for access check
            ip_address: Optional client IP for whitelist check

        Returns:
            tuple[Optional[APIKey], int]: (api_key, current_usage)
                - api_key: Valid API key model or None if invalid
                - current_usage: Current usage count (from Redis)
        """
        # Extract prefix from key string
        if not api_key_string or len(api_key_string) < 16:
            logger.warning("Invalid API key format")
            self._log_api_key_validation(
                prefix=api_key_string[:16] if api_key_string else "unknown",
                status="invalid",
                reason="invalid_format",
            )
            return None, 0

        prefix = api_key_string[:16]
        key_hash = APIKey.hash_key(api_key_string)

        # Find API key by prefix and verify hash
        api_key = await self.get_one(
            session,
            APIKey.prefix == prefix,
            APIKey.key_hash == key_hash,
        )

        if not api_key:
            logger.warning(f"Invalid API key: {api_key_string[:15]}...")
            self._log_api_key_validation(prefix=prefix, status="invalid", reason="not_found")
            return None, 0

        # Check if key is active
        if not api_key.is_active():
            logger.warning(f"Inactive API key: {api_key.prefix} (status: {api_key.status})")
            self._log_api_key_validation(
                prefix=api_key.prefix,
                status="invalid",
                reason=f"status_{getattr(api_key.status, 'value', api_key.status)}",
            )
            return None, 0

        if self.policy_service is not None:
            runtime_allowed = await self.policy_service.validate_runtime_use(session, api_key=api_key)
            if not runtime_allowed:
                self._log_api_key_validation(
                    prefix=api_key.prefix,
                    status="invalid",
                    reason="runtime_use_denied",
                )
                return None, 0

        # Check scope if required
        if required_scope:
            if self.policy_service is not None:
                owner_allowed = await self.policy_service.validate_runtime_permission(
                    session,
                    api_key=api_key,
                    required_scope=required_scope,
                    entity_id=entity_id or api_key.entity_id,
                )
                if not owner_allowed:
                    logger.warning(
                        "API key %s denied by owner permission intersection for scope %s",
                        api_key.prefix,
                        required_scope,
                    )
                    self._log_api_key_validation(
                        prefix=api_key.prefix,
                        status="invalid",
                        reason="owner_permission_missing",
                    )
                    self._log_policy_decision(
                        surface="runtime_permission",
                        outcome="denied",
                        reason="owner_permission_missing",
                        api_key=api_key,
                        required_scope=required_scope,
                        entity_id=str(entity_id or api_key.entity_id) if (entity_id or api_key.entity_id) else None,
                    )
                    return None, 0
            has_scope = await self._check_scope(session, api_key.id, required_scope)
            if not has_scope:
                logger.warning(f"API key {api_key.prefix} lacks required scope: {required_scope}")
                self._log_api_key_validation(
                    prefix=api_key.prefix,
                    status="invalid",
                    reason="scope_not_granted",
                )
                return None, 0

        # Check entity access if required (supports tree permissions)
        if entity_id:
            has_access = await self.check_entity_access_with_tree(session, api_key, entity_id)
            if not has_access:
                logger.warning(f"API key {api_key.prefix} lacks access to entity: {entity_id}")
                self._log_api_key_validation(
                    prefix=api_key.prefix,
                    status="invalid",
                    reason="entity_access_denied",
                )
                return None, 0

        # Check IP whitelist if required
        if ip_address:
            is_allowed = await self._check_ip(session, api_key.id, ip_address)
            if not is_allowed:
                logger.warning(f"API key {api_key.prefix} rejected IP: {ip_address}")
                self._log_api_key_validation(
                    prefix=api_key.prefix,
                    status="invalid",
                    reason="ip_not_allowed",
                    ip_address=ip_address,
                )
                return None, 0

        # Increment usage counter in Redis (FAST - ~0.1ms)
        usage_count = 0
        if self.redis_client and self.redis_client.is_available:
            counter_key = self._make_usage_counter_key(str(api_key.id))
            usage_count = await self.redis_client.increment(counter_key, amount=1) or 0

            # Also track last_used timestamp in Redis
            last_used_key = self._make_last_used_key(str(api_key.id))
            await self.redis_client.set(
                last_used_key,
                datetime.now(timezone.utc).isoformat(),
                ttl=self.config.cache_ttl_seconds,
            )
        else:
            # Fallback: Direct database write
            api_key.usage_count += 1
            api_key.last_used_at = datetime.now(timezone.utc)
            await session.flush()
            usage_count = api_key.usage_count

        # Check rate limits (using Redis counter)
        if self.redis_client and self.redis_client.is_available:
            await self._check_rate_limits(api_key)

        self._log_api_key_validation(prefix=api_key.prefix, status="valid")
        return api_key, usage_count

    @staticmethod
    def scopes_allow_permission(scopes: Optional[List[str]], required_scope: str) -> bool:
        """Check whether API key scopes allow a permission."""
        normalized = {("*:*" if scope == "*" else scope) for scope in (scopes or []) if scope}
        if not normalized:
            return True

        from outlabs_auth.services.permission import PermissionService

        return PermissionService._permission_set_allows(required_scope, normalized)

    async def _check_scope(self, session: AsyncSession, api_key_id: UUID, required_scope: str) -> bool:
        """Check if API key has required scope."""
        stmt = select(APIKeyScope).where(
            APIKeyScope.api_key_id == api_key_id,
        )
        result = await session.execute(stmt)
        scopes = [row.scope for row in result.scalars().all()]

        return self.scopes_allow_permission(scopes, required_scope)

    async def _check_ip(self, session: AsyncSession, api_key_id: UUID, ip_address: str) -> bool:
        stmt = select(func.count()).select_from(APIKeyIPWhitelist).where(APIKeyIPWhitelist.api_key_id == api_key_id)
        result = await session.execute(stmt)
        count = result.scalar() or 0

        # No whitelist = allow all
        if count == 0:
            return True

        # Check if IP is in whitelist
        stmt = select(APIKeyIPWhitelist).where(
            APIKeyIPWhitelist.api_key_id == api_key_id,
            APIKeyIPWhitelist.ip_address == ip_address,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _check_rate_limits(self, api_key: APIKey) -> None:
        """
        Check rate limits using Redis counters with TTL.

        Args:
            api_key: API key to check

        Raises:
            InvalidInputError: If rate limit exceeded
        """
        if not self.redis_client or not self.redis_client.is_available:
            return

        key_id = str(api_key.id)

        # Check per-minute limit
        if api_key.rate_limit_per_minute:
            minute_key = self._make_rate_limit_key(key_id, "minute")
            count = await self.redis_client.increment_with_ttl(minute_key, amount=1, ttl=60) or 0

            if count > api_key.rate_limit_per_minute:
                self._log_api_key_rate_limited(
                    api_key=api_key,
                    current_count=count,
                    limit=api_key.rate_limit_per_minute,
                    window="minute",
                )
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_minute} requests per minute",
                    details={
                        "limit": api_key.rate_limit_per_minute,
                        "current": count,
                        "window": "minute",
                    },
                )

        # Check per-hour limit
        if api_key.rate_limit_per_hour:
            hour_key = self._make_rate_limit_key(key_id, "hour")
            count = await self.redis_client.increment_with_ttl(hour_key, amount=1, ttl=3600) or 0

            if count > api_key.rate_limit_per_hour:
                self._log_api_key_rate_limited(
                    api_key=api_key,
                    current_count=count,
                    limit=api_key.rate_limit_per_hour,
                    window="hour",
                )
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_hour} requests per hour",
                    details={
                        "limit": api_key.rate_limit_per_hour,
                        "current": count,
                        "window": "hour",
                    },
                )

        # Check per-day limit
        if api_key.rate_limit_per_day:
            day_key = self._make_rate_limit_key(key_id, "day")
            count = await self.redis_client.increment_with_ttl(day_key, amount=1, ttl=86400) or 0

            if count > api_key.rate_limit_per_day:
                self._log_api_key_rate_limited(
                    api_key=api_key,
                    current_count=count,
                    limit=api_key.rate_limit_per_day,
                    window="day",
                )
                raise InvalidInputError(
                    message=f"Rate limit exceeded: {api_key.rate_limit_per_day} requests per day",
                    details={
                        "limit": api_key.rate_limit_per_day,
                        "current": count,
                        "window": "day",
                    },
                )

    async def sync_usage_counters_to_db(self, session: AsyncSession) -> Dict[str, int]:
        """
        Sync API key usage counters from Redis to database.

        This is called by background worker (every 5 minutes).
        Implements the Redis counter pattern for 99% DB write reduction.

        Returns:
            Dict[str, int]: Stats about sync operation
        """
        if not self.redis_client or not self.redis_client.is_available:
            logger.debug("Redis not available - skipping counter sync")
            return {"synced_keys": 0, "total_usage": 0, "errors": 0}

        logger.info("Starting API key usage counter sync...")

        stats = {
            "synced_keys": 0,
            "total_usage": 0,
            "errors": 0,
        }

        try:
            # Get all usage counters from Redis
            pattern = self._make_usage_counter_key("*")
            counters = await self.redis_client.get_all_counters(pattern)

            logger.debug(f"Found {len(counters)} usage counters to sync")

            # Sync each counter to database
            for counter_key, usage_count in counters.items():
                if usage_count <= 0:
                    continue

                try:
                    # Extract key_id from "apikey:{key_id}:usage"
                    key_id = counter_key.split(":")[1]

                    # Get API key
                    api_key = await self.get_by_id(session, UUID(key_id))
                    if not api_key:
                        logger.warning(f"API key not found for counter: {key_id}")
                        await self.redis_client.delete(counter_key)
                        continue

                    # Update usage count in database
                    api_key.usage_count += usage_count

                    # Update last_used_at if we have it in Redis
                    last_used_key = self._make_last_used_key(key_id)
                    last_used_str = await self.redis_client.get(last_used_key)
                    if last_used_str:
                        api_key.last_used_at = datetime.fromisoformat(last_used_str)
                    else:
                        api_key.last_used_at = datetime.now(timezone.utc)

                    await session.flush()

                    # Reset Redis counter
                    await self.redis_client.delete(counter_key)

                    stats["synced_keys"] += 1
                    stats["total_usage"] += usage_count

                    logger.debug(f"Synced {usage_count} uses for API key {api_key.prefix}")

                except Exception as e:
                    logger.error(f"Error syncing counter {counter_key}: {e}")
                    stats["errors"] += 1

            logger.info(
                f"Counter sync complete: {stats['synced_keys']} keys, "
                f"{stats['total_usage']} total uses, {stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Error during counter sync: {e}")
            stats["errors"] += 1

        return stats

    # Helper methods for Redis keys

    def _make_usage_counter_key(self, key_id: str) -> str:
        """Make Redis key for usage counter."""
        return f"apikey:{key_id}:usage"

    def _make_last_used_key(self, key_id: str) -> str:
        """Make Redis key for last_used timestamp."""
        return f"apikey:{key_id}:last_used"

    def _make_rate_limit_key(self, key_id: str, window: str) -> str:
        """Make Redis key for rate limit window."""
        return f"apikey:{key_id}:ratelimit:{window}"

    # API Key Management Methods

    async def get_api_key(self, session: AsyncSession, key_id: UUID) -> Optional[APIKey]:
        """Get API key by ID with owner loaded."""
        return await self.get_by_id(
            session,
            key_id,
            options=[
                selectinload(APIKey.owner),
                selectinload(APIKey.integration_principal),
            ],
        )

    async def get_api_key_scopes(self, session: AsyncSession, key_id: UUID) -> List[str]:
        """Get scopes for an API key."""
        stmt = select(APIKeyScope.scope).where(APIKeyScope.api_key_id == key_id)
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_api_key_ip_whitelist(self, session: AsyncSession, key_id: UUID) -> List[str]:
        """Get IP whitelist entries for an API key."""
        stmt = select(APIKeyIPWhitelist.ip_address).where(APIKeyIPWhitelist.api_key_id == key_id)
        stmt = select(APIKeyIPWhitelist.ip_address).where(APIKeyIPWhitelist.api_key_id == key_id)
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_user_api_keys(
        self,
        session: AsyncSession,
        user_id: UUID,
        status: Optional[APIKeyStatus] = None,
    ) -> List[APIKey]:
        """
        List all API keys for a user.

        Args:
            session: Database session
            user_id: User ID
            status: Optional filter by status

        Returns:
            List[APIKey]: User's API keys
        """
        filters = [APIKey.owner_id == user_id]
        if status:
            filters.append(APIKey.status == status)

        return await self.get_many(session, *filters, limit=1000)

    async def list_entity_api_keys(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        owner_id: Optional[UUID] = None,
        status: Optional[APIKeyStatus] = None,
        key_kind: Optional[APIKeyKind] = None,
    ) -> List[APIKey]:
        """List API keys anchored to a specific entity."""
        api_keys, _ = await self.list_entity_api_keys_paginated(
            session,
            entity_id=entity_id,
            owner_id=owner_id,
            status=status,
            key_kind=key_kind,
            page=1,
            limit=1000,
        )
        return api_keys

    async def list_entity_api_keys_paginated(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        owner_id: Optional[UUID] = None,
        status: Optional[APIKeyStatus] = None,
        key_kind: Optional[APIKeyKind] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[APIKey], int]:
        """List API keys anchored to a specific entity with pagination and filtering."""
        filters = [APIKey.entity_id == entity_id]
        if owner_id is not None:
            filters.append(
                or_(
                    APIKey.owner_id == owner_id,
                    APIKey.integration_principal_id == owner_id,
                )
            )
        if status is not None:
            filters.append(APIKey.status == status)
        if key_kind is not None:
            filters.append(APIKey.key_kind == key_kind)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    APIKey.name.ilike(pattern),
                    APIKey.description.ilike(pattern),
                    APIKey.prefix.ilike(pattern),
                )
            )

        total = await self.count(session, *filters)
        api_keys = await self.get_many(
            session,
            *filters,
            skip=(page - 1) * limit,
            limit=limit,
            order_by=APIKey.created_at.desc(),
        )
        return api_keys, total

    async def list_integration_principal_api_keys(
        self,
        session: AsyncSession,
        *,
        integration_principal_id: UUID,
        status: Optional[APIKeyStatus] = None,
    ) -> List[APIKey]:
        """List API keys owned by an integration principal."""
        api_keys, _ = await self.list_integration_principal_api_keys_paginated(
            session,
            integration_principal_id=integration_principal_id,
            status=status,
            page=1,
            limit=1000,
        )
        return api_keys

    async def list_integration_principal_api_keys_paginated(
        self,
        session: AsyncSession,
        *,
        integration_principal_id: UUID,
        status: Optional[APIKeyStatus] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[APIKey], int]:
        """List API keys owned by an integration principal with pagination."""
        filters = [APIKey.integration_principal_id == integration_principal_id]
        if status is not None:
            filters.append(APIKey.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    APIKey.name.ilike(pattern),
                    APIKey.description.ilike(pattern),
                    APIKey.prefix.ilike(pattern),
                )
            )
        total = await self.count(session, *filters)
        api_keys = await self.get_many(
            session,
            *filters,
            skip=(page - 1) * limit,
            limit=limit,
            order_by=APIKey.created_at.desc(),
        )
        return api_keys, total

    async def revoke_api_key(
        self,
        session: AsyncSession,
        key_id: UUID,
        *,
        actor_user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "api_key_service.revoke_api_key",
    ) -> bool:
        """
        Revoke an API key.

        Args:
            session: Database session
            key_id: API key ID

        Returns:
            bool: True if revoked
        """
        api_key = await self.get_by_id(session, key_id)
        if not api_key:
            return False
        resolved_owner = await self.resolve_api_key_owner(session, api_key)
        if resolved_owner is None:
            return False
        effective_actor_user_id = actor_user_id or (resolved_owner.user.id if resolved_owner.user is not None else None)

        await self._revoke_api_key_model(
            session,
            api_key=api_key,
            actor_user_id=effective_actor_user_id,
            reason=reason,
            event_source=event_source,
        )

        logger.info(f"Revoked API key: {api_key.prefix}")
        return True

    async def revoke_user_api_keys(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "api_key_service.revoke_user_api_keys",
    ) -> int:
        """Revoke all non-revoked API keys owned by a user."""
        stmt = select(APIKey).where(
            APIKey.owner_id == user_id,
            APIKey.status != APIKeyStatus.REVOKED,
        )
        result = await session.execute(stmt)
        api_keys = list(result.scalars().all())
        if not api_keys:
            return 0

        for api_key in api_keys:
            await self._revoke_api_key_model(
                session,
                api_key=api_key,
                actor_user_id=revoked_by_id,
                reason=reason,
                event_source=event_source,
            )

        return len(api_keys)

    async def revoke_integration_principal_api_keys(
        self,
        session: AsyncSession,
        integration_principal_id: UUID,
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "api_key_service.revoke_integration_principal_api_keys",
    ) -> int:
        """Revoke all non-revoked API keys owned by an integration principal."""
        stmt = select(APIKey).where(
            APIKey.integration_principal_id == integration_principal_id,
            APIKey.status != APIKeyStatus.REVOKED,
        )
        result = await session.execute(stmt)
        api_keys = list(result.scalars().all())
        if not api_keys:
            return 0

        for api_key in api_keys:
            await self._revoke_api_key_model(
                session,
                api_key=api_key,
                actor_user_id=revoked_by_id,
                reason=reason,
                event_source=event_source,
            )

        return len(api_keys)

    async def revoke_entity_api_keys(
        self,
        session: AsyncSession,
        entity_id: UUID,
        *,
        revoked_by_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        event_source: str = "api_key_service.revoke_entity_api_keys",
    ) -> int:
        """Revoke all non-revoked API keys anchored to an entity."""
        stmt = select(APIKey).where(
            APIKey.entity_id == entity_id,
            APIKey.status != APIKeyStatus.REVOKED,
        )
        result = await session.execute(stmt)
        api_keys = list(result.scalars().all())
        if not api_keys:
            return 0

        for api_key in api_keys:
            await self._revoke_api_key_model(
                session,
                api_key=api_key,
                actor_user_id=revoked_by_id,
                reason=reason,
                event_source=event_source,
            )

        return len(api_keys)

    async def update_api_key(
        self,
        session: AsyncSession,
        key_id: UUID,
        actor_user_id: Optional[UUID] = None,
        event_source: str = "api_key_service.update_api_key",
        **updates,
    ) -> Optional[APIKey]:
        """
        Update API key fields.

        Args:
            session: Database session
            key_id: API key ID
            **updates: Fields to update

        Returns:
            Optional[APIKey]: Updated key or None
        """
        api_key = await self.get_by_id(session, key_id)
        if not api_key:
            return None

        resolved_owner = await self.resolve_api_key_owner(session, api_key)
        if resolved_owner is None:
            raise InvalidInputError(
                message="API key owner could not be resolved",
                details={"key_id": str(key_id)},
            )
        owner = resolved_owner.user
        integration_principal = resolved_owner.integration_principal
        effective_actor_user_id = actor_user_id or (owner.id if owner is not None else None)

        if integration_principal is not None and any(field in updates for field in {"entity_id", "inherit_from_tree"}):
            raise InvalidInputError(
                message="System integration API keys inherit entity scope from their integration principal",
                details={"key_id": str(key_id)},
            )

        grant_fields_changed = any(field in updates for field in {"scopes", "entity_id", "inherit_from_tree"})
        if self.policy_service is not None and grant_fields_changed:
            effective_scopes = (
                updates["scopes"] if "scopes" in updates else await self.get_api_key_scopes(session, key_id)
            )
            effective_entity_id = updates["entity_id"] if "entity_id" in updates else api_key.entity_id
            effective_inherit_from_tree = (
                updates["inherit_from_tree"] if "inherit_from_tree" in updates else api_key.inherit_from_tree
            )
            await self.policy_service.validate_update(
                session,
                actor_user_id=effective_actor_user_id,
                owner=owner,
                integration_principal=integration_principal,
                api_key=api_key,
                scopes=effective_scopes,
                entity_id=effective_entity_id,
                inherit_from_tree=effective_inherit_from_tree,
            )

        previous_snapshot = None
        if self.user_audit_service is not None:
            previous_snapshot = await self._build_api_key_audit_snapshot_from_db(session, api_key)

        # Update allowed fields
        allowed_fields = {
            "name",
            "description",
            "rate_limit_per_minute",
            "rate_limit_per_hour",
            "rate_limit_per_day",
            "status",
            "expires_at",
            "entity_id",
            "inherit_from_tree",
        }

        for field, value in updates.items():
            if field in allowed_fields and hasattr(api_key, field):
                setattr(api_key, field, value)

        # Handle scopes separately
        if "scopes" in updates:
            # Clear existing scopes
            stmt = sql_delete(APIKeyScope).where(APIKeyScope.api_key_id == key_id)
            await session.execute(stmt)

            # Add new scopes
            for scope in updates["scopes"]:
                scope_entry = APIKeyScope(api_key_id=key_id, scope=scope)
                session.add(scope_entry)

        # Handle IP whitelist separately
        if "ip_whitelist" in updates:
            # Clear existing IPs
            stmt = sql_delete(APIKeyIPWhitelist).where(APIKeyIPWhitelist.api_key_id == key_id)
            await session.execute(stmt)

            # Add new IPs
            for ip in updates["ip_whitelist"]:
                ip_entry = APIKeyIPWhitelist(api_key_id=key_id, ip_address=ip)
                session.add(ip_entry)

        await session.flush()
        await session.refresh(api_key)

        if self.user_audit_service is not None and owner is not None:
            await self._record_api_key_audit_event(
                session,
                owner=owner,
                api_key=api_key,
                event_type="user.api_key_updated",
                event_source=event_source,
                actor_user_id=effective_actor_user_id,
                before=previous_snapshot,
                after=await self._build_api_key_audit_snapshot_from_db(session, api_key),
                metadata={"updated_fields": sorted(updates.keys())},
            )
        self._log_api_key_lifecycle(
            operation="updated",
            api_key=api_key,
            actor_user_id=effective_actor_user_id,
            event_source=event_source,
            updated_fields=sorted(updates.keys()),
        )
        return api_key

    async def rotate_api_key(
        self,
        session: AsyncSession,
        key_id: UUID,
        *,
        actor_user_id: Optional[UUID] = None,
        event_source: str = "api_key_service.rotate_api_key",
    ) -> tuple[str, APIKey]:
        """Rotate an API key and emit a single lifecycle audit event."""
        api_key = await self.get_api_key(session, key_id)
        if api_key is None:
            raise InvalidInputError(message="API key not found", details={"key_id": str(key_id)})

        resolved_owner = await self.resolve_api_key_owner(session, api_key)
        if resolved_owner is None:
            raise InvalidInputError(
                message="API key owner could not be resolved",
                details={"key_id": str(key_id)},
            )
        owner = resolved_owner.user
        effective_actor_user_id = actor_user_id or (owner.id if owner is not None else None)

        scopes = await self.get_api_key_scopes(session, api_key.id)
        ip_whitelist = await self.get_api_key_ip_whitelist(session, api_key.id)
        previous_snapshot = None
        if owner is not None:
            previous_snapshot = await self._build_api_key_audit_snapshot_from_db(session, api_key)

        expires_in_days = None
        if api_key.expires_at:
            remaining_seconds = (api_key.expires_at - datetime.now(timezone.utc)).total_seconds()
            if remaining_seconds > 0:
                expires_in_days = max(1, math.ceil(remaining_seconds / 86400))

        prefix_type = "sk_live"
        if api_key.prefix.startswith("sk_test_"):
            prefix_type = "sk_test"
        elif api_key.prefix.startswith("sk_live_"):
            prefix_type = "sk_live"

        full_key, new_key = await self.create_api_key(
            session=session,
            owner_id=api_key.owner_id,
            integration_principal_id=api_key.integration_principal_id,
            name=api_key.name,
            scopes=scopes or None,
            prefix_type=prefix_type,
            ip_whitelist=ip_whitelist or None,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            rate_limit_per_day=api_key.rate_limit_per_day,
            expires_in_days=expires_in_days,
            description=api_key.description,
            key_kind=api_key.key_kind,
            entity_id=api_key.entity_id,
            inherit_from_tree=api_key.inherit_from_tree,
            actor_user_id=effective_actor_user_id,
            event_source=event_source,
            record_audit=False,
            record_observability=False,
        )
        await self._revoke_api_key_model(
            session,
            api_key=api_key,
            actor_user_id=effective_actor_user_id,
            reason="API key rotated",
            event_source=event_source,
            record_audit=False,
            record_observability=False,
        )

        if owner is not None:
            await self._record_api_key_audit_event(
                session,
                owner=owner,
                api_key=new_key,
                event_type="user.api_key_rotated",
                event_source=event_source,
                actor_user_id=effective_actor_user_id,
                before=previous_snapshot,
                after=await self._build_api_key_audit_snapshot_from_db(session, new_key),
                reason="API key rotated",
                metadata={
                    "rotated_from_key_id": str(api_key.id),
                    "rotated_from_prefix": api_key.prefix,
                    "rotated_to_key_id": str(new_key.id),
                    "rotated_to_prefix": new_key.prefix,
                },
            )
        self._log_api_key_lifecycle(
            operation="rotated",
            api_key=new_key,
            actor_user_id=effective_actor_user_id,
            event_source=event_source,
            rotated_from_key_id=str(api_key.id),
            rotated_from_prefix=api_key.prefix,
        )
        return full_key, new_key

    async def check_entity_access_with_tree(
        self, session: AsyncSession, api_key: APIKey, target_entity_id: UUID
    ) -> bool:
        """
        Check if API key has access to target entity, including tree permissions.

        This method checks:
        1. Direct access: If entity_id matches target_entity_id
        2. Tree access: If inherit_from_tree=True and target is a descendant

        Args:
            session: Database session
            api_key: API key to check
            target_entity_id: Target entity ID to access

        Returns:
            bool: True if API key has access
        """
        # No entity_id = global access
        if not api_key.entity_id:
            return True

        # Direct match
        if api_key.entity_id == target_entity_id:
            return True

        # Check tree access if enabled
        if api_key.inherit_from_tree:
            # Check if target is a descendant of api_key's entity
            stmt = select(EntityClosure).where(
                EntityClosure.ancestor_id == api_key.entity_id,
                EntityClosure.descendant_id == target_entity_id,
                EntityClosure.depth > 0,  # Exclude self
            )
            result = await session.execute(stmt)
            closure = result.scalar_one_or_none()

            if closure:
                return True

        return False

    async def delete_api_key(self, session: AsyncSession, key_id: UUID) -> bool:
        """
        Hard delete an API key (use revoke for soft delete).

        Args:
            session: Database session
            key_id: API key ID

        Returns:
            bool: True if deleted
        """
        api_key = await self.get_by_id(session, key_id)
        if not api_key:
            return False

        # Scopes and IP whitelist are deleted via cascade
        await session.delete(api_key)
        await session.flush()

        logger.info(f"Deleted API key: {api_key.prefix}")
        self._log_api_key_lifecycle(
            operation="deleted",
            api_key=api_key,
            event_source="api_key_service.delete_api_key",
        )
        return True

    async def _revoke_api_key_model(
        self,
        session: AsyncSession,
        *,
        api_key: APIKey,
        actor_user_id: Optional[UUID],
        reason: Optional[str],
        event_source: str,
        record_audit: bool = True,
        record_observability: bool = True,
    ) -> None:
        resolved_owner = await self.resolve_api_key_owner(session, api_key)
        owner = resolved_owner.user if resolved_owner is not None else None
        previous_snapshot = None
        if self.user_audit_service is not None and record_audit:
            previous_snapshot = await self._build_api_key_audit_snapshot_from_db(session, api_key)

        api_key.status = APIKeyStatus.REVOKED
        await session.flush()

        if self.user_audit_service is not None and owner is not None and record_audit:
            await self._record_api_key_audit_event(
                session,
                owner=owner,
                api_key=api_key,
                event_type="user.api_key_revoked",
                event_source=event_source,
                actor_user_id=actor_user_id,
                before=previous_snapshot,
                after=await self._build_api_key_audit_snapshot_from_db(session, api_key),
                reason=reason,
            )
        if record_observability:
            self._log_api_key_lifecycle(
                operation="revoked",
                api_key=api_key,
                actor_user_id=actor_user_id,
                event_source=event_source,
                reason=reason,
            )

    async def _build_api_key_audit_snapshot_from_db(
        self,
        session: AsyncSession,
        api_key: APIKey,
    ) -> Dict[str, object]:
        return self._build_api_key_audit_snapshot(
            api_key,
            scopes=await self.get_api_key_scopes(session, api_key.id),
            ip_whitelist=await self.get_api_key_ip_whitelist(session, api_key.id),
        )

    def _build_api_key_audit_snapshot(
        self,
        api_key: APIKey,
        *,
        scopes: Optional[List[str]] = None,
        ip_whitelist: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        return {
            "key_id": api_key.id,
            "name": api_key.name,
            "description": api_key.description,
            "prefix": api_key.prefix,
            "key_kind": api_key.key_kind,
            "owner_type": api_key.owner_type,
            "owner_id": api_key.resolved_owner_id,
            "status": api_key.status,
            "scopes": sorted(scopes or []),
            "ip_whitelist": sorted(ip_whitelist or []),
            "entity_id": api_key.entity_id,
            "inherit_from_tree": api_key.inherit_from_tree,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "rate_limit_per_hour": api_key.rate_limit_per_hour,
            "rate_limit_per_day": api_key.rate_limit_per_day,
            "expires_at": api_key.expires_at,
        }

    def _log_api_key_validation(
        self,
        *,
        prefix: str,
        status: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        **extra: Any,
    ) -> None:
        if self.observability is None:
            return
        self.observability.log_api_key_validated(
            prefix=prefix,
            status=status,
            reason=reason,
            ip_address=ip_address,
            **extra,
        )

    def _log_api_key_rate_limited(
        self,
        *,
        api_key: APIKey,
        current_count: int,
        limit: int,
        window: str,
    ) -> None:
        if self.observability is None:
            return
        self.observability.log_api_key_rate_limited(
            prefix=api_key.prefix,
            current_count=current_count,
            limit=limit,
            window=window,
            key_kind=self._normalize_enum(api_key.key_kind),
        )

    def _log_policy_decision(
        self,
        *,
        surface: str,
        outcome: str,
        reason: str,
        api_key: APIKey,
        **extra: Any,
    ) -> None:
        if self.observability is None:
            return
        self.observability.log_api_key_policy_decision(
            surface=surface,
            outcome=outcome,
            reason=reason,
            key_kind=self._normalize_enum(api_key.key_kind),
            prefix=api_key.prefix,
            owner_id=str(api_key.resolved_owner_id) if api_key.resolved_owner_id else None,
            owner_type=api_key.owner_type,
            **extra,
        )

    def _log_api_key_lifecycle(
        self,
        *,
        operation: str,
        api_key: APIKey,
        actor_user_id: Optional[UUID] = None,
        event_source: Optional[str] = None,
        **extra: Any,
    ) -> None:
        if self.observability is None:
            return
        self.observability.log_api_key_lifecycle(
            operation=operation,
            key_kind=self._normalize_enum(api_key.key_kind),
            status=self._normalize_enum(api_key.status),
            prefix=api_key.prefix,
            owner_id=str(api_key.resolved_owner_id) if api_key.resolved_owner_id else None,
            owner_type=api_key.owner_type,
            actor_user_id=str(actor_user_id) if actor_user_id else None,
            entity_id=str(api_key.entity_id) if api_key.entity_id else None,
            entity_scoped=bool(api_key.entity_id),
            event_source=event_source,
            **extra,
        )

    @staticmethod
    def _normalize_enum(value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    async def _record_api_key_audit_event(
        self,
        session: AsyncSession,
        *,
        owner: User,
        api_key: APIKey,
        event_type: str,
        event_source: str,
        actor_user_id: Optional[UUID],
        before: Optional[Dict[str, object]] = None,
        after: Optional[Dict[str, object]] = None,
        metadata: Optional[Dict[str, object]] = None,
        reason: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        if self.user_audit_service is None:
            return

        root_entity_id = owner.root_entity_id
        if api_key.entity_id is not None:
            root_entity_id = await self._get_root_entity_id(session, api_key.entity_id)

        await self.user_audit_service.record_event(
            session,
            event_category="credential",
            event_type=event_type,
            event_source=event_source,
            actor_user_id=actor_user_id,
            subject_user_id=owner.id,
            subject_email_snapshot=owner.email,
            root_entity_id=root_entity_id,
            entity_id=api_key.entity_id,
            reason=reason,
            before=before,
            after=after,
            metadata={
                "api_key_id": api_key.id,
                "api_key_prefix": api_key.prefix,
                **(metadata or {}),
            },
            occurred_at=occurred_at,
        )

    async def _get_root_entity_id(
        self,
        session: AsyncSession,
        entity_id: UUID,
    ) -> UUID:
        stmt = (
            select(EntityClosure.ancestor_id)
            .where(EntityClosure.descendant_id == entity_id)
            .order_by(EntityClosure.depth.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else entity_id
