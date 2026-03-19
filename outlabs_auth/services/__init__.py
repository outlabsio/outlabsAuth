"""
OutlabsAuth Services

SQLAlchemy-based service layer for authentication and authorization.
"""

from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.services.access_scope import AccessScopeService, PrincipalEntityScope
from outlabs_auth.services.auth import AuthService, TokenPair
from outlabs_auth.services.base import BaseService
from outlabs_auth.services.cache import CacheService
from outlabs_auth.services.config import ConfigService
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.permission_history import PermissionHistoryService
from outlabs_auth.services.permission import PermissionService
from outlabs_auth.services.role_history import RoleHistoryService
from outlabs_auth.services.role import RoleService
from outlabs_auth.services.service_token import ServiceTokenService
from outlabs_auth.services.user_audit import UserAuditService
from outlabs_auth.services.user import UserService

__all__ = [
    # Base
    "BaseService",
    "CacheService",
    "AccessScopeService",
    "PrincipalEntityScope",
    # Core services
    "UserService",
    "RoleService",
    "RoleHistoryService",
    "PermissionHistoryService",
    "PermissionService",
    "AuthService",
    "TokenPair",
    "ServiceTokenService",
    "UserAuditService",
    # EnterpriseRBAC services
    "EntityService",
    "MembershipService",
    # API Key service
    "APIKeyService",
    # Config service
    "ConfigService",
]
