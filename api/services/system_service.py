"""
System Service
Handles system initialization and status checks
"""
from typing import Dict, Optional
from datetime import datetime, timezone
from beanie import PydanticObjectId
from fastapi import HTTPException, status
import logging

from api.models import UserModel, RoleModel, EntityModel
from api.services.auth_service import AuthService
from api.services.entity_service import EntityService
from api.services.role_service import RoleService
from api.services.entity_membership_service import EntityMembershipService
from api.services.permission_management_service import permission_management_service
from api.models import PermissionModel

logger = logging.getLogger(__name__)


class SystemService:
    """Service for system initialization and status"""
    
    @staticmethod
    async def get_system_status() -> Dict[str, any]:
        """
        Check if the system is initialized
        
        Returns:
            Dictionary with system status information
        """
        # Check if any users exist
        user_count = await UserModel.count()
        
        # Check if system roles exist
        system_admin_role = await RoleModel.find_one(
            RoleModel.name == "system_admin",
            RoleModel.is_system_role == True
        )
        
        # Check if root platform entity exists
        root_entity = await EntityModel.find_one(
            EntityModel.entity_type == "platform",
            EntityModel.parent_entity == None
        )
        
        is_initialized = (
            user_count > 0 and 
            system_admin_role is not None and
            root_entity is not None
        )
        
        return {
            "initialized": is_initialized,
            "user_count": user_count,
            "has_system_admin_role": system_admin_role is not None,
            "has_root_entity": root_entity is not None,
            "version": "1.0.0",  # You can get this from config
            "requires_setup": not is_initialized
        }
    
    @staticmethod
    async def initialize_system(
        email: str,
        password: str,
        first_name: str = "System",
        last_name: str = "Administrator"
    ) -> Dict[str, any]:
        """
        Initialize the system with the first superuser
        
        Args:
            email: Email for the superuser
            password: Password for the superuser
            first_name: First name (default: System)
            last_name: Last name (default: Administrator)
            
        Returns:
            Dictionary with initialization results
            
        Raises:
            HTTPException: If system is already initialized
        """
        # Check if already initialized
        status = await SystemService.get_system_status()
        if status["initialized"]:
            raise HTTPException(
                status_code=400,
                detail="System is already initialized"
            )
        
        logger.info(f"Initializing system with superuser: {email}")
        
        # Step 1: Create root platform entity
        root_entity = await EntityModel(
            name="root_platform",
            display_name="Root Platform",
            slug="root-platform",
            description="The root platform entity for the entire system",
            entity_class="structural",
            entity_type="platform",
            platform_id="root",  # Self-referential for root
            parent_entity=None,  # No parent for root
            status="active",
            metadata={
                "is_root": True,
                "created_during_init": True
            },
            allowed_child_classes=["structural", "access_group"],
            allowed_child_types=[]  # Flexible entity types allowed
        ).save()
        
        logger.info(f"Created root platform entity: {root_entity.id}")
        
        # Step 2: Create system roles
        # System Admin role (highest level)
        system_admin_role = await RoleModel(
            name="system_admin",
            display_name="System Administrator",
            description="Full system administration access",
            permissions=[
                "*",  # All permissions
                "entity:create_all",
                "entity:read_all",
                "entity:update_all",
                "entity:delete_all",
                "user:create_all",
                "user:read_all",
                "user:update_all",
                "user:delete_all",
                "user:invite_all",
                "role:create_all",
                "role:read_all",
                "role:update_all",
                "role:delete_all",
                "role:delete_all"
            ],
            entity=root_entity,  # Link to root entity
            assignable_at_types=[],  # Can be assigned at any entity
            is_system_role=True,
            is_global=True  # Global role
        ).save()
        
        # Platform Admin role
        platform_admin_role = await RoleModel(
            name="platform_admin",
            display_name="Platform Administrator",
            description="Platform-level administration access",
            permissions=[
                "entity:read_all",
                "user:read_all",
                "role:read_all"
            ],
            entity=root_entity,
            assignable_at_types=[],
            is_system_role=True,
            is_global=True
        ).save()
        
        # Organization Admin role - with hierarchical permissions
        org_admin_role = await RoleModel(
            name="organization_admin",
            display_name="Organization Administrator",
            description="Organization-level administration access with hierarchical control",
            permissions=[
                "entity:create",          # Create direct children
                "entity:read_tree",       # Read org and all descendants
                "entity:update",          # Update org itself
                "entity:update_tree",     # Update all descendants
                "entity:delete_tree",     # Delete org and descendants
                "user:create_tree",       # Create users in entire tree
                "user:read_tree",         # Read users in entire tree
                "user:update_tree",       # Update users in entire tree
                "user:delete_tree",       # Delete users in entire tree
                "user:invite_tree",       # Invite users in entire tree
                "role:create",            # Create roles at org level
                "role:read",              # Read roles at org level
                "role:update",            # Update roles at org level
                "role:delete",            # Delete roles at org level
                "role:update",            # Update roles at org level
                "role:read_tree",         # Read roles in tree
                "member:create_tree",     # Create members in tree
                "member:read_tree",       # Read members in tree
                "member:update_tree",     # Update members in tree
                "member:delete_tree",     # Delete members in tree
                "user:read_tree",         # Read all users in tree
            ],
            entity=root_entity,
            assignable_at_types=[],
            is_system_role=True,
            is_global=True
        ).save()
        
        logger.info("Created system roles")
        
        # Step 2.5: Create common custom permissions
        await SystemService._create_custom_permissions(root_entity)
        logger.info("Created custom permissions")
        
        # Step 3: Create the superuser
        # Hash the password first
        auth_service = AuthService()
        hashed_password = auth_service.hash_password(password)
        
        user = UserModel(
            email=email.lower(),
            hashed_password=hashed_password,  # Include hashed password in creation
            is_active=True,
            is_verified=True,  # Auto-verify the first user
            is_system_user=True,  # Mark as system user
            profile={
                "first_name": first_name,
                "last_name": last_name,
                "display_name": f"{first_name} {last_name}",
                "title": "System Administrator",
                "bio": "Primary system administrator"
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Save the user
        await user.save()
        logger.info(f"Created superuser: {user.email}")
        
        # Step 4: Add user to root platform with system_admin role
        from api.schemas.entity_schema import EntityMemberAdd
        
        membership_service = EntityMembershipService()
        member_data = EntityMemberAdd(
            user_id=str(user.id),
            role_id=str(system_admin_role.id)
        )
        membership = await membership_service.add_member(
            entity_id=str(root_entity.id),
            member_data=member_data,
            added_by=user
        )
        
        logger.info(f"Added superuser to root platform with system_admin role")
        
        # Step 5: Create default roles for common entity types
        # Team member role
        await RoleModel(
            name="member",
            display_name="Member",
            description="Basic member access",
            permissions=[
                "entity:read",
                "user:read",
                "member:read"
            ],
            entity=root_entity,
            assignable_at_types=[],
            is_system_role=True,
            is_global=True
        ).save()
        
        # Team lead role
        await RoleModel(
            name="team_lead",
            display_name="Team Lead",
            description="Team leadership access",
            permissions=[
                "entity:read",
                "user:read",
                "member:create",
                "member:read",
                "member:update",
                "member:delete",
                "user:invite"
            ],
            entity=root_entity,
            assignable_at_types=[],
            is_system_role=True,
            is_global=True
        ).save()
        
        # Viewer role
        await RoleModel(
            name="viewer",
            display_name="Viewer",
            description="Read-only access",
            permissions=[
                "entity:read",
                "user:read"
            ],
            entity=root_entity,
            assignable_at_types=[],
            is_system_role=True,
            is_global=True
        ).save()
        
        logger.info("System initialization complete")
        
        return {
            "initialized": True,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.profile.first_name,
                "last_name": user.profile.last_name
            },
            "root_entity": {
                "id": str(root_entity.id),
                "name": root_entity.name,
                "slug": root_entity.slug
            },
            "message": "System initialized successfully"
        }
    
    @staticmethod
    async def reset_system(confirmation: str) -> Dict[str, any]:
        """
        Reset the entire system (DANGEROUS - for development only)
        
        Args:
            confirmation: Must be "RESET_ENTIRE_SYSTEM" to proceed
            
        Returns:
            Dictionary with reset status
            
        Raises:
            HTTPException: If confirmation is incorrect
        """
        if confirmation != "RESET_ENTIRE_SYSTEM":
            raise HTTPException(
                status_code=400,
                detail="Invalid confirmation. This is a dangerous operation."
            )
        
        # Only allow in development
        import os
        if os.getenv("ENVIRONMENT", "development") != "development":
            raise HTTPException(
                status_code=403,
                detail="System reset is only allowed in development environment"
            )
        
        # Delete all data
        deleted_counts = {
            "users": await UserModel.delete_all(),
            "roles": await RoleModel.delete_all(),
            "entities": await EntityModel.delete_all(),
        }
        
        logger.warning(f"System reset complete. Deleted: {deleted_counts}")
        
        return {
            "reset": True,
            "deleted": deleted_counts,
            "message": "System has been reset. Please reinitialize."
        }
    
    @staticmethod
    async def _create_custom_permissions(root_entity: EntityModel):
        """
        Create common custom permissions during system initialization
        
        Args:
            root_entity: The root platform entity
        """
        # Define common custom permissions that extend beyond system permissions
        custom_permissions = [
            # Organization-level permissions
            {
                "name": "organization:create",
                "display_name": "Create Organizations",
                "description": "Create new organizations",
                "resource": "organization",
                "action": "create",
                "tags": ["platform", "organization"]
            },
            {
                "name": "organization:read",
                "display_name": "View Organizations",
                "description": "View organization details",
                "resource": "organization",
                "action": "read",
                "tags": ["organization"]
            },
            {
                "name": "organization:update",
                "display_name": "Update Organizations",
                "description": "Update organization settings",
                "resource": "organization",
                "action": "update",
                "tags": ["organization"]
            },
            {
                "name": "organization:delete",
                "display_name": "Delete Organizations",
                "description": "Remove organizations",
                "resource": "organization",
                "action": "delete",
                "tags": ["platform", "organization"]
            },
            
            # Hierarchical organization permissions
            {
                "name": "organization:read_tree",
                "display_name": "View Organization Tree",
                "description": "View organization and all sub-entities",
                "resource": "organization",
                "action": "read_tree",
                "tags": ["organization", "hierarchical"]
            },
            {
                "name": "organization:update_tree",
                "display_name": "Update Organization Tree",
                "description": "Update organization and all sub-entities",
                "resource": "organization",
                "action": "update_tree",
                "tags": ["organization", "hierarchical"]
            },
            {
                "name": "organization:delete_tree",
                "display_name": "Delete Organization Tree",
                "description": "Delete organization and all sub-entities",
                "resource": "organization",
                "action": "delete_tree",
                "tags": ["platform", "organization", "hierarchical"]
            },
            
            # Team/Branch permissions
            {
                "name": "team:create",
                "display_name": "Create Teams",
                "description": "Create new teams or branches",
                "resource": "team",
                "action": "create",
                "tags": ["team", "branch"]
            },
            {
                "name": "team:update",
                "display_name": "Update Teams",
                "description": "Update team settings",
                "resource": "team",
                "action": "update",
                "tags": ["team", "branch"]
            },
            {
                "name": "team:delete",
                "display_name": "Delete Teams",
                "description": "Delete teams",
                "resource": "team",
                "action": "delete",
                "tags": ["team", "branch"]
            },
            {
                "name": "team:read",
                "display_name": "View Teams",
                "description": "View team information",
                "resource": "team",
                "action": "read",
                "tags": ["team", "branch"]
            },
            
            # Hierarchical team permissions
            {
                "name": "team:read_tree",
                "display_name": "View Team Tree",
                "description": "View team and all sub-teams",
                "resource": "team",
                "action": "read_tree",
                "tags": ["team", "hierarchical"]
            },
            {
                "name": "team:update_tree",
                "display_name": "Update Team Tree",
                "description": "Update team and all sub-teams",
                "resource": "team",
                "action": "update_tree",
                "tags": ["team", "hierarchical"]
            },
            {
                "name": "team:delete_tree",
                "display_name": "Delete Team Tree",
                "description": "Delete team and all sub-teams",
                "resource": "team",
                "action": "delete_tree",
                "tags": ["team", "hierarchical"]
            },
            
            # Project/Resource permissions (for future use)
            {
                "name": "project:create",
                "display_name": "Create Projects",
                "description": "Create new projects",
                "resource": "project",
                "action": "create",
                "tags": ["project"]
            },
            {
                "name": "project:update",
                "display_name": "Update Projects",
                "description": "Update project settings",
                "resource": "project",
                "action": "update",
                "tags": ["project"]
            },
            {
                "name": "project:delete",
                "display_name": "Delete Projects",
                "description": "Delete projects",
                "resource": "project",
                "action": "delete",
                "tags": ["project"]
            },
            {
                "name": "project:read",
                "display_name": "View Projects",
                "description": "View project details",
                "resource": "project",
                "action": "read",
                "tags": ["project"]
            },
            
            # Analytics/Reporting permissions
            {
                "name": "analytics:view",
                "display_name": "View Analytics",
                "description": "Access analytics and reports",
                "resource": "analytics",
                "action": "view",
                "tags": ["analytics", "reporting"]
            },
            {
                "name": "analytics:export",
                "display_name": "Export Analytics",
                "description": "Export analytics data",
                "resource": "analytics",
                "action": "export",
                "tags": ["analytics", "reporting"]
            },
            
            # Audit/Compliance permissions
            {
                "name": "audit:view",
                "display_name": "View Audit Logs",
                "description": "Access audit logs and compliance data",
                "resource": "audit",
                "action": "view",
                "tags": ["audit", "compliance"]
            },
            {
                "name": "audit:export",
                "display_name": "Export Audit Data",
                "description": "Export audit logs",
                "resource": "audit",
                "action": "export",
                "tags": ["audit", "compliance"]
            },
            
            # API/Integration permissions
            {
                "name": "api:create",
                "display_name": "Create API Keys",
                "description": "Create new API keys",
                "resource": "api",
                "action": "create",
                "tags": ["api"]
            },
            
            # Settings/Configuration permissions
            {
                "name": "settings:update",
                "display_name": "Update Settings",
                "description": "Update entity settings and configuration",
                "resource": "settings",
                "action": "update",
                "tags": ["settings", "configuration"]
            },
            {
                "name": "settings:view",
                "display_name": "View Settings",
                "description": "View entity settings",
                "resource": "settings",
                "action": "view",
                "tags": ["settings"]
            }
        ]
        
        # Create each custom permission
        for perm_data in custom_permissions:
            try:
                permission = PermissionModel(
                    name=perm_data["name"],
                    display_name=perm_data["display_name"],
                    description=perm_data["description"],
                    resource=perm_data["resource"],
                    action=perm_data["action"],
                    entity_id=None,  # Global permissions
                    created_by=None,  # System-created
                    tags=perm_data.get("tags", []),
                    is_system=False,  # Custom permissions, not system
                    is_active=True,
                    metadata={
                        "created_during_init": True,
                        "is_common": True
                    }
                )
                await permission.save()
                logger.debug(f"Created custom permission: {permission.name}")
            except Exception as e:
                logger.warning(f"Failed to create permission {perm_data['name']}: {str(e)}")


# Global instance
system_service = SystemService()