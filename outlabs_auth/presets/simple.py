"""
SimpleRBAC Preset

Thin wrapper around OutlabsAuth that disables entity hierarchy.

This preset is for simple applications that need basic role-based
access control without organizational hierarchies.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase

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
        >>> from motor.motor_asyncio import AsyncIOMotorClient
        >>>
        >>> client = AsyncIOMotorClient("mongodb://localhost:27017")
        >>> db = client["my_app"]
        >>>
        >>> auth = SimpleRBAC(
        ...     database=db,
        ...     secret_key="your-secret-key-here"
        ... )
        >>> await auth.initialize()
        >>>
        >>> # Create a user
        >>> user = await auth.user_service.create_user(
        ...     email="john@example.com",
        ...     password="SecurePass123!",
        ...     first_name="John",
        ...     last_name="Doe"
        ... )
        >>>
        >>> # Login
        >>> user, tokens = await auth.auth_service.login(
        ...     email="john@example.com",
        ...     password="SecurePass123!"
        ... )
        >>>
        >>> # Verify token and get user
        >>> current_user = await auth.get_current_user(tokens.access_token)
    """

    def __init__(self, database: AsyncIOMotorDatabase, **kwargs):
        """
        Initialize SimpleRBAC.

        Args:
            database: MongoDB database instance
            **kwargs: Additional OutlabsAuth configuration options
                     (see OutlabsAuth.__init__ for all options)

        Note:
            The following options are forced to False in SimpleRBAC:
            - enable_entity_hierarchy
            - enable_context_aware_roles
            - enable_abac
        """
        # Force disable entity hierarchy and related features
        kwargs.pop("enable_entity_hierarchy", None)  # Remove if provided
        kwargs.pop("enable_context_aware_roles", None)
        kwargs.pop("enable_abac", None)

        super().__init__(
            database,
            enable_entity_hierarchy=False,  # Force flat structure
            enable_context_aware_roles=False,  # No context-aware roles
            enable_abac=False,  # No ABAC conditions
            **kwargs
        )
