"""
Database Engine Factory and Session Management

Provides async SQLAlchemy engine creation and session factories for PostgreSQL.
"""

from typing import Any, AsyncGenerator, Dict, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool


class DatabaseConfig:
    """
    Database configuration for OutlabsAuth PostgreSQL backend.

    Attributes:
        database_url: PostgreSQL connection URL (must use asyncpg driver)
        echo: If True, log all SQL statements (development only)
        pool_size: Number of persistent connections in the pool
        max_overflow: Maximum connections above pool_size when busy
        pool_timeout: Seconds to wait for a connection before timeout
        pool_recycle: Seconds before connections are recycled (prevents stale connections)
        pool_pre_ping: If True, validate connections before use
        connect_args: Additional arguments passed to asyncpg

    Example:
        >>> config = DatabaseConfig(
        ...     database_url="postgresql+asyncpg://user:pass@localhost:5432/dbname",
        ...     pool_size=5,
        ...     max_overflow=10,
        ... )
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        # Managed Postgres providers (Neon, RDS Proxy idle, Supabase) kill
        # idle connections in the 600-900s range. Recycle well under that
        # window so we rarely hand out a dead connection; pool_pre_ping stays
        # on as the safety net for the remaining cases.
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
        connect_args: Optional[Dict[str, Any]] = None,
    ):
        # Validate URL uses asyncpg driver
        if not database_url.startswith("postgresql+asyncpg://"):
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            else:
                raise ValueError(
                    "database_url must be a PostgreSQL URL. "
                    "Expected format: postgresql+asyncpg://user:pass@host:port/dbname"
                )

        self.database_url = database_url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping
        self.connect_args = connect_args or {}


class DatabasePresets:
    """
    Pre-configured database settings for common deployment environments.

    Use these presets as starting points, then customize as needed:
    - development: Verbose logging, small pool
    - production: Optimized for performance and reliability
    - serverless: No connection pooling (for Lambda, Cloud Functions)
    - testing: In-memory or isolated test database
    """

    @staticmethod
    def development(database_url: str) -> DatabaseConfig:
        """
        Development settings with verbose logging and small pool.

        Features:
        - SQL echo enabled for debugging
        - Small pool (2 connections)
        - Fast recycling for schema changes
        """
        return DatabaseConfig(
            database_url=database_url,
            echo=True,
            pool_size=2,
            max_overflow=3,
            pool_recycle=300,  # 5 minutes
            pool_pre_ping=True,
        )

    @staticmethod
    def production(database_url: str) -> DatabaseConfig:
        """
        Production settings optimized for performance and reliability.

        Features:
        - No SQL echo
        - Larger pool (10 connections)
        - Connection validation
        - 12.5-minute recycling (stays under common 15-minute idle-kill
          windows on managed Postgres providers like Neon and some
          RDS Proxy configurations)
        """
        return DatabaseConfig(
            database_url=database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=750,
            pool_pre_ping=True,
        )

    @staticmethod
    def serverless(database_url: str) -> DatabaseConfig:
        """
        Serverless settings for Lambda, Cloud Functions, etc.

        Features:
        - NullPool (no persistent connections)
        - Each request gets a fresh connection
        - Suitable for short-lived function invocations
        """
        return DatabaseConfig(
            database_url=database_url,
            echo=False,
            pool_size=0,  # Signals to use NullPool
            max_overflow=0,
            pool_pre_ping=False,  # Not needed with NullPool
        )

    @staticmethod
    def testing(database_url: str) -> DatabaseConfig:
        """
        Testing settings for isolated test runs.

        Features:
        - SQL echo for debugging test failures
        - Minimal pool
        - Fast recycling
        """
        return DatabaseConfig(
            database_url=database_url,
            echo=False,  # Set to True if debugging tests
            pool_size=1,
            max_overflow=2,
            pool_recycle=60,
            pool_pre_ping=True,
        )


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    """
    Create an async SQLAlchemy engine with the given configuration.

    Args:
        config: DatabaseConfig instance with connection settings

    Returns:
        AsyncEngine instance ready for use

    Example:
        >>> config = DatabaseConfig("postgresql+asyncpg://...")
        >>> engine = create_engine(config)
        >>> async with engine.connect() as conn:
        ...     result = await conn.execute(text("SELECT 1"))
    """
    # Use NullPool for serverless, otherwise use connection pooling
    if config.pool_size == 0:
        poolclass: type[Any] = NullPool
        pool_kwargs = {}
    else:
        poolclass = AsyncAdaptedQueuePool
        pool_kwargs = {
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_timeout": config.pool_timeout,
            "pool_recycle": config.pool_recycle,
            "pool_pre_ping": config.pool_pre_ping,
        }

    return create_async_engine(
        config.database_url,
        echo=config.echo,
        poolclass=poolclass,
        connect_args=config.connect_args,
        **pool_kwargs,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Create an async session factory bound to the given engine.

    Args:
        engine: AsyncEngine to bind sessions to

    Returns:
        async_sessionmaker that creates AsyncSession instances

    Example:
        >>> engine = create_engine(config)
        >>> session_factory = create_session_factory(engine)
        >>> async with session_factory() as session:
        ...     result = await session.execute(select(User))
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator for database sessions with automatic commit/rollback.

    Use as a FastAPI dependency:

        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_session_dep)):
            ...

    Args:
        session_factory: Session factory to create sessions from

    Yields:
        AsyncSession with automatic transaction management

    Note:
        - Commits on successful completion
        - Rolls back on exception
        - Always closes the session
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
