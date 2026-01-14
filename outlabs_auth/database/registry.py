"""
Model Registry for OutlabsAuth

Manages model registration based on feature flags (SimpleRBAC vs EnterpriseRBAC).
"""

from typing import List, Type
from sqlmodel import SQLModel


class ModelRegistry:
    """
    Registry for OutlabsAuth SQLModel models based on feature flags.

    Models are grouped by preset:
    - CORE_MODELS: Always included (users, roles, permissions, etc.)
    - SIMPLE_RBAC_MODELS: Only for SimpleRBAC preset (user_role_memberships)
    - ENTERPRISE_RBAC_MODELS: Only for EnterpriseRBAC preset (entities, memberships, closure)

    Usage:
        # Get all models for SimpleRBAC
        models = ModelRegistry.get_models(enable_entity_hierarchy=False)

        # Get all models for EnterpriseRBAC
        models = ModelRegistry.get_models(enable_entity_hierarchy=True)

        # Get metadata for Alembic migrations
        metadata = ModelRegistry.get_metadata(enable_entity_hierarchy=True)
    """

    # Core models (always included regardless of preset)
    CORE_MODEL_NAMES: List[str] = [
        "User",
        "Role",
        "Permission",
        "RefreshToken",
        "APIKey",
        "SocialAccount",
        "OAuthState",
        "ActivityMetric",
    ]

    # SimpleRBAC-specific models (flat role structure)
    SIMPLE_RBAC_MODEL_NAMES: List[str] = [
        "UserRoleMembership",
    ]

    # EnterpriseRBAC-specific models (hierarchical entities)
    ENTERPRISE_RBAC_MODEL_NAMES: List[str] = [
        "Entity",
        "EntityMembership",
        "EntityMembershipRole",  # Junction table
        "EntityClosure",
    ]

    @classmethod
    def get_model_names(
        cls,
        enable_entity_hierarchy: bool = False,
    ) -> List[str]:
        """
        Get list of model names based on feature flags.

        Args:
            enable_entity_hierarchy: If True, include EnterpriseRBAC models.
                                     If False, include SimpleRBAC models.

        Returns:
            List of model class names to be registered.
        """
        names = cls.CORE_MODEL_NAMES.copy()

        if enable_entity_hierarchy:
            names.extend(cls.ENTERPRISE_RBAC_MODEL_NAMES)
        else:
            names.extend(cls.SIMPLE_RBAC_MODEL_NAMES)

        return names

    @classmethod
    def get_models(
        cls,
        enable_entity_hierarchy: bool = False,
    ) -> List[Type[SQLModel]]:
        """
        Get list of model classes based on feature flags.

        This imports and returns the actual model classes. Use this to
        ensure all models are registered with SQLModel.metadata.

        Args:
            enable_entity_hierarchy: If True, include EnterpriseRBAC models.
                                     If False, include SimpleRBAC models.

        Returns:
            List of SQLModel table classes.

        Note:
            Models are imported lazily to avoid circular import issues.
            This method should be called after all models are defined.
        """
        # Lazy import to avoid circular dependencies
        # Models will be in outlabs_auth/models/sql/
        # For now, return empty list until models are implemented
        # TODO: Implement after Phase 2 (Model Migration)

        models: List[Type[SQLModel]] = []

        # Core models (always included)
        # from outlabs_auth.models.sql.user import User
        # from outlabs_auth.models.sql.role import Role
        # from outlabs_auth.models.sql.permission import Permission
        # from outlabs_auth.models.sql.token import RefreshToken
        # from outlabs_auth.models.sql.api_key import APIKey
        # from outlabs_auth.models.sql.social_account import SocialAccount
        # from outlabs_auth.models.sql.oauth_state import OAuthState
        # from outlabs_auth.models.sql.activity_metric import ActivityMetric
        # models.extend([User, Role, Permission, RefreshToken, APIKey,
        #                SocialAccount, OAuthState, ActivityMetric])

        # if enable_entity_hierarchy:
        #     # EnterpriseRBAC models
        #     from outlabs_auth.models.sql.entity import Entity
        #     from outlabs_auth.models.sql.entity_membership import (
        #         EntityMembership, EntityMembershipRole
        #     )
        #     from outlabs_auth.models.sql.closure import EntityClosure
        #     models.extend([Entity, EntityMembership, EntityMembershipRole, EntityClosure])
        # else:
        #     # SimpleRBAC models
        #     from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
        #     models.append(UserRoleMembership)

        return models

    @classmethod
    def get_metadata(cls, enable_entity_hierarchy: bool = False):
        """
        Get SQLAlchemy metadata with appropriate models registered.

        This ensures all relevant models are imported, which registers
        their tables with SQLModel.metadata.

        Args:
            enable_entity_hierarchy: If True, include EnterpriseRBAC models.

        Returns:
            SQLModel.metadata with all tables registered.
        """
        # Import models to register them
        cls.get_models(enable_entity_hierarchy=enable_entity_hierarchy)

        return SQLModel.metadata

    @classmethod
    def get_table_names(
        cls,
        enable_entity_hierarchy: bool = False,
    ) -> List[str]:
        """
        Get list of expected table names based on feature flags.

        Useful for validation that migrations have been run.

        Args:
            enable_entity_hierarchy: If True, include EnterpriseRBAC tables.

        Returns:
            List of PostgreSQL table names.
        """
        tables = [
            "users",
            "roles",
            "permissions",
            "refresh_tokens",
            "api_keys",
            "social_accounts",
            "oauth_states",
            "activity_metrics",
        ]

        if enable_entity_hierarchy:
            tables.extend([
                "entities",
                "entity_memberships",
                "entity_membership_roles",
                "entity_closure",
            ])
        else:
            tables.append("user_role_memberships")

        return tables
