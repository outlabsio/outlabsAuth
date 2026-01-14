"""
EnterpriseRBAC Preset

Thin wrapper around OutlabsAuth that enables entity hierarchy and tree permissions.

This preset is for enterprise applications that need hierarchical RBAC
with organizational structures and permission inheritance.

NOTE: EnterpriseRBAC is currently in BETA. Some services still need
migration to PostgreSQL. For production use, consider SimpleRBAC.
"""
import warnings
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine

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
        >>>
        >>> auth = EnterpriseRBAC(
        ...     database_url="postgresql+asyncpg://user:pass@localhost:5432/mydb",
        ...     secret_key="your-secret-key-here"
        ... )
        >>> await auth.initialize()
        >>>
        >>> # Create entity hierarchy
        >>> async with auth.get_session() as session:
        ...     platform = await auth.entity_service.create_entity(
        ...         session,
        ...         name="platform",
        ...         display_name="ACME Platform",
        ...         entity_class=EntityClass.STRUCTURAL,
        ...         entity_type="platform"
        ...     )
        ...     await session.commit()
        >>>
        >>> # Check permissions (tree permissions apply to descendants)
        >>> async with auth.get_session() as session:
        ...     has_perm, source = await auth.permission_service.check_permission(
        ...         session,
        ...         user_id=user.id,
        ...         permission="entity:update",
        ...         entity_id=org.id
        ...     )
        >>> # has_perm=True, source="tree"
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        engine: Optional[AsyncEngine] = None,
        **kwargs,
    ):
        """
        Initialize EnterpriseRBAC.

        Args:
            database_url: PostgreSQL connection URL
            engine: Existing SQLAlchemy AsyncEngine (optional)
            **kwargs: Additional OutlabsAuth configuration options
                     (see OutlabsAuth.__init__ for all options)

        Note:
            The following options are forced in EnterpriseRBAC:
            - enable_entity_hierarchy: True (forced)
            - enable_context_aware_roles: False (default, can override)
            - enable_abac: False (default, can override)
        """
        # Emit beta warning
        warnings.warn(
            "EnterpriseRBAC is currently in BETA. Some services (entity, membership) "
            "still need migration to PostgreSQL. For production use, consider SimpleRBAC.",
            UserWarning,
            stacklevel=2
        )

        # Force enable entity hierarchy
        kwargs.pop("enable_entity_hierarchy", None)

        # Allow context-aware roles and ABAC to be configured by user
        # But default them to False for simplicity
        enable_context_aware = kwargs.pop("enable_context_aware_roles", False)
        enable_abac = kwargs.pop("enable_abac", False)

        super().__init__(
            database_url=database_url,
            engine=engine,
            enable_entity_hierarchy=True,
            enable_context_aware_roles=enable_context_aware,
            enable_abac=enable_abac,
            **kwargs,
        )
