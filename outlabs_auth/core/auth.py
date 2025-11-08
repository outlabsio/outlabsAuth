"""
Core OutlabsAuth class - unified implementation for all presets

This is the single source of truth for all authentication and authorization logic.
All features are controlled by configuration flags.
"""

import asyncio
from typing import Any, Dict, Optional, Type

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import ConfigurationError
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.token import RefreshTokenModel
from outlabs_auth.models.user import UserModel

# Import observability (v1.5)
from outlabs_auth.observability import ObservabilityConfig, ObservabilityService


class OutlabsAuth:
    """
    Core auth implementation with all features.

    All capabilities are controlled by configuration flags passed to __init__.
    SimpleRBAC and EnterpriseRBAC are thin wrappers that set different defaults.

    Architecture:
    - Single codebase (no code duplication)
    - Feature flags control capabilities
    - Services initialized based on config
    - Models can be customized

    Example:
        >>> auth = OutlabsAuth(
        ...     database=mongo_db,
        ...     secret_key="your-secret-key",
        ...     enable_entity_hierarchy=True
        ... )
        >>> await auth.initialize()
        >>> user = await auth.get_current_user(token)
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        # Core configuration
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 30,
        # Feature flags
        enable_entity_hierarchy: bool = False,
        enable_context_aware_roles: bool = False,
        enable_abac: bool = False,
        enable_caching: bool = False,
        multi_tenant: bool = False,
        enable_audit_log: bool = False,
        enable_notifications: bool = False,
        # Password settings
        password_min_length: int = 8,
        require_special_char: bool = True,
        require_uppercase: bool = True,
        require_digit: bool = True,
        # Security settings
        max_login_attempts: int = 5,
        lockout_duration_minutes: int = 30,
        # API Key settings
        api_key_prefix_length: int = 12,
        api_key_rate_limit_per_minute: int = 60,
        api_key_temporary_lock_minutes: int = 30,
        # Optional dependencies
        redis_enabled: bool = False,
        redis_url: Optional[str] = None,
        cache_ttl_seconds: int = 300,
        notification_service: Optional[Any] = None,  # NotificationService instance
        # Observability (v1.5)
        observability_config: Optional[ObservabilityConfig] = None,
        # Model customization (advanced)
        user_model: Type[UserModel] = UserModel,
        role_model: Type[RoleModel] = RoleModel,
        permission_model: Type[PermissionModel] = PermissionModel,
        entity_model: Optional[Type[Any]] = None,  # Only for EnterpriseRBAC
        # Enterprise settings (only when enable_entity_hierarchy=True)
        max_entity_depth: int = 10,
        allowed_entity_types: Optional[list[str]] = None,
        allow_access_groups: bool = True,
        **kwargs,
    ):
        """
        Initialize OutlabsAuth core.

        Args:
            database: MongoDB database instance (motor AsyncIOMotorDatabase)
            secret_key: JWT signing key (REQUIRED)
            algorithm: JWT algorithm (default: HS256)
            access_token_expire_minutes: Access token TTL (default: 15)
            refresh_token_expire_days: Refresh token TTL (default: 30)

            enable_entity_hierarchy: Enable entity system (EnterpriseRBAC)
            enable_context_aware_roles: Context-based role permissions (optional)
            enable_abac: Attribute-based access control (optional)
            enable_caching: Redis caching for performance (optional, deprecated - use redis_enabled)
            multi_tenant: Multi-tenant isolation (optional)
            enable_audit_log: Audit logging for compliance (optional)
            enable_notifications: Enable notification system (optional)

            redis_enabled: Enable Redis features (caching, counters, activity tracking)
            redis_url: Redis connection URL (required if redis_enabled=True)
            notification_service: NotificationService instance (optional)
            user_model: Custom user model class
            role_model: Custom role model class
            permission_model: Custom permission model class
            entity_model: Custom entity model class (EnterpriseRBAC only)

        Raises:
            ConfigurationError: If configuration is invalid
        """
        self.database = database

        # Validate configuration
        self._validate_config(
            enable_entity_hierarchy=enable_entity_hierarchy,
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            enable_caching=enable_caching,
            redis_url=redis_url,
        )

        # Set redis_enabled based on redis_url if not explicitly set
        # If user provides redis_url, assume they want Redis enabled (unless they explicitly set redis_enabled=False)
        if redis_url and "redis_enabled" not in kwargs:
            redis_enabled = True

        # Create configuration object
        self.config = AuthConfig(
            secret_key=secret_key,
            algorithm=algorithm,
            access_token_expire_minutes=access_token_expire_minutes,
            refresh_token_expire_days=refresh_token_expire_days,
            password_min_length=password_min_length,
            require_special_char=require_special_char,
            require_uppercase=require_uppercase,
            require_digit=require_digit,
            max_login_attempts=max_login_attempts,
            lockout_duration_minutes=lockout_duration_minutes,
            api_key_prefix_length=api_key_prefix_length,
            api_key_rate_limit_per_minute=api_key_rate_limit_per_minute,
            api_key_temporary_lock_minutes=api_key_temporary_lock_minutes,
            enable_entity_hierarchy=enable_entity_hierarchy,
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            enable_caching=enable_caching,
            redis_enabled=redis_enabled,  # Add explicit redis_enabled to config
            multi_tenant=multi_tenant,
            enable_audit_log=enable_audit_log,
            enable_notifications=enable_notifications,
            redis_url=redis_url,
            cache_ttl_seconds=cache_ttl_seconds,
            **kwargs,
        )

        # Store notification service
        self.notification_service = notification_service

        # Initialize observability (v1.5)
        self.observability_config = observability_config or ObservabilityConfig()
        self.observability = None  # Will be initialized in initialize()

        # Store models
        self.user_model = user_model
        self.role_model = role_model
        self.permission_model = permission_model
        self.entity_model = entity_model if enable_entity_hierarchy else None

        # Store enterprise settings
        if enable_entity_hierarchy:
            self.max_entity_depth = max_entity_depth
            self.allowed_entity_types = allowed_entity_types
            self.allow_access_groups = allow_access_groups

        # Services will be initialized by _init_services()
        # These are set to None initially and populated during initialization
        self.auth_service = None
        self.user_service = None
        self.role_service = None
        self.permission_service = None
        self.api_key_service = None
        self.service_token_service = None
        self.entity_service = None
        self.membership_service = None
        self.cache_service = None
        self.activity_tracker = None  # Activity tracking service (requires Redis)

        # Redis client (initialized during _init_services if caching enabled)
        self.redis_client = None

        # Authentication backends and dependency injection
        # These are initialized by _init_backends() and _init_deps()
        self._backends = []
        self._deps = None

        # Background task schedulers
        self._cleanup_task = None  # Token cleanup
        self._activity_sync_task = None  # Activity tracking sync

        # Track initialization state
        self._initialized = False

    def _validate_config(
        self,
        enable_entity_hierarchy: bool,
        enable_context_aware_roles: bool,
        enable_abac: bool,
        enable_caching: bool,
        redis_url: Optional[str],
    ):
        """
        Validate configuration is internally consistent.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Context-aware roles require entity hierarchy
        if enable_context_aware_roles and not enable_entity_hierarchy:
            raise ConfigurationError(
                "enable_context_aware_roles requires enable_entity_hierarchy=True"
            )

        # ABAC can work with or without entity hierarchy
        # (entity-based ABAC requires hierarchy, but attribute-based doesn't)

        # Caching requires Redis URL
        if enable_caching and not redis_url:
            raise ConfigurationError("enable_caching=True requires redis_url parameter")

    async def initialize(self):
        """
        Initialize database collections and indexes.

        This MUST be called after creating OutlabsAuth instance and before using it.
        It sets up Beanie document models and creates database indexes.

        Example:
            >>> auth = OutlabsAuth(database=db, secret_key="secret")
            >>> await auth.initialize()
            >>> # Now ready to use
        """
        if self._initialized:
            return

        # Import EntityModel for forward reference resolution
        # (RoleModel has a Link to EntityModel, so it must be initialized even in SimpleRBAC)
        from outlabs_auth.models.entity import EntityModel

        # Determine which models to initialize
        document_models = [
            self.user_model,
            self.role_model,
            self.permission_model,
            RefreshTokenModel,
            EntityModel,  # Always included for forward ref resolution in RoleModel
        ]

        # Add SimpleRBAC models (when entity hierarchy is disabled)
        if not self.config.enable_entity_hierarchy:
            from outlabs_auth.models.user_role_membership import UserRoleMembership

            document_models.append(UserRoleMembership)

        # Add additional enterprise models if entity hierarchy is enabled
        if self.config.enable_entity_hierarchy:
            if self.entity_model is None:
                # Import default entity models only when needed
                from outlabs_auth.models.closure import EntityClosureModel
                from outlabs_auth.models.membership import EntityMembershipModel

                self.entity_model = EntityModel
                document_models.extend(
                    [
                        EntityMembershipModel,
                        EntityClosureModel,
                    ]
                )
            else:
                # Custom entity model provided
                document_models.append(self.entity_model)

        # Initialize Beanie with all document models
        await init_beanie(database=self.database, document_models=document_models)

        # Initialize observability service (v1.5)
        self.observability = ObservabilityService(self.observability_config)
        await self.observability.initialize()

        # Initialize services
        await self._init_services()

        # Connect to Redis if available
        if self.redis_client:
            await self.redis_client.connect()

        # Initialize authentication backends
        self._init_backends()

        # Initialize dependency injection
        self._init_deps()

        # Start token cleanup scheduler if enabled
        if self.config.enable_token_cleanup and self.config.store_refresh_tokens:
            self._start_token_cleanup_scheduler()

        # Start activity sync scheduler if enabled
        if self.config.enable_activity_tracking and self.activity_tracker:
            self._start_activity_sync_scheduler()

        self._initialized = True

    async def _init_services(self):
        """
        Initialize all services based on configuration.

        Services are conditionally initialized based on feature flags:
        - Core services (always available)
        - Entity services (only if enable_entity_hierarchy=True)
        - Cache service (only if enable_caching=True)
        """
        # Import services
        from outlabs_auth.services.auth import AuthService
        from outlabs_auth.services.permission import BasicPermissionService
        from outlabs_auth.services.role import RoleService
        from outlabs_auth.services.user import UserService

        # Core services (always available) - pass observability (v1.5)
        self.auth_service = AuthService(
            self.database,
            self.config,
            notification_service=self.notification_service,
            activity_tracker=None,  # Set later in _init_services if activity tracking enabled
            observability=self.observability,
        )
        self.user_service = UserService(
            self.database, self.config, self.notification_service
        )
        self.role_service = RoleService(self.database, self.config)

        # Permission service (adapts based on features)
        if self.config.enable_entity_hierarchy:
            # Enterprise permission service with entity context + tree permissions
            from outlabs_auth.services.entity import EntityService
            from outlabs_auth.services.membership import MembershipService
            from outlabs_auth.services.permission import EnterprisePermissionService

            self.permission_service = EnterprisePermissionService(
                self.database, self.config, observability=self.observability
            )
            self.entity_service = EntityService(self.config)
            self.membership_service = MembershipService(self.config)
        else:
            # Basic permission service (flat structure)
            self.permission_service = BasicPermissionService(
                self.database, self.config, observability=self.observability
            )
            self.entity_service = None  # Not available in SimpleRBAC
            self.membership_service = None  # Not available in SimpleRBAC

        # Initialize Redis client if redis_enabled
        if self.config.redis_enabled and self.config.redis_url:
            from outlabs_auth.services.redis_client import RedisClient

            self.redis_client = RedisClient(self.config)
            # Redis connection happens in initialize(), not here
        else:
            self.redis_client = None

        # API Key service (for API key authentication)
        from outlabs_auth.services.api_key import APIKeyService

        self.api_key_service = APIKeyService(
            database=self.database, config=self.config, redis_client=self.redis_client
        )

        # Service Token service (for service-to-service auth)
        from outlabs_auth.services.service_token import ServiceTokenService

        self.service_token_service = ServiceTokenService(config=self.config)

        # Optional services
        if self.config.enable_caching and self.config.redis_url:
            # Cache service (will be implemented in Phase 5)
            # self.cache_service = CacheService(self.config.redis_url)
            self.cache_service = None
        else:
            self.cache_service = None

        # Activity tracking service (DD-049 - requires Redis)
        if self.config.enable_activity_tracking:
            # Validate Redis is available
            if not self.redis_client:
                raise ConfigurationError(
                    "Activity tracking requires Redis. Either:\n"
                    "1. Provide redis_url parameter, or\n"
                    "2. Set enable_activity_tracking=False"
                )

            from outlabs_auth.services.activity_tracker import ActivityTracker

            self.activity_tracker = ActivityTracker(
                redis_client=self.redis_client,
                enabled=True,
                update_user_model=self.config.activity_update_user_model,
                store_user_ids=self.config.activity_store_user_ids,
            )

            # Connect activity_tracker to services that need it
            self.auth_service.activity_tracker = self.activity_tracker
        else:
            self.activity_tracker = None

    def _init_backends(self):
        """
        Initialize authentication backends.

        Creates backends for all available authentication methods:
        - JWT (Bearer token) - always enabled
        - API Key - enabled if api_key_service exists
        - Service Token - enabled if service_token_service exists

        Backends combine transports (how credentials are extracted) with
        strategies (how credentials are validated).
        """
        from outlabs_auth.authentication.backend import AuthBackend
        from outlabs_auth.authentication.strategy import (
            ApiKeyStrategy,
            JWTStrategy,
            ServiceTokenStrategy,
        )
        from outlabs_auth.authentication.transport import (
            ApiKeyTransport,
            BearerTransport,
        )

        self._backends = []

        # JWT Backend (always available)
        jwt_strategy = JWTStrategy(
            secret=self.config.secret_key,
            algorithm=self.config.algorithm,
            audience=self.config.jwt_audience,  # Use configured audience (string, not list)
            redis_client=self.redis_client,  # Pass Redis client for blacklist checking
        )
        jwt_backend = AuthBackend(
            name="jwt", transport=BearerTransport(), strategy=jwt_strategy
        )
        self._backends.append(jwt_backend)

        # API Key Backend (if service exists)
        if self.api_key_service is not None:
            api_key_strategy = ApiKeyStrategy()
            api_key_backend = AuthBackend(
                name="api_key",
                transport=ApiKeyTransport(header_name="X-API-Key"),
                strategy=api_key_strategy,
            )
            self._backends.append(api_key_backend)

        # Service Token Backend (if service exists)
        if self.service_token_service is not None:
            service_token_strategy = ServiceTokenStrategy(
                secret=self.config.secret_key, algorithm=self.config.algorithm
            )
            service_token_backend = AuthBackend(
                name="service_token",
                transport=BearerTransport(),
                strategy=service_token_strategy,
            )
            self._backends.append(service_token_backend)

    def _init_deps(self):
        """
        Initialize AuthDeps for FastAPI dependency injection.

        Creates the deps instance that routers use via auth.deps.require_auth(),
        auth.deps.require_permission(), etc.

        This must be called AFTER _init_services() and _init_backends().
        """
        from outlabs_auth.dependencies import AuthDeps

        self._deps = AuthDeps(
            backends=self._backends,
            user_service=self.user_service,
            api_key_service=self.api_key_service,
            permission_service=self.permission_service,
            role_service=self.role_service,
            entity_service=self.entity_service,
            membership_service=self.membership_service,
            activity_tracker=self.activity_tracker,  # For tracking user activity
        )

    async def get_current_user(self, token: str) -> UserModel:
        """
        Get current authenticated user from JWT token.

        Args:
            token: JWT access token

        Returns:
            UserModel: Authenticated user

        Raises:
            TokenInvalidError: If token is invalid
            TokenExpiredError: If token is expired
            UserNotFoundError: If user doesn't exist
        """
        if not self._initialized:
            raise ConfigurationError(
                "OutlabsAuth not initialized. Call await auth.initialize() first."
            )

        # Will be implemented when AuthService is created in Phase 2
        return await self.auth_service.get_current_user(token)

    @property
    def backends(self) -> list:
        """
        Get list of configured authentication backends.

        Returns:
            List of AuthBackend instances

        Raises:
            ConfigurationError: If backends not initialized
        """
        if not self._backends:
            raise ConfigurationError(
                "Backends not initialized. Call await auth.initialize() first."
            )
        return self._backends

    @property
    def deps(self):
        """
        Get dependency injection instance for FastAPI routes.

        This provides the require_auth(), require_permission(), and require_source()
        methods used to protect routes.

        Returns:
            AuthDeps instance

        Raises:
            ConfigurationError: If deps not initialized

        Example:
            >>> @app.get("/protected")
            >>> async def protected_route(auth_result = Depends(auth.deps.require_auth())):
            ...     return auth_result["user"]
        """
        if self._deps is None:
            raise ConfigurationError(
                "Dependencies not initialized. Call await auth.initialize() first."
            )
        return self._deps

    @property
    def is_enterprise(self) -> bool:
        """Check if entity hierarchy is enabled (EnterpriseRBAC mode)"""
        return self.config.enable_entity_hierarchy

    @property
    def features(self) -> Dict[str, bool]:
        """Get all enabled features as a dictionary"""
        return {
            "entity_hierarchy": self.config.enable_entity_hierarchy,
            "context_aware_roles": self.config.enable_context_aware_roles,
            "abac": self.config.enable_abac,
            "caching": self.config.enable_caching,
            "multi_tenant": self.config.multi_tenant,
            "audit_log": self.config.enable_audit_log,
        }

    def __repr__(self) -> str:
        """String representation showing configuration"""
        preset = "EnterpriseRBAC" if self.is_enterprise else "SimpleRBAC"
        features = [
            k for k, v in self.features.items() if v and k != "entity_hierarchy"
        ]
        features_str = f" + {', '.join(features)}" if features else ""
        return f"<OutlabsAuth: {preset}{features_str}>"

    def _start_token_cleanup_scheduler(self):
        """
        Start background task for token cleanup.

        Runs cleanup_expired_refresh_tokens() every N hours (configured via token_cleanup_interval_hours).
        Only starts if enable_token_cleanup=True and store_refresh_tokens=True.
        """
        import asyncio

        from outlabs_auth.workers.token_cleanup import cleanup_expired_refresh_tokens

        async def cleanup_loop():
            """Background cleanup loop"""
            interval_seconds = self.config.token_cleanup_interval_hours * 3600

            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    stats = await cleanup_expired_refresh_tokens()
                    if stats.get("total", 0) > 0:
                        print(
                            f"[TokenCleanup] Removed {stats['total']} tokens ({stats['expired']} expired, {stats['revoked']} revoked)"
                        )
                except Exception as e:
                    print(f"[TokenCleanup] Error: {e}")

        # Start background task
        import asyncio

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    def _start_activity_sync_scheduler(self):
        """
        Start background task for activity tracking sync.

        Syncs Redis activity data to MongoDB every N seconds (configured via activity_sync_interval).
        Only starts if enable_activity_tracking=True and activity_tracker is available.
        """
        import asyncio

        async def activity_sync_loop():
            """Background activity sync loop"""
            interval_seconds = self.config.activity_sync_interval

            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    stats = await self.activity_tracker.sync_to_mongodb()
                    if stats.get("daily", 0) > 0 or stats.get("monthly", 0) > 0:
                        print(
                            f"[ActivitySync] Synced metrics - "
                            f"DAU: {stats['daily']}, MAU: {stats['monthly']}, QAU: {stats['quarterly']}, "
                            f"users_updated: {stats['users_updated']}, errors: {stats['errors']}"
                        )
                except Exception as e:
                    print(f"[ActivitySync] Error: {e}")

        # Start background task
        import asyncio

        self._activity_sync_task = asyncio.create_task(activity_sync_loop())

    async def shutdown(self):
        """
        Cleanup resources on shutdown.

        Cancels background tasks and closes connections.
        Call this in FastAPI lifespan shutdown.
        """
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._activity_sync_task:
            self._activity_sync_task.cancel()
            try:
                await self._activity_sync_task
            except asyncio.CancelledError:
                pass

        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
