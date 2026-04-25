"""
Configuration classes for OutlabsAuth library
"""

from typing import Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthConfig(BaseModel):
    """
    Base configuration for all OutlabsAuth presets.

    This configuration is shared by SimpleRBAC and EnterpriseRBAC.
    """

    # Database Settings (PostgreSQL)
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@localhost:5432/dbname)",
    )
    database_schema: Optional[str] = Field(
        default=None,
        description="Optional PostgreSQL schema for auth tables and migrations",
    )
    auto_migrate: bool = Field(default=False, description="Automatically run database migrations on startup")
    echo_sql: bool = Field(default=False, description="Echo SQL statements to stdout (for debugging)")

    # JWT Settings
    secret_key: str = Field(..., description="Secret key for JWT signing")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_audience: str = Field(
        default="outlabs-auth",
        description="JWT audience claim for cross-application security",
    )
    access_token_expire_minutes: int = Field(default=15, description="Access token TTL in minutes")
    refresh_token_expire_days: int = Field(default=30, description="Refresh token TTL in days")

    # Password Settings
    password_min_length: int = Field(default=8, description="Minimum password length")
    require_special_char: bool = Field(default=True, description="Require special character in password")
    require_uppercase: bool = Field(default=True, description="Require uppercase letter in password")
    require_digit: bool = Field(default=True, description="Require digit in password")

    # Argon2id tuning. Defaults meet OWASP 2023 minimum (m=19 MiB, t=2, p=1)
    # and typically hash in 30-80ms. Raise memory/time for higher security
    # budgets; raise parallelism on multi-core machines. Applied at library init.
    argon2_time_cost: int = Field(default=2, description="Argon2id iterations (OWASP min: 2)")
    argon2_memory_cost_kib: int = Field(default=19456, description="Argon2id memory in KiB (OWASP min: 19 MiB)")
    argon2_parallelism: int = Field(default=1, description="Argon2id parallelism (OWASP min: 1)")

    # Security
    max_login_attempts: int = Field(default=5, description="Max failed login attempts before lockout")
    lockout_duration_minutes: int = Field(default=30, description="Account lockout duration in minutes")

    # Token Revocation Strategy
    enable_token_blacklist: bool = Field(
        default=False,
        description="Enable immediate access token blacklisting (requires Redis)",
    )
    store_refresh_tokens: bool = Field(
        default=True,
        description="Store refresh tokens in PostgreSQL for revocation. Set to False for stateless-only JWT.",
    )
    enable_token_cleanup: bool = Field(default=True, description="Enable automatic cleanup of expired/revoked tokens")
    token_cleanup_interval_hours: int = Field(default=24, description="Hours between token cleanup runs")

    # Feature Flags (Core - controlled by OutlabsAuth base class)
    enable_entity_hierarchy: bool = Field(default=False, description="Enable entity hierarchy (EnterpriseRBAC)")
    enable_context_aware_roles: bool = Field(
        default=False,
        description="Enable context-aware roles (EnterpriseRBAC optional)",
    )
    enable_abac: bool = Field(default=False, description="Enable ABAC conditions (EnterpriseRBAC optional)")
    enable_caching: bool = Field(
        default=False,
        description="Enable Redis-backed permission caching. OutlabsAuth enables this by default when Redis is enabled.",
    )
    enable_audit_log: bool = Field(default=False, description="Enable audit logging (optional)")
    trust_resource_context_header: bool = Field(
        default=False,
        description="Trust X-Resource-Context header from clients for ABAC resource attributes",
    )
    store_oauth_provider_tokens: bool = Field(
        default=False,
        description="Persist OAuth provider access/refresh tokens in the social_accounts table",
    )
    oauth_token_encryption_key: Optional[str] = Field(
        default=None,
        description="Fernet key used to encrypt OAuth provider tokens at rest",
    )
    enable_invitations: bool = Field(
        default=True,
        description="Enable user invitation system (invite by email, set password later)",
    )
    invite_token_expire_days: int = Field(
        default=7,
        description="Number of days before an invite token expires",
    )
    enable_magic_links: bool = Field(
        default=False,
        description="Enable email magic-link authentication",
    )
    magic_link_expire_minutes: int = Field(
        default=15,
        description="Number of minutes before a magic-link token expires",
    )
    magic_link_request_rate_limit_max: int = Field(
        default=3,
        description="Maximum magic-link requests per email in the rate-limit window",
    )
    magic_link_request_rate_limit_window_seconds: int = Field(
        default=300,
        description="Magic-link request rate-limit window in seconds",
    )

    # Redis Configuration (recommended for production counters, rate limits, and caching)
    redis_enabled: bool = Field(default=False, description="Enable Redis-backed auth features")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL (overrides host/port)")

    # Cache TTL Settings
    cache_ttl_seconds: int = Field(default=300, description="Default cache TTL in seconds (5 minutes)")
    cache_permission_ttl: int = Field(default=900, description="Permission cache TTL in seconds (15 minutes)")
    cache_entity_ttl: int = Field(default=600, description="Entity cache TTL in seconds (10 minutes)")
    api_key_auth_snapshot_ttl: int = Field(
        default=60,
        description="Compiled API-key auth snapshot TTL in seconds for permission-dependency hot paths",
    )

    # Pub/Sub Channels
    redis_invalidation_channel: str = Field(
        default="auth:cache:invalidate",
        description="Redis Pub/Sub channel for cache invalidation",
    )

    # API Key Settings (v1.3 - included in core)
    api_key_prefix_length: int = Field(default=12, description="API key prefix length")
    api_key_rate_limit_per_minute: int = Field(default=60, description="Default rate limit per API key")
    api_key_temporary_lock_minutes: int = Field(default=30, description="Temporary lock duration after failures")
    api_key_personal_allowed_action_prefixes: list[str] = Field(
        default_factory=lambda: ["read", "list", "search", "view", "get", "update"],
        description="Action prefixes allowed for personal API keys in EnterpriseRBAC v1",
    )
    api_key_personal_excluded_resources: list[str] = Field(
        default_factory=lambda: ["api_key", "service_token"],
        description="Permission resources that personal API keys may never request",
    )
    api_key_personal_allow_inherit_from_tree: bool = Field(
        default=True,
        description="Whether personal API keys may inherit anchor access to descendant entities",
    )
    api_key_system_allowed_action_prefixes: list[str] = Field(
        default_factory=lambda: [
            "create",
            "read",
            "list",
            "search",
            "view",
            "get",
            "update",
            "delete",
            "write",
            "run",
            "execute",
            "trigger",
            "control",
            "sync",
            "import",
            "export",
            "generate",
            "manage",
        ],
        description="Action prefixes allowed for system integration API keys in EnterpriseRBAC",
    )
    api_key_system_excluded_resources: list[str] = Field(
        default_factory=lambda: ["api_key", "service_token", "integration_principal"],
        description="Permission resources system integration API keys may never request",
    )

    # Activity Tracking Settings (DD-049 - requires Redis)
    enable_activity_tracking: bool = Field(
        default=False,
        description="Enable DAU/MAU/WAU/QAU activity tracking (requires Redis)",
    )
    activity_sync_interval: int = Field(
        default=1800,
        description="Activity sync interval in seconds (default: 30 minutes)",
    )
    activity_update_user_model: bool = Field(
        default=True,
        description="Update UserModel.last_activity field via background sync",
    )
    activity_store_user_ids: bool = Field(
        default=False,
        description="Store user IDs in ActivityMetric for cohort analysis (increases storage)",
    )
    activity_ttl_days: int = Field(default=90, description="Days to keep ActivityMetric records (default: 90 days)")

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _resolve_redis_defaults(self) -> Self:
        """
        Treat Redis configuration as the source of truth while preserving explicit opt-outs.

        Direct AuthConfig construction should behave the same as OutlabsAuth:
        providing redis_url enables Redis features and permission caching unless
        the caller explicitly sets redis_enabled=False or enable_caching=False.
        """
        fields_set = self.model_fields_set

        if self.redis_url and "redis_enabled" not in fields_set:
            object.__setattr__(self, "redis_enabled", True)

        if self.redis_enabled and "enable_caching" not in fields_set:
            object.__setattr__(self, "enable_caching", True)

        if self.enable_caching and not self.redis_enabled:
            raise ValueError("enable_caching=True requires Redis; provide redis_url or redis_enabled=True")

        return self


class SimpleConfig(AuthConfig):
    """
    Configuration for SimpleRBAC preset.

    SimpleRBAC disables entity hierarchy and advanced features.
    """

    # Force disable entity hierarchy
    enable_entity_hierarchy: bool = Field(default=False, frozen=True)
    enable_context_aware_roles: bool = Field(default=False, frozen=True)
    enable_abac: bool = Field(default=False, frozen=True)


class EnterpriseConfig(AuthConfig):
    """
    Configuration for EnterpriseRBAC preset.

    EnterpriseRBAC always enables entity hierarchy.
    Optional features can be enabled via flags.
    """

    # Force enable entity hierarchy
    enable_entity_hierarchy: bool = Field(default=True, frozen=True)

    # Entity Settings (always enabled when entity hierarchy is on)
    max_entity_depth: int = Field(default=10, description="Maximum depth of entity hierarchy")
    allowed_entity_types: Optional[list[str]] = Field(default=None, description="Allowed entity types (None = any)")
    allow_access_groups: bool = Field(default=True, description="Allow ACCESS_GROUP entities")

    # Optional Features (opt-in)
    # enable_context_aware_roles: bool - inherited from AuthConfig
    # enable_abac: bool - inherited from AuthConfig
    # enable_caching: bool - inherited from AuthConfig
    # enable_audit_log: bool - inherited from AuthConfig
