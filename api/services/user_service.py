"""
User Service
Handles user management operations including profile management, search, invitations, and status updates
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from beanie import PydanticObjectId
from beanie.operators import In, And, Or
from fastapi import HTTPException, status
import secrets
import string

from api.models import UserModel, EntityModel, EntityMembershipModel, RoleModel
from api.models.user_model import UserProfile
from api.services.auth_service import AuthService
from api.services.entity_service import EntityService
from api.services.permission_service import permission_service
from api.services.email_service import email_service
from api.config import settings


class UserService:
    """Service for user management operations"""
    
    @staticmethod
    async def get_user(user_id: str) -> UserModel:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User model
            
        Raises:
            HTTPException: If user not found
        """
        user = await UserModel.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    
    @staticmethod
    async def update_user_profile(
        user_id: str,
        profile_data: Dict[str, Any],
        current_user: UserModel
    ) -> UserModel:
        """
        Update user profile information
        
        Args:
            user_id: User ID to update
            profile_data: Profile data to update
            current_user: User performing the update
            
        Returns:
            Updated user model
            
        Raises:
            HTTPException: If user not found or unauthorized
        """
        user = await UserService.get_user(user_id)
        
        # Check if user can update profile (self or admin)
        if current_user.id != user.id:
            # Check if current user has permission to manage users
            has_permission, _ = await permission_service.check_permission(
                str(current_user.id),
                "user:manage"
            )
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update user profile"
                )
        
        # Update profile fields
        if not user.profile:
            user.profile = UserProfile()
            
        for field, value in profile_data.items():
            if hasattr(user.profile, field):
                setattr(user.profile, field, value)
        
        user.updated_at = datetime.now(timezone.utc)
        await user.save()
        
        return user
    
    @staticmethod
    async def search_users(
        query: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        current_user: UserModel = None
    ) -> Tuple[List[UserModel], int]:
        """
        Search users with filtering and pagination
        
        Args:
            query: Search query (email, name)
            entity_id: Filter by entity membership
            status: Filter by user status
            page: Page number
            page_size: Items per page
            current_user: User performing the search
            
        Returns:
            Tuple of (users list, total count)
        """
        # Build query conditions
        conditions = []
        
        # Text search
        if query:
            conditions.append(
                Or(
                    UserModel.email.contains(query, case_insensitive=True),
                    UserModel.profile.first_name.contains(query, case_insensitive=True),
                    UserModel.profile.last_name.contains(query, case_insensitive=True)
                )
            )
        
        # Status filter
        if status:
            if status == "active":
                conditions.append(UserModel.is_active == True)
            elif status == "inactive":
                conditions.append(UserModel.is_active == False)
            elif status == "locked":
                conditions.append(UserModel.locked_until.ne(None))
        
        # Entity membership filter
        if entity_id:
            # Get the entity and its parent hierarchy
            entity = await EntityModel.get(entity_id, fetch_links=True)
            if not entity:
                return [], 0
            
            # Collect entity IDs from the hierarchy (including self and all parents)
            entity_ids = [PydanticObjectId(entity_id)]
            current_entity = entity
            
            # Traverse up the hierarchy to get all parent entities
            while current_entity.parent_entity:
                # Fetch the parent entity link if not already fetched
                if hasattr(current_entity.parent_entity, 'id'):
                    parent_id = current_entity.parent_entity.id
                else:
                    parent_ref = await current_entity.parent_entity.fetch()
                    if not parent_ref:
                        break
                    parent_id = parent_ref.id
                
                parent = await EntityModel.get(parent_id, fetch_links=True)
                if parent:
                    entity_ids.append(parent.id)
                    current_entity = parent
                else:
                    break
            
            # Get users who are members of any entity in the hierarchy
            memberships = await EntityMembershipModel.find(
                In(EntityMembershipModel.entity.id, entity_ids),
                EntityMembershipModel.status == "active",
                fetch_links=True
            ).to_list()
            
            if memberships:
                user_ids = list(set([m.user.id for m in memberships]))  # Remove duplicates
                conditions.append(In(UserModel.id, user_ids))
            else:
                # No members in entire hierarchy, return empty result
                return [], 0
        
        # Build final query
        if conditions:
            query_filter = And(*conditions)
        else:
            query_filter = {}
        
        # Execute query with pagination
        total = await UserModel.find(query_filter).count()
        
        skip = (page - 1) * page_size
        users = await UserModel.find(query_filter) \
            .skip(skip) \
            .limit(page_size) \
            .sort("+profile.first_name", "+profile.last_name", "+email") \
            .to_list()
        
        return users, total
    
    @staticmethod
    async def update_user_status(
        user_id: str,
        status: str,
        current_user: UserModel
    ) -> UserModel:
        """
        Update user account status
        
        Args:
            user_id: User ID to update
            status: New status (active/inactive/locked)
            current_user: User performing the update
            
        Returns:
            Updated user model
            
        Raises:
            HTTPException: If user not found or unauthorized
        """
        user = await UserService.get_user(user_id)
        
        # Check permission
        has_permission, _ = await permission_service.check_permission(
            str(current_user.id),
            "user:manage"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update user status"
            )
        
        # Prevent self-deactivation
        if user.id == current_user.id and status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
        
        # Update status
        if status == "active":
            user.is_active = True
            user.locked_until = None
        elif status == "inactive":
            user.is_active = False
            user.locked_until = None
        elif status == "locked":
            user.is_active = False
            user.locked_until = datetime.now(timezone.utc).replace(year=2099)  # Lock indefinitely
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Must be 'active', 'inactive', or 'locked'"
            )
        
        user.updated_at = datetime.now(timezone.utc)
        await user.save()
        
        return user
    
    @staticmethod
    async def delete_user(
        user_id: str,
        current_user: UserModel,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete or deactivate a user account
        
        Args:
            user_id: User ID to delete
            current_user: User performing the deletion
            hard_delete: Whether to permanently delete the user
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If user not found or unauthorized
        """
        user = await UserService.get_user(user_id)
        
        # Check permission
        has_permission, _ = await permission_service.check_permission(
            str(current_user.id),
            "user:manage"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete user"
            )
        
        # Prevent self-deletion
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        if hard_delete:
            # Check if user has any critical memberships
            memberships = await EntityMembershipModel.find(
                EntityMembershipModel.user.id == user.id,
                EntityMembershipModel.status == "active"
            ).to_list()
            
            for membership in memberships:
                entity = await membership.entity.fetch()
                role = await membership.roles[0].fetch() if membership.roles else None
                
                # Check if user is the last admin of any entity
                if role and "admin" in role.name.lower():
                    admin_roles = await RoleModel.find(
                        RoleModel.entity.id == entity.id,
                        RoleModel.name.contains("admin")
                    ).to_list()
                    
                    if admin_roles:
                        admin_role_ids = [r.id for r in admin_roles]
                        admin_memberships = await EntityMembershipModel.find(
                            EntityMembershipModel.entity.id == entity.id,
                            EntityMembershipModel.status == "active",
                            In(EntityMembershipModel.roles.id, admin_role_ids)
                        ).to_list()
                        
                        if len(admin_memberships) <= 1:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot delete user: last admin of entity '{entity.name}'"
                            )
            
            # Remove all memberships first
            await EntityMembershipModel.find(
                EntityMembershipModel.user.id == user.id
            ).delete()
            
            # Delete user
            await user.delete()
        else:
            # Soft delete - just deactivate
            user.is_active = False
            user.updated_at = datetime.now(timezone.utc)
            await user.save()
        
        return True
    
    @staticmethod
    async def invite_user(
        email: str,
        entity_id: str,
        role_id: str,
        invited_by: UserModel,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        send_email: bool = True
    ) -> UserModel:
        """
        Invite a new user to an entity
        
        Args:
            email: Email address of the user to invite
            entity_id: Entity to invite user to
            role_id: Role to assign to the user
            invited_by: User performing the invitation
            first_name: Optional first name
            last_name: Optional last name
            send_email: Whether to send invitation email
            
        Returns:
            Created user model
            
        Raises:
            HTTPException: If entity/role not found or unauthorized
        """
        # Check if inviter has permission to manage members
        has_permission, _ = await permission_service.check_permission(
            str(invited_by.id),
            "member:manage",
            entity_id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to invite users to this entity"
            )
        
        # Check if user already exists
        existing_user = await UserModel.find_one(UserModel.email == email)
        if existing_user:
            # Check if already a member
            existing_membership = await EntityMembershipModel.find_one(
                EntityMembershipModel.user.id == existing_user.id,
                EntityMembershipModel.entity.id == PydanticObjectId(entity_id),
                EntityMembershipModel.status == "active"
            )
            if existing_membership:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User is already a member of this entity"
                )
            
            # Add existing user to entity
            entity = await EntityModel.get(entity_id)
            role = await RoleModel.get(role_id)
            
            membership = EntityMembershipModel(
                user=existing_user,
                entity=entity,
                roles=[role],
                status="active",
                joined_by=invited_by,
                created_at=datetime.now(timezone.utc)
            )
            await membership.save()
            
            return existing_user
        
        # Create new user with temporary password
        temp_password = UserService._generate_temporary_password()
        hashed_password = AuthService.hash_password(temp_password)
        
        user = UserModel(
            email=email,
            hashed_password=hashed_password,
            profile=UserProfile(
                first_name=first_name or "",
                last_name=last_name or ""
            ),
            is_active=True,
            email_verified=False,  # Will be verified on first login
            metadata={"invited_by": str(invited_by.id), "temp_password": True},
            created_at=datetime.now(timezone.utc)
        )
        
        await user.save()
        
        # Add user to entity
        entity = await EntityModel.get(entity_id)
        role = await RoleModel.get(role_id)
        
        membership = EntityMembershipModel(
            user=user,
            entity=entity,
            roles=[role],
            status="active",
            joined_by=invited_by,
            created_at=datetime.now(timezone.utc)
        )
        await membership.save()
        
        # TODO: Send invitation email with temporary password
        if send_email:
            await UserService._send_invitation_email(user, temp_password, entity, invited_by)
        
        return user
    
    @staticmethod
    async def reset_user_password(
        user_id: str,
        current_user: UserModel,
        send_email: bool = True
    ) -> str:
        """
        Reset a user's password (admin function)
        
        Args:
            user_id: User ID to reset password for
            current_user: User performing the reset
            send_email: Whether to send the new password via email
            
        Returns:
            New temporary password
            
        Raises:
            HTTPException: If user not found or unauthorized
        """
        user = await UserService.get_user(user_id)
        
        # Check permission
        has_permission, _ = await permission_service.check_permission(
            str(current_user.id),
            "user:manage"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to reset user password"
            )
        
        # Generate new temporary password
        temp_password = UserService._generate_temporary_password()
        hashed_password = AuthService.hash_password(temp_password)
        
        # Update user
        user.hashed_password = hashed_password
        user.last_password_change = datetime.now(timezone.utc)
        user.metadata = user.metadata or {}
        user.metadata["temp_password"] = True
        user.updated_at = datetime.now(timezone.utc)
        
        await user.save()
        
        # TODO: Send password reset email
        if send_email:
            await UserService._send_password_reset_email(user, temp_password, current_user)
        
        return temp_password
    
    @staticmethod
    async def get_user_memberships(
        user_id: str,
        current_user: UserModel,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get user's entity memberships
        
        Args:
            user_id: User ID
            current_user: User requesting the memberships
            include_inactive: Whether to include inactive memberships
            
        Returns:
            List of membership data
            
        Raises:
            HTTPException: If user not found or unauthorized
        """
        user = await UserService.get_user(user_id)
        
        # Check if user can view memberships (self or admin)
        if current_user.id != user.id:
            has_permission, _ = await permission_service.check_permission(
                str(current_user.id),
                "user:read"
            )
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view user memberships"
                )
        
        # Build query
        query_conditions = [EntityMembershipModel.user.id == user.id]
        if not include_inactive:
            query_conditions.append(EntityMembershipModel.status == "active")
        
        memberships = await EntityMembershipModel.find(
            And(*query_conditions)
        ).to_list()
        
        # Format response
        result = []
        for membership in memberships:
            entity = await membership.entity.fetch()
            roles = []
            for role_link in membership.roles:
                role = await role_link.fetch()
                roles.append({
                    "id": str(role.id),
                    "name": role.name,
                    "display_name": role.display_name,
                    "permissions": role.permissions
                })
            
            result.append({
                "id": str(membership.id),
                "entity": {
                    "id": str(entity.id),
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "entity_class": entity.entity_class
                },
                "roles": roles,
                "status": membership.status,
                "joined_at": membership.joined_at,
                "valid_from": membership.valid_from,
                "valid_until": membership.valid_until
            })
        
        return result
    
    @staticmethod
    async def enrich_user_with_entities(user: UserModel) -> Dict[str, Any]:
        """
        Enrich user data with entity memberships
        
        Args:
            user: User model
            
        Returns:
            User data with entities
        """
        # Get active memberships
        memberships = await EntityMembershipModel.find(
            And(
                EntityMembershipModel.user.id == user.id,
                EntityMembershipModel.status == "active"
            )
        ).to_list()
        
        # Format entities
        entities = []
        for membership in memberships:
            entity = await membership.entity.fetch()
            roles = []
            for role_link in membership.roles:
                role = await role_link.fetch()
                roles.append({
                    "id": str(role.id),
                    "name": role.name,
                    "display_name": role.display_name,
                    "permissions": role.permissions
                })
            
            # Handle parent entity Link object
            parent_id = None
            if entity.parent_entity:
                if hasattr(entity.parent_entity, 'id'):
                    parent_id = str(entity.parent_entity.id)
                elif hasattr(entity.parent_entity, 'ref'):
                    parent_id = str(entity.parent_entity.ref.id)
            
            entities.append({
                "id": str(entity.id),
                "name": entity.name,
                "slug": entity.slug,
                "entity_type": entity.entity_type,
                "entity_class": entity.entity_class,
                "parent_id": parent_id,
                "roles": roles,
                "status": membership.status,
                "joined_at": membership.joined_at
            })
        
        return {
            "id": str(user.id),
            "email": user.email,
            "profile": {
                "first_name": user.profile.first_name,
                "last_name": user.profile.last_name,
                "phone": user.profile.phone,
                "avatar_url": user.profile.avatar_url,
                "preferences": user.profile.preferences,
                "full_name": user.profile.full_name
            },
            "is_active": user.is_active,
            "is_system_user": user.is_system_user,
            "email_verified": user.email_verified,
            "last_login": user.last_login,
            "last_password_change": user.last_password_change,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "entities": entities
        }
    
    @staticmethod
    async def create_user_with_entities(
        email: str,
        password: Optional[str],
        profile_data: Dict[str, Any],
        entity_assignments: List[Dict[str, Any]],
        is_active: bool = True,
        send_welcome_email: bool = True,
        current_user: UserModel = None
    ) -> Tuple[UserModel, Optional[str]]:
        """
        Create a new user with entity assignments
        
        Args:
            email: User email
            password: User password (optional, will generate if not provided)
            profile_data: Profile information
            entity_assignments: List of entity/role assignments
            is_active: Whether user is active
            send_welcome_email: Whether to send welcome email
            current_user: User creating the new user
            
        Returns:
            Tuple of (created user, temporary password if generated)
        """
        # Check if user already exists
        existing_user = await UserModel.find_one(UserModel.email == email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Generate password if not provided
        temp_password = None
        if not password:
            temp_password = UserService._generate_temporary_password()
            password = temp_password
        
        # Create user
        hashed_password = AuthService.hash_password(password)
        user = UserModel(
            email=email,
            hashed_password=hashed_password,
            profile=UserProfile(**profile_data),
            is_active=is_active,
            created_at=datetime.now(timezone.utc)
        )
        await user.save()
        
        # Assign to entities
        for assignment in entity_assignments:
            entity = await EntityModel.get(assignment["entity_id"])
            if not entity:
                continue
                
            # Create membership
            membership = EntityMembershipModel(
                user=user,
                entity=entity,
                status=assignment.get("status", "active"),
                valid_from=assignment.get("valid_from"),
                valid_until=assignment.get("valid_until"),
                joined_by=current_user if current_user else None
            )
            
            # Assign roles
            for role_id in assignment.get("role_ids", []):
                role = await RoleModel.get(role_id, fetch_links=True)
                if role and role.entity and str(role.entity.id) == str(entity.id):
                    membership.roles.append(role)
            
            await membership.save()
        
        # Send welcome email if requested
        if send_welcome_email and temp_password:
            await UserService._send_invitation_email(user, entity.name, temp_password)
        
        return user, temp_password
    
    @staticmethod
    async def update_user_entities(
        user_id: str,
        entity_assignments: List[Dict[str, Any]],
        current_user: UserModel
    ) -> UserModel:
        """
        Update user's entity assignments
        
        Args:
            user_id: User ID to update
            entity_assignments: New entity/role assignments
            current_user: User performing the update
            
        Returns:
            Updated user
        """
        user = await UserService.get_user(user_id)
        
        # Check permission
        has_permission, _ = await permission_service.check_permission(
            str(current_user.id),
            "user:manage"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update user entities"
            )
        
        # Remove existing memberships
        await EntityMembershipModel.find(
            EntityMembershipModel.user.id == user.id
        ).delete()
        
        # Add new assignments
        for assignment in entity_assignments:
            entity = await EntityModel.get(assignment["entity_id"])
            if not entity:
                continue
                
            membership = EntityMembershipModel(
                user=user,
                entity=entity,
                status=assignment.get("status", "active"),
                valid_from=assignment.get("valid_from"),
                valid_until=assignment.get("valid_until"),
                joined_by=current_user
            )
            
            # Assign roles
            for role_id in assignment.get("role_ids", []):
                role = await RoleModel.get(role_id, fetch_links=True)
                if role:
                    # Check if role can be assigned:
                    # 1. Global role (no entity)
                    # 2. Role belongs to this entity
                    # 3. Role is assignable at this entity type
                    can_assign = False
                    if role.is_global or not role.entity:
                        can_assign = True
                    elif role.entity and str(role.entity.id) == str(entity.id):
                        can_assign = True
                    elif role.assignable_at_types and entity.entity_type in role.assignable_at_types:
                        can_assign = True
                    
                    if can_assign:
                        membership.roles.append(role)
            
            await membership.save()
        
        return user
    
    @staticmethod
    def _generate_temporary_password(length: int = 12) -> str:
        """Generate a secure temporary password"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    @staticmethod
    async def _send_invitation_email(
        user: UserModel,
        temp_password: str,
        entity: EntityModel,
        invited_by: UserModel
    ):
        """Send invitation email to new user"""
        await email_service.send_invitation_email(
            user=user,
            temp_password=temp_password,
            entity=entity,
            invited_by=invited_by
        )
    
    @staticmethod
    async def _send_password_reset_email(
        user: UserModel,
        temp_password: str,
        reset_by: UserModel
    ):
        """Send password reset email"""
        await email_service.send_admin_password_reset_email(
            user=user,
            temp_password=temp_password,
            reset_by=reset_by
        )