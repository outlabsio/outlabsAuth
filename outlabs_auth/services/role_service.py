"""
Role service with lifecycle hooks.

Implements lifecycle hooks pattern from FastAPI-Users (DD-040).
"""

from typing import Any, Optional, List
from fastapi import Request
from outlabs_auth.services.base import BaseService


class RoleService(BaseService):
    """
    Role management service with lifecycle hooks.

    Available Hooks:
        - on_after_role_created: After role creation
        - on_after_role_updated: After role update
        - on_before_role_deleted: Before role deletion
        - on_after_role_deleted: After role deletion
        - on_after_role_assigned: After role assigned to user
        - on_after_role_removed: After role removed from user
        - on_after_permission_changed: After role's permissions changed
    """

    def __init__(self, database: Any):
        self.database = database

    # ===================================================================
    # LIFECYCLE HOOKS
    # ===================================================================

    async def on_after_role_created(
        self,
        role: Any,
        request: Optional[Request] = None
    ) -> None:
        """Called after role creation."""
        pass

    async def on_after_role_updated(
        self,
        role: Any,
        update_dict: dict,
        request: Optional[Request] = None
    ) -> None:
        """Called after role update."""
        pass

    async def on_before_role_deleted(
        self,
        role: Any,
        request: Optional[Request] = None
    ) -> None:
        """Called before role deletion. Raise exception to prevent."""
        pass

    async def on_after_role_deleted(
        self,
        role: Any,
        request: Optional[Request] = None
    ) -> None:
        """Called after role deletion."""
        pass

    async def on_after_role_assigned(
        self,
        user: Any,
        role: Any,
        entity_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after role assigned to user.

        Override to:
        - Send notification to user
        - Log permission change
        - Invalidate permission cache
        - Trigger webhook

        Args:
            user: User who received the role
            role: Role that was assigned
            entity_id: Entity context (EnterpriseRBAC only)
            request: Optional request object
        """
        pass

    async def on_after_role_removed(
        self,
        user: Any,
        role: Any,
        entity_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> None:
        """
        Called after role removed from user.

        Override to:
        - Send notification to user
        - Log permission revocation
        - Invalidate permission cache
        - Trigger webhook

        Args:
            user: User who lost the role
            role: Role that was removed
            entity_id: Entity context (EnterpriseRBAC only)
            request: Optional request object
        """
        pass

    async def on_after_permission_changed(
        self,
        role: Any,
        old_permissions: List[str],
        new_permissions: List[str],
        request: Optional[Request] = None
    ) -> None:
        """
        Called after role's permissions changed.

        Override to:
        - Invalidate cache for all users with this role
        - Log audit trail
        - Notify affected users

        Args:
            role: Role whose permissions changed
            old_permissions: Previous permissions
            new_permissions: New permissions
            request: Optional request object
        """
        pass
