"""
Core OutlabsAuth class - unified implementation for all presets

PostgreSQL/SQLAlchemy based authentication and authorization.
This is the single source of truth for all authentication and authorization logic.
All features are controlled by configuration flags.
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, Optional, Type

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import Request

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import ConfigurationError
from outlabs_auth.database import DatabaseConfig, create_engine, create_session_factory


class OutlabsAuth:
    """
    Core auth implementation with all features.

    All capabilities are controlled by configuration flags passed to __init__.
    SimpleRBAC and EnterpriseRBAC are thin wrappers that set different defaults.

    Architecture:
    - Single codebase (no code duplication)
    - Feature flags control capabilities
    - Services initialized based on config
    - PostgreSQL with SQLAlchemy async

    Example:
        >>> auth = OutlabsAuth(
        ...     database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
        ...     secret_key="your-secret-key",
        ...     enable_entity_hierarchy=True
        ... )
        >>> await auth.initialize()
        >>> user = await auth.get_current_user(token)
    """

    def __init__(
        self,
        # Database configuration
        database_url: Optional[str] = None,
        engine: Optional[AsyncEngine] = None,
        auto_migrate: bool = False,
        echo_sql: bool = False,
        # Core configuration
        secret_key: str = "",
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
        notification_service: Optional[Any] = None,
        # Observability
        observability_config: Optional[Any] = None,
        # Enterprise settings (only when enable_entity_hierarchy=True)
        max_entity_depth: int = 10,
        allowed_entity_types: Optional[list[str]] = None,
        allow_access_groups: bool = True,
        **kwargs,
    ):
        """
        Initialize OutlabsAuth core.

        Args:
            database_url: PostgreSQL connection URL (required if engine not provided)
            engine: Existing SQLAlchemy AsyncEngine (optional, takes precedence over database_url)
            auto_migrate: Run Alembic migrations on startup
            echo_sql: Echo SQL statements for debugging
            secret_key: JWT signing key (REQUIRED)
            algorithm: JWT algorithm (default: HS256)
            access_token_expire_minutes: Access token TTL (default: 15)
            refresh_token_expire_days: Refresh token TTL (default: 30)

            enable_entity_hierarchy: Enable entity system (EnterpriseRBAC)
            enable_context_aware_roles: Context-based role permissions (optional)
            enable_abac: Attribute-based access control (optional)
            enable_caching: Redis caching for performance (optional)
            multi_tenant: Multi-tenant isolation (optional)
            enable_audit_log: Audit logging for compliance (optional)
            enable_notifications: Enable notification system (optional)

            redis_enabled: Enable Redis features (caching, counters, activity tracking)
            redis_url: Redis connection URL (required if redis_enabled=True)
            notification_service: NotificationService instance (optional)

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate we have either database_url or engine
        if not database_url and not engine:
            raise ConfigurationError("Either database_url or engine must be provided")

        if not secret_key:
            raise ConfigurationError("secret_key is required")

        # Validate configuration
        self._validate_config(
            enable_entity_hierarchy=enable_entity_hierarchy,
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            enable_caching=enable_caching,
            redis_url=redis_url,
        )

        # Set redis_enabled based on redis_url if not explicitly set
        if redis_url and "redis_enabled" not in kwargs:
            redis_enabled = True

        # Create configuration object
        self.config = AuthConfig(
            database_url=database_url,
            auto_migrate=auto_migrate,
            echo_sql=echo_sql,
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
            redis_enabled=redis_enabled,
            multi_tenant=multi_tenant,
            enable_audit_log=enable_audit_log,
            redis_url=redis_url,
            cache_ttl_seconds=cache_ttl_seconds,
            **kwargs,
        )

        # Store notification service
        self.notification_service = notification_service

        # Initialize observability
        self.observability_config = observability_config
        self.observability = None

        # Store enterprise settings
        if enable_entity_hierarchy:
            self.max_entity_depth = max_entity_depth
            self.allowed_entity_types = allowed_entity_types
            self.allow_access_groups = allow_access_groups

        # Database engine and session factory
        self._engine = engine
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

        # Services will be initialized by _init_services()
        self.auth_service = None
        self.user_service = None
        self.role_service = None
        self.permission_service = None
        self.api_key_service = None
        self.service_token_service = None
        self.entity_service = None
        self.membership_service = None
        self.cache_service = None
        self.activity_tracker = None

        # Redis client
        self.redis_client = None

        # Authentication backends and dependency injection
        self._backends = []
        self._deps = None

        # Background task schedulers
        self._cleanup_task = None
        self._activity_sync_task = None

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
        """Validate configuration is internally consistent."""
        # Context-aware roles require entity hierarchy
        if enable_context_aware_roles and not enable_entity_hierarchy:
            raise ConfigurationError(
                "enable_context_aware_roles requires enable_entity_hierarchy=True"
            )

        # Caching requires Redis URL
        if enable_caching and not redis_url:
            raise ConfigurationError("enable_caching=True requires redis_url parameter")

    async def initialize(self):
        """
        Initialize database and services.

        This MUST be called after creating OutlabsAuth instance and before using it.
        It sets up the database connection, optionally runs migrations, and initializes services.

        Example:
            >>> auth = OutlabsAuth(database_url="...", secret_key="secret")
            >>> await auth.initialize()
            >>> # Now ready to use
        """
        if self._initialized:
            return

        # Create engine if not provided
        if self._engine is None:
            db_config = DatabaseConfig(
                database_url=self.config.database_url,
                echo=self.config.echo_sql,
            )
            self._engine = create_engine(db_config)

        # Create session factory
        self._session_factory = create_session_factory(self._engine)

        # Run migrations if auto_migrate is enabled
        if self.config.auto_migrate:
            await self._run_migrations()

        # Initialize observability service
        if self.observability_config:
            from outlabs_auth.observability import ObservabilityService

            self.observability = ObservabilityService(self.observability_config)
            await self.observability.initialize()
            self.observability.instrument_sqlalchemy(self._engine)

        # Initialize services
        await self._init_services()

        # Connect to Redis if available
        if self.redis_client:
            await self.redis_client.connect()

        # Initialize authentication backends
        self._init_backends()

        # Initialize dependency injection
        self._init_deps()

        # Start background tasks
        if self.config.enable_token_cleanup and self.config.store_refresh_tokens:
            self._start_token_cleanup_scheduler()

        if self.config.enable_activity_tracking and self.activity_tracker:
            self._start_activity_sync_scheduler()

        self._initialized = True

    async def _run_migrations(self):
        """Run Alembic migrations to head."""
        from outlabs_auth.cli import run_migrations

        await run_migrations(self.config.database_url)

    async def _init_services(self):
        """Initialize all services based on configuration."""
        from outlabs_auth.services.api_key import APIKeyService
        from outlabs_auth.services.auth import AuthService
        from outlabs_auth.services.permission import PermissionService
        from outlabs_auth.services.role import RoleService
        from outlabs_auth.services.user import UserService

        # Core services
        self.auth_service = AuthService(
            self.config,
            notification_service=self.notification_service,
            activity_tracker=None,  # Set later if activity tracking enabled
            observability=self.observability,
        )
        self.user_service = UserService(
            self.config,
            notification_service=self.notification_service,
        )
        self.role_service = RoleService(self.config)
        self.permission_service = PermissionService(
            self.config,
            observability=self.observability,
        )

        # Initialize Redis client if enabled
        if self.config.redis_enabled and self.config.redis_url:
            from outlabs_auth.services.redis_client import RedisClient

            self.redis_client = RedisClient(self.config)

        # Entity and membership services for EnterpriseRBAC
        if self.config.enable_entity_hierarchy:
            from outlabs_auth.services.entity import EntityService
            from outlabs_auth.services.membership import MembershipService

            self.entity_service = EntityService(
                self.config, redis_client=self.redis_client
            )
            self.membership_service = MembershipService(self.config)

        # API Key service
        self.api_key_service = APIKeyService(
            self.config, redis_client=self.redis_client
        )

        # Service Token service
        # TODO: Update ServiceTokenService for PostgreSQL
        # self.service_token_service = ServiceTokenService(...)

        # Activity tracking
        if self.config.enable_activity_tracking:
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
            self.auth_service.activity_tracker = self.activity_tracker

    def _init_backends(self):
        """Initialize authentication backends."""
        from outlabs_auth.authentication.backend import AuthBackend
        from outlabs_auth.authentication.strategy import JWTStrategy
        from outlabs_auth.authentication.transport import BearerTransport

        self._backends = []

        # JWT Backend (always available)
        jwt_strategy = JWTStrategy(
            secret=self.config.secret_key,
            algorithm=self.config.algorithm,
            audience=self.config.jwt_audience,
            redis_client=self.redis_client,
        )
        jwt_backend = AuthBackend(
            name="jwt",
            transport=BearerTransport(),
            strategy=jwt_strategy,
        )
        self._backends.append(jwt_backend)

        # API Key Backend
        if self.api_key_service is not None:
            from outlabs_auth.authentication.strategy import ApiKeyStrategy
            from outlabs_auth.authentication.transport import ApiKeyTransport

            api_key_strategy = ApiKeyStrategy()
            api_key_backend = AuthBackend(
                name="api_key",
                transport=ApiKeyTransport(header_name="X-API-Key"),
                strategy=api_key_strategy,
            )
            self._backends.append(api_key_backend)

        # Service Token Backend
        if self.service_token_service is not None:
            from outlabs_auth.authentication.strategy import ServiceTokenStrategy

            service_token_strategy = ServiceTokenStrategy(
                secret=self.config.secret_key,
                algorithm=self.config.algorithm,
            )
            service_token_backend = AuthBackend(
                name="service_token",
                transport=BearerTransport(),
                strategy=service_token_strategy,
            )
            self._backends.append(service_token_backend)

    def _init_deps(self):
        """Initialize AuthDeps for FastAPI dependency injection."""
        from outlabs_auth.dependencies import AuthDeps

        self._deps = AuthDeps(
            backends=self._backends,
            user_service=self.user_service,
            api_key_service=self.api_key_service,
            permission_service=self.permission_service,
            role_service=self.role_service,
            entity_service=self.entity_service,
            membership_service=self.membership_service,
            activity_tracker=self.activity_tracker,
            get_session=self.uow,  # Shared per-request unit-of-work
        )

    def get_session(self) -> AsyncSession:
        """
        Get a new database session.

        Use this with async context manager:
            async with auth.get_session() as session:
                user = await auth.user_service.get_user_by_id(session, user_id)

        Returns:
            AsyncSession context manager
        """
        if self._session_factory is None:
            raise ConfigurationError(
                "Database not initialized. Call await auth.initialize() first."
            )
        return self._session_factory()

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency that yields a database session.

        Prefer this over `Depends(auth.get_session)` so sessions are closed reliably.

        Example:
            >>> @app.get("/users")
            >>> async def list_users(session: AsyncSession = Depends(auth.session)):
            ...     ...
        """
        if self._session_factory is None:
            raise ConfigurationError(
                "Database not initialized. Call await auth.initialize() first."
            )

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def uow(self, request: Request) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency that yields a database session and commits on success for
        write HTTP methods.

        This implements a simple "unit of work" per-request:
        - on success: commit for write methods (POST/PUT/PATCH/DELETE), else rollback
        - on error: rollback
        - always: close session

        Use this for request handlers and wire auth/permission dependencies to it
        so the whole request shares a single session.
        """
        if self._session_factory is None:
            raise ConfigurationError(
                "Database not initialized. Call await auth.initialize() first."
            )

        async with self._session_factory() as session:
            try:
                yield session
                if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                    await session.commit()
                else:
                    await session.rollback()
            except Exception:
                await session.rollback()
                raise

    async def get_current_user(self, session: AsyncSession, token: str):
        """
        Get current authenticated user from JWT token.

        Args:
            session: Database session
            token: JWT access token

        Returns:
            User: Authenticated user

        Raises:
            TokenInvalidError: If token is invalid
            TokenExpiredError: If token is expired
            UserNotFoundError: If user doesn't exist
        """
        if not self._initialized:
            raise ConfigurationError(
                "OutlabsAuth not initialized. Call await auth.initialize() first."
            )

        return await self.auth_service.get_current_user(session, token)

    @property
    def engine(self) -> AsyncEngine:
        """Get the SQLAlchemy async engine."""
        if self._engine is None:
            raise ConfigurationError(
                "Database not initialized. Call await auth.initialize() first."
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory for creating database sessions."""
        if self._session_factory is None:
            raise ConfigurationError(
                "Database not initialized. Call await auth.initialize() first."
            )
        return self._session_factory

    @property
    def backends(self) -> list:
        """Get list of configured authentication backends."""
        if not self._backends:
            raise ConfigurationError(
                "Backends not initialized. Call await auth.initialize() first."
            )
        return self._backends

    @property
    def deps(self):
        """
        Get dependency injection instance for FastAPI routes.

        Returns:
            AuthDeps instance

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

    # ---------------------------------------------------------------------
    # FastAPI dependency convenience wrappers (documented API)
    # ---------------------------------------------------------------------

    def require_permission(self, *permissions: str, require_all: bool = False):
        return self.deps.require_permission(*permissions, require_all=require_all)

    def require_entity_permission(
        self, permission: str, entity_id_param: str = "entity_id"
    ):
        return self.deps.require_entity_permission(
            permission, entity_id_param=entity_id_param
        )

    def require_tree_permission(
        self,
        permission: str,
        entity_id_field: str,
        *,
        source: str = "path",
    ):
        return self.deps.require_tree_permission(
            permission, entity_id_field, source=source
        )

    @property
    def is_enterprise(self) -> bool:
        """Check if entity hierarchy is enabled (EnterpriseRBAC mode)."""
        return self.config.enable_entity_hierarchy

    @property
    def features(self) -> Dict[str, bool]:
        """Get all enabled features as a dictionary."""
        return {
            "entity_hierarchy": self.config.enable_entity_hierarchy,
            "context_aware_roles": self.config.enable_context_aware_roles,
            "abac": self.config.enable_abac,
            "caching": self.config.enable_caching,
            "multi_tenant": self.config.multi_tenant,
            "audit_log": self.config.enable_audit_log,
        }

    def __repr__(self) -> str:
        """String representation showing configuration."""
        preset = "EnterpriseRBAC" if self.is_enterprise else "SimpleRBAC"
        features = [
            k for k, v in self.features.items() if v and k != "entity_hierarchy"
        ]
        features_str = f" + {', '.join(features)}" if features else ""
        return f"<OutlabsAuth: {preset}{features_str}>"

    def _start_token_cleanup_scheduler(self):
        """Start background task for token cleanup."""

        async def cleanup_loop():
            interval_seconds = self.config.token_cleanup_interval_hours * 3600

            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    from outlabs_auth.workers.token_cleanup import (
                        cleanup_expired_refresh_tokens,
                    )

                    async with self.get_session() as session:
                        await cleanup_expired_refresh_tokens(session)
                        await session.commit()
                except Exception as e:
                    print(f"[TokenCleanup] Error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    def _start_activity_sync_scheduler(self):
        """Start background task for activity tracking sync."""

        async def activity_sync_loop():
            interval_seconds = self.config.activity_sync_interval

            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    if self.activity_tracker:
                        async with self.get_session() as session:
                            stats = await self.activity_tracker.sync_to_database(
                                session
                            )
                            await session.commit()
                        if stats.get("daily", 0) > 0 or stats.get("monthly", 0) > 0:
                            print(
                                f"[ActivitySync] Synced metrics - "
                                f"DAU: {stats['daily']}, MAU: {stats['monthly']}"
                            )
                except Exception as e:
                    print(f"[ActivitySync] Error: {e}")

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
            await self.redis_client.disconnect()

        if self.observability:
            await self.observability.shutdown()

        # Close database engine
        if self._engine:
            await self._engine.dispose()

    def instrument_fastapi(
        self,
        app: FastAPI,
        *,
        debug: bool = False,
        include_metrics: bool = True,
    ) -> None:
        """
        Install OutlabsAuth observability + error handling onto a FastAPI app.

        - Correlation ID middleware (if observability enabled)
        - Centralized exception handlers (uses observability for logging)
        - /metrics endpoint (if enabled and include_metrics=True)
        """
        from outlabs_auth.fastapi import register_exception_handlers

        register_exception_handlers(app, debug=debug, observability=self.observability)

        if self.observability:
            from outlabs_auth.observability import (
                CorrelationIDMiddleware,
                create_metrics_router,
            )

            app.add_middleware(CorrelationIDMiddleware, obs_service=self.observability)
            if include_metrics:
                app.include_router(create_metrics_router(self.observability))
