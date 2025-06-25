from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
from fastapi import HTTPException, status

from ..models.role_model import RoleModel, RoleScope
from ..schemas.role_schema import (
    RoleCreateSchema, 
    RoleUpdateSchema, 
    RoleResponseSchema,
    AvailableRolesResponseSchema
)
from .permission_service import permission_service

class RoleService:
    """
    Service class for role-related operations with scoped role support.
    """

    async def create_role(
        self, 
        role_data: RoleCreateSchema, 
        current_user_id: str,
        current_client_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> RoleModel:
        """
        Create a new role with proper scoping.
        
        Args:
            role_data: Role creation data
            current_user_id: ID of user creating the role
            current_client_id: Client ID of current user
            scope_id: Explicit scope ID (platform_id or client_account_id)
        """
        # Determine scope_id based on role scope
        if role_data.scope == RoleScope.SYSTEM:
            final_scope_id = None
        elif role_data.scope == RoleScope.CLIENT:
            final_scope_id = scope_id or current_client_id
            if not final_scope_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client ID required for client-scoped roles"
                )
        elif role_data.scope == RoleScope.PLATFORM:
            if not scope_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Platform ID required for platform-scoped roles"
                )
            final_scope_id = scope_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope: {role_data.scope}"
            )

        # Check if role name already exists in this scope
        existing_role = await RoleModel.find_one(
            RoleModel.name == role_data.name,
            RoleModel.scope == role_data.scope,
            RoleModel.scope_id == final_scope_id
        )
        
        if existing_role:
            scope_desc = f"{role_data.scope} scope"
            if final_scope_id:
                scope_desc += f" ({final_scope_id})"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{role_data.name}' already exists in {scope_desc}"
            )

        # Convert permission names to Link objects
        permission_links = await permission_service.convert_permission_names_to_links(role_data.permissions)

        # Create role
        role = RoleModel(
            name=role_data.name,
            display_name=role_data.display_name,
            description=role_data.description,
            permissions=permission_links,
            scope=role_data.scope,
            scope_id=final_scope_id,
            is_assignable_by_main_client=role_data.is_assignable_by_main_client,
            created_by_user_id=current_user_id,
            created_by_client_id=current_client_id
        )
        
        await role.insert()
        return role

    async def get_role_by_id(self, role_id: PydanticObjectId) -> Optional[RoleModel]:
        """Get a role by its MongoDB ObjectId."""
        return await RoleModel.get(role_id)

    async def get_roles_by_scope(
        self, 
        scope: RoleScope, 
        scope_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[RoleModel]:
        """Get all roles for a specific scope."""
        if scope == RoleScope.SYSTEM:
            # For system roles, just query by scope since scope_id should be None
            roles = await RoleModel.find(
                RoleModel.scope == scope
            ).skip(skip).limit(limit).to_list()
        else:
            # For platform/client roles, filter by scope_id if provided
            if scope_id is not None:
                roles = await RoleModel.find(
                    RoleModel.scope == scope,
                    RoleModel.scope_id == scope_id
                ).skip(skip).limit(limit).to_list()
            else:
                roles = await RoleModel.find(
                    RoleModel.scope == scope
                ).skip(skip).limit(limit).to_list()
            
        return roles

    async def role_to_response_schema(self, role: RoleModel) -> RoleResponseSchema:
        """
        Convert a RoleModel to RoleResponseSchema with detailed permission information.
        """
        # Extract permission ObjectIds from Link objects
        permission_ids = []
        if role.permissions:
            for permission_link in role.permissions:
                if hasattr(permission_link, 'id'):
                    permission_ids.append(permission_link.id)
                else:
                    # Fallback if it's still an ObjectId
                    permission_ids.append(permission_link)
        
        # Resolve permission ObjectIds to detailed permission information
        permission_details = await permission_service.resolve_permissions_to_details(permission_ids)
        
        # Convert role to dict and update permissions
        role_dict = role.model_dump(by_alias=True)
        role_dict["permissions"] = permission_details
        
        return RoleResponseSchema.model_validate(role_dict)

    async def get_available_roles_for_user(
        self,
        current_user_client_id: Optional[str] = None,
        current_user_platform_id: Optional[str] = None,
        is_super_admin: bool = False,
        is_platform_admin: bool = False
    ) -> AvailableRolesResponseSchema:
        """
        Get roles that a user can assign to others, grouped by scope.
        """
        available_roles = AvailableRolesResponseSchema()

        # System roles (only super admins can assign these, or assignable ones for client admins)
        if is_super_admin:
            system_roles = await self.get_roles_by_scope(RoleScope.SYSTEM)
            available_roles.system_roles = [
                await self.role_to_response_schema(role) for role in system_roles
            ]
        elif current_user_client_id:
            # Client admins can assign system roles marked as assignable
            assignable_system_roles = await RoleModel.find(
                RoleModel.scope == RoleScope.SYSTEM,
                RoleModel.is_assignable_by_main_client == True
            ).to_list()
            available_roles.system_roles = [
                await self.role_to_response_schema(role) for role in assignable_system_roles
            ]

        # Platform roles (platform admins can assign within their platform)
        if is_super_admin or (is_platform_admin and current_user_platform_id):
            platform_roles = await self.get_roles_by_scope(
                RoleScope.PLATFORM, 
                current_user_platform_id
            )
            available_roles.platform_roles = [
                await self.role_to_response_schema(role) for role in platform_roles
            ]

        # Client roles (client admins can assign within their client)
        if current_user_client_id:
            client_roles = await self.get_roles_by_scope(
                RoleScope.CLIENT,
                current_user_client_id
            )
            available_roles.client_roles = [
                await self.role_to_response_schema(role) for role in client_roles
            ]

        return available_roles

    async def update_role(self, role_id: PydanticObjectId, role_data: RoleUpdateSchema) -> Optional[RoleModel]:
        """Update a role by ID."""
        role = await self.get_role_by_id(role_id)
        if not role:
            return None

        update_data = role_data.model_dump(exclude_unset=True)
        
        # Convert permission names to Link objects if permissions are being updated
        if "permissions" in update_data and update_data["permissions"] is not None:
            permission_links = await permission_service.convert_permission_names_to_links(update_data["permissions"])
            update_data["permissions"] = permission_links
        
        if update_data:
            for field, value in update_data.items():
                setattr(role, field, value)
            await role.save()
            
        return role

    async def delete_role(self, role_id: PydanticObjectId) -> bool:
        """Delete a role by ID."""
        role = await self.get_role_by_id(role_id)
        if not role:
            return False

        await role.delete()
        return True

    async def user_can_manage_role(
        self,
        user_roles: List[RoleModel],  # Now expects RoleModel objects instead of string IDs
        user_client_id: Optional[str],
        target_role: RoleModel
    ) -> bool:
        """
        Check if a user can manage (create/update/delete) a specific role.
        
        Args:
            user_roles: List of RoleModel objects (user's roles as Beanie Links)
            user_client_id: User's client account ID
            target_role: The role being managed
        """
        # Super admins can manage everything
        if any(role.name == "super_admin" and role.scope == RoleScope.SYSTEM for role in user_roles):
            return True

        # System roles - only super admins can manage
        if target_role.scope == RoleScope.SYSTEM:
            return False
        
        # Platform roles - platform admins for that platform can manage
        if target_role.scope == RoleScope.PLATFORM:
            platform_admin_roles = [
                role for role in user_roles 
                if (role.name == "admin" and 
                    role.scope == RoleScope.PLATFORM and 
                    role.scope_id == target_role.scope_id)
            ]
            return len(platform_admin_roles) > 0
            
        # Client roles - client admins for that client can manage
        if target_role.scope == RoleScope.CLIENT:
            if user_client_id != target_role.scope_id:
                return False
            client_admin_roles = [
                role for role in user_roles 
                if (role.name == "admin" and 
                    role.scope == RoleScope.CLIENT and 
                    role.scope_id == target_role.scope_id)
            ]
            return len(client_admin_roles) > 0
        
        return False

    async def user_can_view_role(
        self,
        user_roles: List[RoleModel],  # Now expects RoleModel objects instead of string IDs
        user_client_id: Optional[str],
        target_role: RoleModel
    ) -> bool:
        """
        Check if a user can view a specific role.
        
        Args:
            user_roles: List of RoleModel objects (user's roles as Beanie Links)
            user_client_id: User's client account ID
            target_role: The role being viewed
        """
        # Super admins can view everything
        if any(role.name == "super_admin" and role.scope == RoleScope.SYSTEM for role in user_roles):
            return True
        
        # System roles - everyone can view
        if target_role.scope == RoleScope.SYSTEM:
            return True
        
        # Platform roles - platform users can view their platform roles
        if target_role.scope == RoleScope.PLATFORM:
            user_platform_roles = [
                role for role in user_roles 
                if (role.scope == RoleScope.PLATFORM and 
                    role.scope_id == target_role.scope_id)
            ]
            return len(user_platform_roles) > 0
            
        # Client roles - users in that client can view
        if target_role.scope == RoleScope.CLIENT:
            return user_client_id == target_role.scope_id
        
        return False

# Create service instance
role_service = RoleService() 