"""
EnterpriseRBAC Preset

Thin wrapper around OutlabsAuth that enables entity hierarchy and tree permissions.

This preset is for enterprise applications that need hierarchical RBAC
with organizational structures and permission inheritance.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase

from outlabs_auth.core.auth import OutlabsAuth


class EnterpriseRBAC(OutlabsAuth):
    """
    Enterprise RBAC preset for hierarchical organizational structures.

    Forces enable:
    - Entity hierarchy
    - Tree permissions via closure table
    - Entity memberships
    - Multi-role assignments

    Optional features (can be enabled):
    - Context-aware roles (default: disabled)
    - ABAC conditions (default: disabled)

    Available features:
    - All SimpleRBAC features
    - Entity hierarchy (structural + access groups)
    - Tree permissions (direct, tree, all)
    - Closure table optimization (O(1) queries)
    - Entity memberships with multiple roles
    - Permission inheritance through hierarchy
    - Entity path and descendant queries

    Example:
        >>> from outlabs_auth.presets import EnterpriseRBAC
        >>> from motor.motor_asyncio import AsyncIOMotorClient
        >>>
        >>> client = AsyncIOMotorClient("mongodb://localhost:27017")
        >>> db = client["my_app"]
        >>>
        >>> auth = EnterpriseRBAC(
        ...     database=db,
        ...     secret_key="your-secret-key-here"
        ... )
        >>> await auth.initialize()
        >>>
        >>> # Create entity hierarchy
        >>> platform = await auth.entity_service.create_entity(
        ...     name="platform",
        ...     display_name="ACME Platform",
        ...     entity_class=EntityClass.STRUCTURAL,
        ...     entity_type="platform"
        ... )
        >>>
        >>> org = await auth.entity_service.create_entity(
        ...     name="acme_corp",
        ...     display_name="ACME Corp",
        ...     entity_class=EntityClass.STRUCTURAL,
        ...     entity_type="organization",
        ...     parent_id=str(platform.id)
        ... )
        >>>
        >>> # Create user
        >>> user = await auth.user_service.create_user(
        ...     email="admin@acme.com",
        ...     password="SecurePass123!",
        ...     first_name="Admin",
        ...     last_name="User"
        ... )
        >>>
        >>> # Create role with tree permissions
        >>> admin_role = await auth.role_service.create_role(
        ...     name="platform_admin",
        ...     display_name="Platform Administrator",
        ...     permissions=["entity:read_tree", "entity:update_tree"],
        ...     entity_id=str(platform.id)
        ... )
        >>>
        >>> # Add user to platform with role
        >>> await auth.membership_service.add_member(
        ...     entity_id=str(platform.id),
        ...     user_id=str(user.id),
        ...     role_ids=[str(admin_role.id)]
        ... )
        >>>
        >>> # Check permissions (tree permissions apply to descendants)
        >>> has_perm, source = await auth.permission_service.check_permission(
        ...     user_id=str(user.id),
        ...     permission="entity:update",
        ...     entity_id=str(org.id)
        ... )
        >>> # has_perm=True, source="tree"
    """

    def __init__(self, database: AsyncIOMotorDatabase, **kwargs):
        """
        Initialize EnterpriseRBAC.

        Args:
            database: MongoDB database instance
            **kwargs: Additional OutlabsAuth configuration options
                     (see OutlabsAuth.__init__ for all options)

        Note:
            The following options are forced in EnterpriseRBAC:
            - enable_entity_hierarchy: True (forced)
            - enable_context_aware_roles: False (default, can override)
            - enable_abac: False (default, can override)
        """
        # Force enable entity hierarchy
        kwargs.pop("enable_entity_hierarchy", None)  # Remove if provided

        # Allow context-aware roles and ABAC to be configured by user
        # But default them to False for simplicity
        enable_context_aware = kwargs.pop("enable_context_aware_roles", False)
        enable_abac = kwargs.pop("enable_abac", False)

        super().__init__(
            database,
            enable_entity_hierarchy=True,  # Force hierarchical structure
            enable_context_aware_roles=enable_context_aware,
            enable_abac=enable_abac,
            **kwargs
        )
