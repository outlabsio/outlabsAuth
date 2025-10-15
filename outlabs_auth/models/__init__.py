"""
OutlabsAuth Models

Public exports for all Beanie ODM models.
"""

# Base
from outlabs_auth.models.base import BaseDocument

# Core models (all presets)
from outlabs_auth.models.user import UserModel, UserProfile, UserStatus
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.token import RefreshTokenModel

# Entity models (EnterpriseRBAC only)
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel

__all__ = [
    # Base
    "BaseDocument",
    # Core models
    "UserModel",
    "UserProfile",
    "UserStatus",
    "RoleModel",
    "PermissionModel",
    "RefreshTokenModel",
    # Entity models
    "EntityModel",
    "EntityClass",
    "EntityMembershipModel",
    "EntityClosureModel",
]
