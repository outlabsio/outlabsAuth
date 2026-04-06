"""
Router factories for OutlabsAuth.

Pre-built FastAPI routers for quick setup (DD-041).
"""

from outlabs_auth.routers.api_keys import get_api_keys_router
from outlabs_auth.routers.api_key_admin import get_api_key_admin_router
from outlabs_auth.routers.auth import get_auth_router
from outlabs_auth.routers.config import get_config_router
from outlabs_auth.routers.entities import get_entities_router
from outlabs_auth.routers.integration_principals import get_integration_principals_router
from outlabs_auth.routers.memberships import get_memberships_router
from outlabs_auth.routers.permissions import get_permissions_router
from outlabs_auth.routers.roles import get_roles_router
from outlabs_auth.routers.self_service import get_self_service_users_router
from outlabs_auth.routers.session import get_session_router
from outlabs_auth.routers.users import get_users_router

__all__ = [
    "get_auth_router",
    "get_session_router",
    "get_users_router",
    "get_self_service_users_router",
    "get_api_keys_router",
    "get_api_key_admin_router",
    "get_integration_principals_router",
    "get_entities_router",
    "get_roles_router",
    "get_permissions_router",
    "get_memberships_router",
    "get_config_router",
]
