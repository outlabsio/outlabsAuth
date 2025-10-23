"""
Router factories for OutlabsAuth.

Pre-built FastAPI routers for quick setup (DD-041).
"""

from outlabs_auth.routers.auth import get_auth_router
from outlabs_auth.routers.users import get_users_router
from outlabs_auth.routers.api_keys import get_api_keys_router

__all__ = [
    "get_auth_router",
    "get_users_router",
    "get_api_keys_router",
]
