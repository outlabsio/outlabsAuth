"""
API Key Model

Represents API keys for programmatic authentication.
Supports Redis counter pattern for high-performance usage tracking.
"""
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum
from beanie import Indexed, Link
from pydantic import Field
import secrets
import hashlib

from outlabs_auth.models.base import BaseDocument
from outlabs_auth.models.user import UserModel


class APIKeyStatus(str, Enum):
    """API key status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIKeyModel(BaseDocument):
    """
    API Key model for programmatic authentication.

    Features:
    - Secure key generation with prefix
    - Usage tracking (with Redis counter pattern)
    - Rate limiting per key
    - Expiration support
    - Scoped permissions
    - IP whitelisting

    Example:
        >>> api_key = await APIKeyModel.create(
        ...     name="Production API Key",
        ...     owner=user,
        ...     scopes=["user:read", "entity:read"],
        ...     rate_limit_per_minute=60
        ... )
        >>> api_key.prefix
        'sk_live_abc123'
    """

    # Key Information
    name: str = Field(..., description="Human-readable key name")
    prefix: Indexed(str) = Field(..., description="Key prefix for identification (e.g., 'sk_live_abc123')")
    key_hash: str = Field(..., description="Hashed full key (never store plain key)")

    # Ownership
    owner: Link[UserModel] = Field(..., description="User who owns this API key")

    # Status & Lifecycle
    status: APIKeyStatus = Field(default=APIKeyStatus.ACTIVE, description="Current key status")
    expires_at: Optional[datetime] = Field(default=None, description="When key expires (None = never)")
    last_used_at: Optional[datetime] = Field(default=None, description="Last time key was used")

    # Usage Tracking (synced from Redis)
    usage_count: int = Field(default=0, description="Total number of times key has been used")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="Max requests per minute")
    rate_limit_per_hour: Optional[int] = Field(default=None, description="Max requests per hour")
    rate_limit_per_day: Optional[int] = Field(default=None, description="Max requests per day")

    # Permissions & Scoping
    scopes: List[str] = Field(default_factory=list, description="Allowed permissions/scopes")
    entity_ids: Optional[List[str]] = Field(default=None, description="Restrict to specific entities (None = all)")

    # Security
    ip_whitelist: Optional[List[str]] = Field(default=None, description="Allowed IP addresses (None = all)")

    # Metadata
    description: Optional[str] = Field(default=None, description="Key description")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    class Settings:
        """Beanie document settings"""
        name = "api_keys"
        indexes = [
            "prefix",
            "owner",
            "status",
            "expires_at",
        ]

    @staticmethod
    def generate_key(prefix_type: str = "sk_live") -> tuple[str, str]:
        """
        Generate a new API key with prefix.

        Args:
            prefix_type: Key prefix (e.g., 'sk_live', 'sk_test')

        Returns:
            tuple[str, str]: (full_key, prefix)
                - full_key: The complete API key to give to user (only shown once)
                - prefix: First 12 chars for identification

        Example:
            >>> full_key, prefix = APIKeyModel.generate_key("sk_live")
            >>> full_key
            'sk_live_abc123def456ghi789jkl012mno345pqr678'
            >>> prefix
            'sk_live_abc1'
        """
        # Generate random key material (32 bytes = 64 hex chars)
        key_material = secrets.token_hex(32)

        # Construct full key
        full_key = f"{prefix_type}_{key_material}"

        # Extract prefix (first 12 characters)
        prefix = full_key[:12]

        return full_key, prefix

    @staticmethod
    def hash_key(full_key: str) -> str:
        """
        Hash an API key for secure storage.

        Args:
            full_key: Full API key string

        Returns:
            str: SHA256 hash of the key

        Example:
            >>> key_hash = APIKeyModel.hash_key("sk_live_abc123...")
        """
        return hashlib.sha256(full_key.encode()).hexdigest()

    def is_active(self) -> bool:
        """
        Check if API key is currently active.

        Returns:
            bool: True if key is active and not expired

        Example:
            >>> if api_key.is_active():
            ...     # Process request
        """
        # Check status
        if self.status != APIKeyStatus.ACTIVE:
            return False

        # Check expiration
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False

        return True

    def has_scope(self, scope: str) -> bool:
        """
        Check if API key has a specific scope/permission.

        Args:
            scope: Scope to check (e.g., "user:read")

        Returns:
            bool: True if key has scope

        Example:
            >>> if api_key.has_scope("user:read"):
            ...     # Allow operation
        """
        # Empty scopes = all permissions
        if not self.scopes:
            return True

        # Check exact match
        if scope in self.scopes:
            return True

        # Check wildcard match
        if ":" in scope:
            resource, action = scope.split(":", 1)
            if f"{resource}:*" in self.scopes:
                return True

        # Check full wildcard
        if "*:*" in self.scopes:
            return True

        return False

    def has_entity_access(self, entity_id: str) -> bool:
        """
        Check if API key has access to a specific entity.

        Args:
            entity_id: Entity ID to check

        Returns:
            bool: True if key has access

        Example:
            >>> if api_key.has_entity_access(entity_id):
            ...     # Allow operation
        """
        # None = access to all entities
        if self.entity_ids is None:
            return True

        return entity_id in self.entity_ids

    def check_ip(self, ip_address: str) -> bool:
        """
        Check if request IP is allowed.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if IP is allowed

        Example:
            >>> if api_key.check_ip(request.client.host):
            ...     # Allow request
        """
        # None = all IPs allowed
        if self.ip_whitelist is None:
            return True

        return ip_address in self.ip_whitelist

    async def update_last_used(self) -> None:
        """
        Update last_used_at timestamp.

        Note: This is called by background sync worker, not on every request.

        Example:
            >>> await api_key.update_last_used()
        """
        self.last_used_at = datetime.now(timezone.utc)
        await self.save()

    @classmethod
    async def get_by_prefix(cls, prefix: str) -> Optional["APIKeyModel"]:
        """
        Get API key by prefix.

        Args:
            prefix: Key prefix (first 12 chars)

        Returns:
            Optional[APIKeyModel]: API key if found

        Example:
            >>> api_key = await APIKeyModel.get_by_prefix("sk_live_abc1")
        """
        return await cls.find_one(cls.prefix == prefix)

    @classmethod
    async def verify_key(cls, full_key: str) -> Optional["APIKeyModel"]:
        """
        Verify and retrieve API key by full key string.

        Args:
            full_key: Full API key string

        Returns:
            Optional[APIKeyModel]: API key if valid, None otherwise

        Example:
            >>> api_key = await APIKeyModel.verify_key("sk_live_abc123...")
            >>> if api_key and api_key.is_active():
            ...     # Valid key
        """
        # Extract prefix
        prefix = full_key[:12]

        # Get key by prefix
        api_key = await cls.get_by_prefix(prefix)
        if not api_key:
            return None

        # Verify hash
        key_hash = cls.hash_key(full_key)
        if api_key.key_hash != key_hash:
            return None

        return api_key
