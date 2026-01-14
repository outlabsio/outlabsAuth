"""
SimpleRBAC Preset

Thin wrapper around OutlabsAuth that disables entity hierarchy.

This preset is for simple applications that need basic role-based
access control without organizational hierarchies.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from outlabs_auth.core.auth import OutlabsAuth


class SimpleRBAC(OutlabsAuth):
    """
    Simple RBAC preset for flat organizational structures.

    Forces disable:
    - Entity hierarchy
    - Context-aware roles
    - ABAC conditions

    Available features:
    - User management
    - Role management
    - Flat permissions
    - JWT authentication
    - Password hashing
    - Account lockout

    Example:
        >>> from outlabs_auth.presets import SimpleRBAC
        >>>
        >>> auth = SimpleRBAC(
        ...     database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
        ...     secret_key="your-secret-key-here"
        ... )
        >>> await auth.initialize()
        >>>
        >>> # Create a user
        >>> async with auth.get_session() as session:
        ...     user = await auth.user_service.create_user(
        ...         session,
        ...         email="john@example.com",
        ...         password="SecurePass123!",
        ...         first_name="John",
        ...         last_name="Doe"
        ...     )
        ...     await session.commit()
        >>>
        >>> # Login
        >>> async with auth.get_session() as session:
        ...     user, tokens = await auth.auth_service.login(
        ...         session,
        ...         email="john@example.com",
        ...         password="SecurePass123!"
        ...     )
        ...     await session.commit()
        >>>
        >>> # Verify token and get user
        >>> async with auth.get_session() as session:
        ...     current_user = await auth.get_current_user(session, tokens.access_token)
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        engine: Optional[AsyncEngine] = None,
        **kwargs,
    ):
        """
        Initialize SimpleRBAC.

        Args:
            database_url: PostgreSQL connection URL
            engine: Existing SQLAlchemy AsyncEngine (optional)
            **kwargs: Additional OutlabsAuth configuration options
                     (see OutlabsAuth.__init__ for all options)

        Note:
            The following options are forced to False in SimpleRBAC:
            - enable_entity_hierarchy
            - enable_context_aware_roles
            - enable_abac
        """
        # Force disable entity hierarchy and related features
        kwargs.pop("enable_entity_hierarchy", None)
        kwargs.pop("enable_context_aware_roles", None)
        kwargs.pop("enable_abac", None)

        super().__init__(
            database_url=database_url,
            engine=engine,
            enable_entity_hierarchy=False,
            enable_context_aware_roles=False,
            enable_abac=False,
            **kwargs,
        )
