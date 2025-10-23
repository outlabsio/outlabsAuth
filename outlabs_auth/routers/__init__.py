"""
Router factories for OutlabsAuth.

Pre-built FastAPI routers for quick setup (DD-041).
"""

from outlabs_auth.routers.auth import get_auth_router
from outlabs_auth.routers.users import get_users_router
from outlabs_auth.routers.api_keys import get_api_keys_router
from outlabs_auth.routers.entities import get_entities_router
from outlabs_auth.routers.roles import get_roles_router
from outlabs_auth.routers.permissions import get_permissions_router
from outlabs_auth.routers.memberships import get_memberships_router

__all__ = [
    "get_auth_router",
    "get_users_router",
    "get_api_keys_router",
    "get_entities_router",
    "get_roles_router",
    "get_permissions_router",
    "get_memberships_router",
]
