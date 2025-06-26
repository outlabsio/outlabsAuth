from beanie import PydanticObjectId
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Tuple, Optional, List, Dict, Any

from .services.security_service import security_service
from .services.user_service import user_service
from .services.role_service import role_service
from .services.group_service import group_service
from .services.client_account_service import client_account_service
from .models.user_model import UserModel
from .schemas.auth_schema import TokenDataSchema

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


# --- Response Utilities ---

def convert_user_to_response(user: UserModel) -> Dict[str, Any]:
    """
    Convert a UserModel to response format with proper role/group ID conversion.
    This utility ensures consistent user response format across all endpoints.
    
    Args:
        user: UserModel instance with populated roles and groups
        
    Returns:
        Dict containing user data with roles and groups as ID strings
    """
    user_dict = user.model_dump(by_alias=True)
    user_dict["_id"] = str(user_dict["_id"])
    
    # Convert role objects to role ID strings
    user_dict["roles"] = [str(role.id) for role in user.roles] if user.roles else []
    
    # Convert group objects to group ID strings (if groups field exists)
    user_dict["groups"] = [str(group.id) for group in user.groups] if hasattr(user, 'groups') and user.groups else []
    
    # Handle client_account conversion
    if user.client_account:
        user_dict["client_account_id"] = str(user.client_account.id)
    else:
        user_dict["client_account_id"] = None
    # Remove the client_account object from response
    user_dict.pop("client_account", None)
    
    return user_dict


# --- User Role Utilities ---

def user_is_client_admin(user: UserModel) -> bool:
    """
    Check if a user is a client admin (has admin role with CLIENT scope).
    
    Args:
        user: UserModel instance
        
    Returns:
        bool: True if user is a client admin, False otherwise
    """
    if not user.roles:
        return False
    
    for role in user.roles:
        if (role.name == "admin" and 
            hasattr(role, 'scope') and 
            role.scope.value == "client"):
            return True
    return False


def user_has_role(user: UserModel, role_name: str) -> bool:
    """
    Check if a user has a specific role by name.
    Works with Beanie Link roles.
    
    Args:
        user: UserModel instance
        role_name: Name of the role to check for (e.g., "super_admin")
        
    Returns:
        bool: True if user has the role, False otherwise
    """
    if not user.roles:
        return False
    
    for role in user.roles:
        if role.name == role_name:
            return True
    
    return False


def user_has_any_role(user: UserModel, role_names: List[str]) -> bool:
    """
    Check if a user has any of the specified roles.
    
    Args:
        user: UserModel instance
        role_names: List of role names to check for
        
    Returns:
        bool: True if user has any of the roles, False otherwise
    """
    if not user.roles:
        return False
    
    user_role_names = {role.name for role in user.roles}
    return bool(user_role_names.intersection(role_names))


def user_get_role_names(user: UserModel) -> List[str]:
    """
    Get all role names for a user.
    
    Args:
        user: UserModel instance
        
    Returns:
        List[str]: List of role names
    """
    if not user.roles:
        return []
    
    return [role.name for role in user.roles]


# --- Dependency Factories for Role-Based Access ---

def require_role(role_name: str):
    """
    Dependency factory to require a specific role.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: UserModel = Depends(require_role("super_admin"))):
            return {"message": "Admin access granted"}
    """
    async def _require_role(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        if not user_has_role(current_user, role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {role_name}"
            )
        return current_user
    return _require_role


def require_any_role(role_names: List[str]):
    """
    Dependency factory to require any of the specified roles.
    
    Usage:
        @router.get("/admin-or-manager")
        async def endpoint(user: UserModel = Depends(require_any_role(["admin", "manager"]))):
            return {"message": "Access granted"}
    """
    async def _require_any_role(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        if not user_has_any_role(current_user, role_names):
            roles_str = ", ".join(role_names)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required any of: {roles_str}"
            )
        return current_user
    return _require_any_role


# --- Core Dependencies ---

def valid_account_id(account_id: str):
    try:
        return PydanticObjectId(account_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid ObjectId: {account_id}"
        )


def validate_object_id(object_id: str, object_type: str = "ObjectId") -> PydanticObjectId:
    """
    Utility function to validate and convert string to PydanticObjectId.
    
    Args:
        object_id: String representation of ObjectId
        object_type: Type name for error message (e.g., "User ID", "Role ID")
        
    Returns:
        PydanticObjectId: Validated ObjectId
        
    Raises:
        HTTPException: If ObjectId is invalid
    """
    try:
        return PydanticObjectId(object_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail=f"Invalid {object_type}: {object_id}"
        )

async def get_token_from_request(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme)
) -> str:
    """
    Extract token from either Authorization header or HTTP-only cookie.
    """
    # Try Authorization header first
    if token:
        return token
    
    # Try HTTP-only cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    
    # No token found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user_with_token(
    token: str = Depends(get_token_from_request)
) -> Tuple[UserModel, TokenDataSchema]:
    """
    Decodes JWT, then retrieves user from DB using Beanie ODM. Returns user and token payload.
    """
    token_data = security_service.decode_access_token(token)
    user = await user_service.get_user_by_id(PydanticObjectId(token_data.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user, token_data

async def get_current_user(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
) -> UserModel:
    return user_and_token[0]


# --- Permission-Based Dependencies ---

def require_permissions(
    any_of: Optional[List[str]] = None,
    all_of: Optional[List[str]] = None
):
    """
    A powerful dependency factory for permission-based access control with hierarchical checking.

    Supports hierarchical permissions where:
    - Manage permissions include read permissions
    - Broader scopes include narrower scopes
    - user:manage_all includes user:read_all, user:read_platform, user:read_client, user:read_self

    It can check for:
    - `any_of`: User must have at least one of the specified permissions.
    - `all_of`: User must have all of the specified permissions.

    Usage:
        # Require a single permission (hierarchical)
        Depends(require_permissions(all_of=["user:read_client"]))  # user:manage_client also works

        # Require one of several permissions (hierarchical)
        Depends(require_permissions(any_of=["user:read_all", "user:read_platform", "user:read_client"]))
    """
    async def _require_permissions_dependency(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # 1. Get user's effective permissions from the service layer
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)

        # 2. Import hierarchical checking function
        from .services.permission_service import check_hierarchical_permission

        # 3. Check for "any_of" condition using hierarchical logic
        if any_of:
            has_any_permission = any(
                check_hierarchical_permission(user_permissions, p) for p in any_of
            )
            if not has_any_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Requires one of the following permissions: {', '.join(any_of)}"
                )

        # 4. Check for "all_of" condition using hierarchical logic
        if all_of:
            missing_permissions = []
            for p in all_of:
                if not check_hierarchical_permission(user_permissions, p):
                    missing_permissions.append(p)
            
            if missing_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Missing required permissions: {', '.join(missing_permissions)}"
                )

        return current_user
    return _require_permissions_dependency


def has_permission(required_permission: str):
    """
    Dependency factory to check if the current user has the required permission.
    
    DEPRECATED: Use require_permissions(all_of=[permission]) instead.
    This function is kept for backwards compatibility.
    
    Usage:
        @router.post("/users", dependencies=[Depends(has_permission("user:create"))])
        async def create_user_endpoint():
            return {"message": "User creation allowed"}
    """
    # Use the new unified permission system internally
    return require_permissions(all_of=[required_permission])


def has_hierarchical_client_access(target_client_field: str = "account_id"):
    """
    Dependency factory for hierarchical client account access control.
    Validates that the user can access the target client account based on:
    - Super admins: Access everything
    - Platform admins: Access clients in their platform scope
    - Regular users: Access only their own client account
    
    Args:
        target_client_field: The path parameter or field name containing the target client ID
        
    Usage:
        @router.get("/clients/{account_id}/data")
        async def get_client_data(
            user: UserModel = Depends(has_hierarchical_client_access("account_id"))
        ):
            return {"message": "Access granted"}
    """
    async def _has_hierarchical_access(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Extract target client ID from path parameters
        target_client_id = request.path_params.get(target_client_field)
        if not target_client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameter: {target_client_field}"
            )
        
        # Get user's effective permissions
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)
        
        # Check if user is super admin (has all permissions)
        is_super_admin = user_has_role(current_user, "super_admin")
        
        # Use the enhanced service method to check access
        user_client_id = str(current_user.client_account.id) if current_user.client_account else None
        if not user_client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not associated with any client account."
            )
        
        can_access = await client_account_service.can_user_access_client_account(
            user_client_id=user_client_id,
            target_client_id=target_client_id,
            user_permissions=user_permissions,
            is_super_admin=is_super_admin
        )
        
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,  # Return 404 to prevent information disclosure
                detail="Client account not found"
            )
        
        return current_user
    return _has_hierarchical_access


# --- User Access Control Dependencies ---

def can_access_user(user_id_param: str = "user_id"):
    """
    Dependency factory for user access control.
    - Admins can access any user
    - Regular users can only access themselves
    
    Usage:
        @router.get("/users/{user_id}")
        async def get_user(user: UserModel = Depends(can_access_user())):
            return user
    """
    async def _can_access_user(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Extract user ID from path parameters
        target_user_id = request.path_params.get(user_id_param)
        if not target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameter: {user_id_param}"
            )
        
        # Validate ObjectId format
        target_user_object_id = validate_object_id(target_user_id, "User ID")
        
        # Get the target user
        target_user = await user_service.get_user_by_id(target_user_object_id)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        # Access control logic
        is_super_admin = user_has_role(current_user, "super_admin")
        is_client_admin = user_is_client_admin(current_user)
        is_admin = is_super_admin or is_client_admin
        is_self_access = str(current_user.id) == target_user_id
        
        if not is_admin and not is_self_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You can only access your own user data"
            )
        
        # For client admins, enforce client account scoping
        if is_client_admin and not is_super_admin:
            if target_user.client_account and current_user.client_account:
                if str(target_user.client_account.id) != str(current_user.client_account.id):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail="User not found"
                    )
        
        return target_user
    return _can_access_user


def require_self_or_admin(user_id_param: str = "user_id"):
    """
    Dependency factory that returns the current user if they can access the target user.
    Similar to can_access_user but returns the current_user instead of target_user.
    
    Usage:
        @router.put("/users/{user_id}")
        async def update_user(
            user_data: UserUpdateSchema,
            current_user: UserModel = Depends(require_self_or_admin())
        ):
            # current_user is guaranteed to have access
    """
    async def _require_self_or_admin(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # This dependency validates access but returns current_user
        await _can_access_user(request, current_user)
        return current_user
    
    # We need to create the inner function here
    async def _can_access_user(request: Request, current_user: UserModel) -> UserModel:
        target_user_id = request.path_params.get(user_id_param)
        if not target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameter: {user_id_param}"
            )
        
        target_user_object_id = validate_object_id(target_user_id, "User ID")
        
        target_user = await user_service.get_user_by_id(target_user_object_id)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        is_super_admin = user_has_role(current_user, "super_admin")
        is_client_admin = user_is_client_admin(current_user)
        is_admin = is_super_admin or is_client_admin
        is_self_access = str(current_user.id) == target_user_id
        
        if not is_admin and not is_self_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You can only access your own user data"
            )
        
        if is_client_admin and not is_super_admin:
            if target_user.client_account and current_user.client_account:
                if str(target_user.client_account.id) != str(current_user.client_account.id):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail="User not found"
                    )
        return target_user
    
    return _require_self_or_admin


# --- Commonly Used Dependencies ---

# Admin access (any admin role)  
require_admin = require_any_role(["super_admin", "admin"])


# --- New Unified Permission Dependencies ---

# User Management
can_read_users = require_permissions(any_of=["user:read_all", "user:read_platform", "user:read_client"])
can_manage_users = require_permissions(any_of=["user:manage_all", "user:manage_platform", "user:manage_client"])

# Role Management
can_read_roles = require_permissions(any_of=["role:read_all", "role:read_platform", "role:read_client"])
can_manage_roles = require_permissions(any_of=["role:manage_all", "role:manage_platform", "role:manage_client"])

# Group Management
can_read_groups = require_permissions(any_of=["group:read_all", "group:read_platform", "group:read_client"])
can_manage_groups = require_permissions(any_of=["group:manage_all", "group:manage_platform", "group:manage_client"])

# Client Account Management  
can_read_client_accounts = require_permissions(any_of=["client:read_all", "client:read_platform"])
can_manage_client_accounts = require_permissions(any_of=["client:manage_all", "client:manage_platform"])

# Permission Management
can_read_permissions = require_permissions(any_of=["permission:read_all", "permission:read_platform"])
can_manage_permissions = require_permissions(any_of=["permission:manage_all", "permission:manage_platform"])


# --- Enhanced Commonly Used Dependencies ---


def require_admin_or_permission(permission_name: str):
    """
    Dependency that requires EITHER admin role OR specific permission.
    
    DEPRECATED: Use require_permissions() or role-based dependencies instead.
    This function is kept for backwards compatibility.
    
    Usage:
        @router.get("/users")
        async def get_users(
            user: UserModel = Depends(require_admin_or_permission("user:read"))
        ):
            # User either has admin role OR user:read permission
    """
    async def _require_admin_or_permission(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Check if user is any kind of admin first
        is_admin = user_has_any_role(current_user, ["super_admin", "admin", "client_admin"])
        
        if is_admin:
            return current_user
        
        # Use the unified permission system for permission checking
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)
        if permission_name in user_permissions:
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required: admin role or '{permission_name}' permission"
        )
    return _require_admin_or_permission


# FIXED: More restrictive dependencies for system management
require_user_read_access = require_admin_or_permission("user:read_client")  # Admins or users with user:read_client can read user lists
require_user_manage_access = require_admin_or_permission("user:manage")
require_role_read_access = require_admin  # Only admins can read role lists  
require_group_read_access = require_admin_or_permission("group:read_client")  # Admins or users with group:read_client can read groups
require_permission_read_access = require_admin  # Only admins can read permission lists

# Granular management permissions (for specific operations)
require_role_manage_access = require_admin_or_permission("role:manage_client")
require_group_manage_access = require_admin_or_permission("group:manage_client")
require_permission_manage_access = require_admin_or_permission("permission:manage_client")

# --- DEPRECATED DEPENDENCIES (Migrated to require_permissions) ---
# These dependencies remain for backwards compatibility during migration
# TODO: Remove after all routes have been migrated to new pattern 