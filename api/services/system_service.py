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
from api.models.entity_model import EntityType, EntityClass
from api.services.auth_service import AuthService
from api.services.entity_service import EntityService
from api.services.role_service import RoleService
from api.services.entity_membership_service import EntityMembershipService

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
            EntityModel.entity_type == EntityType.PLATFORM,
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
            slug="root-platform",
            description="The root platform entity for the entire system",
            entity_class=EntityClass.STRUCTURAL,
            entity_type=EntityType.PLATFORM,
            platform_id="root",  # Self-referential for root
            parent_entity=None,  # No parent for root
            status="active",
            metadata={
                "is_root": True,
                "created_during_init": True,
                "display_name": "Root Platform"
            },
            allowed_child_classes=[EntityClass.STRUCTURAL, EntityClass.ACCESS_GROUP],
            allowed_child_types=[EntityType.ORGANIZATION, EntityType.PLATFORM]
        ).save()
        
        logger.info(f"Created root platform entity: {root_entity.id}")
        
        # Step 2: Create system roles
        # System Admin role (highest level)
        system_admin_role = await RoleModel(
            name="system_admin",
            display_name="System Administrator",
            description="Full system administration access",
            permissions=[
                "*:manage_all",  # All permissions
                "system:manage_all",
                "platform:manage_all",
                "entity:manage_all",
                "user:manage_all",
                "role:manage_all",
                "permission:manage_all"
            ],
            entity=root_entity,  # Link to root entity
            assignable_at_types=[EntityType.PLATFORM],  # Only assignable at platform level
            is_system_role=True,
            is_global=True  # Global role
        ).save()
        
        # Platform Admin role
        platform_admin_role = await RoleModel(
            name="platform_admin",
            display_name="Platform Administrator",
            description="Platform-level administration access",
            permissions=[
                "platform:manage_platform",
                "entity:manage_platform",
                "user:manage_platform",
                "role:manage_platform",
                "entity:read_all",
                "user:read_all",
                "role:read_all"
            ],
            entity=root_entity,
            assignable_at_types=[EntityType.PLATFORM],
            is_system_role=True,
            is_global=True
        ).save()
        
        # Organization Admin role
        org_admin_role = await RoleModel(
            name="organization_admin",
            display_name="Organization Administrator",
            description="Organization-level administration access",
            permissions=[
                "entity:manage",
                "user:manage",
                "role:manage",
                "member:manage",
                "entity:read",
                "user:read",
                "role:read"
            ],
            entity=root_entity,
            assignable_at_types=[EntityType.ORGANIZATION],
            is_system_role=True,
            is_global=True
        ).save()
        
        logger.info("Created system roles")
        
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
            assignable_at_types=[EntityType.ORGANIZATION, EntityType.BRANCH, EntityType.TEAM],
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
                "member:manage",
                "user:invite"
            ],
            entity=root_entity,
            assignable_at_types=[EntityType.TEAM],
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
            assignable_at_types=[EntityType.ORGANIZATION, EntityType.BRANCH, EntityType.TEAM],
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


# Global instance
system_service = SystemService()