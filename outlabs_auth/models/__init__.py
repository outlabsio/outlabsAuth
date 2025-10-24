"""
OutlabsAuth Models

Public exports for all Beanie ODM models.
"""

# Base
from outlabs_auth.models.base import BaseDocument

# Core models (all presets)
from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.token import RefreshTokenModel

# Entity models (EnterpriseRBAC only)
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel

# OAuth models (v1.2)
from outlabs_auth.models.social_account import SocialAccount
from outlabs_auth.models.oauth_state import OAuthState

__all__ = [
    # Base
    "BaseDocument",
    # Core models
    "UserModel",
    "UserStatus",
    "RoleModel",
    "PermissionModel",
    "RefreshTokenModel",
    # Entity models
    "EntityModel",
    "EntityClass",
    "EntityMembershipModel",
    "EntityClosureModel",
    # OAuth models
    "SocialAccount",
    "OAuthState",
]
