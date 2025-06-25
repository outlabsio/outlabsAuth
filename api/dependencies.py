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

def has_permission(required_permission: str):
    """
    Dependency factory to check if the current user has the required permission.
    Now includes permissions from both direct roles and group memberships.
    Uses clean permission names (e.g., "user:create", "listings:manage").
    
    Usage:
        @router.post("/users", dependencies=[Depends(has_permission("user:create"))])
        async def create_user_endpoint():
            return {"message": "User creation allowed"}
    """
    async def _has_permission(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Get all effective permissions (direct roles + group memberships)
        # Returns clean permission names from resolved ObjectIds
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)
        
        # Check for exact match
        if required_permission in user_permissions:
            return current_user
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action."
        )
    return _has_permission


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
        try:
            target_user_object_id = PydanticObjectId(target_user_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
                detail=f"Invalid ObjectId: {target_user_id}"
            )
        
        # Get the target user
        target_user = await user_service.get_user_by_id(target_user_object_id)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        # Access control logic
        is_super_admin = user_has_role(current_user, "super_admin")
        is_client_admin = False
        
        # Check for client admin role (role named "admin" with CLIENT scope)
        if current_user.roles:
            for role in current_user.roles:
                if (role.name == "admin" and 
                    hasattr(role, 'scope') and 
                    role.scope.value == "client"):
                    is_client_admin = True
                    break
        
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
        
        try:
            target_user_object_id = PydanticObjectId(target_user_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
                detail=f"Invalid ObjectId: {target_user_id}"
            )
        
        target_user = await user_service.get_user_by_id(target_user_object_id)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        is_super_admin = user_has_role(current_user, "super_admin")
        is_client_admin = False
        
        # Check for client admin role (role named "admin" with CLIENT scope)
        if current_user.roles:
            for role in current_user.roles:
                if (role.name == "admin" and 
                    hasattr(role, 'scope') and 
                    role.scope.value == "client"):
                    is_client_admin = True
                    break
        
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

# Super Admin access only
require_super_admin = require_role("super_admin")

# Admin access (any admin role)
require_admin = require_any_role(["super_admin", "admin"])

# Platform admin access
require_platform_admin = require_any_role(["super_admin", "platform_admin"])


# --- Scope-Based Admin Dependencies ---

def require_scope_admin(scope: str):
    """
    Dependency factory for scope-specific admin access.
    
    Usage:
        @router.post("/roles")
        async def create_role(
            role_data: RoleCreateSchema,
            admin_user: UserModel = Depends(require_scope_admin("client"))
        ):
            # admin_user is guaranteed to be admin in the requested scope
    """
    async def _require_scope_admin(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        from .models.role_model import RoleScope
        
        if scope == "system":
            if not user_has_role(current_user, "super_admin"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only super admins can perform this action"
                )
        elif scope == "platform":
            platform_admin_roles = [
                role for role in (current_user.roles or [])
                if (role.name == "admin" and role.scope == RoleScope.PLATFORM)
            ]
            is_super_admin = user_has_role(current_user, "super_admin")
            if not platform_admin_roles and not is_super_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only platform admins can perform this action"
                )
        elif scope == "client":
            if not current_user.client_account:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client account required for this action"
                )
            
            client_admin_roles = [
                role for role in (current_user.roles or [])
                if (role.name == "admin" and 
                    role.scope == RoleScope.CLIENT and 
                    role.scope_id == str(current_user.client_account.id))
            ]
            is_super_admin = user_has_role(current_user, "super_admin")
            if not client_admin_roles and not is_super_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only client admins can perform this action"
                )
        
        return current_user
    return _require_scope_admin


def require_admin_or_permission(permission_name: str):
    """
    Dependency that requires EITHER admin role OR specific permission.
    This is useful for endpoints that can be accessed by admins OR users with specific permissions.
    
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
        # Check if user is any kind of admin
        is_admin = user_has_any_role(current_user, ["super_admin", "admin", "client_admin"])
        
        if is_admin:
            return current_user
        
        # Check if user has the specific permission
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)
        if permission_name in user_permissions:
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required: admin role or '{permission_name}' permission"
        )
    return _require_admin_or_permission


# --- Enhanced Commonly Used Dependencies ---

# Scope-specific admin access
require_system_admin = require_scope_admin("system")
require_platform_admin_scope = require_scope_admin("platform")
require_client_admin_scope = require_scope_admin("client")

# FIXED: More restrictive dependencies for system management
require_user_read_access = require_admin_or_permission("user:manage_client")  # Admins or users with user:manage_client can read user lists
require_user_manage_access = require_admin_or_permission("user:manage")
require_role_read_access = require_admin  # Only admins can read role lists  
require_group_read_access = require_admin_or_permission("group:manage_client")  # Admins or users with group:manage_client can read groups
require_permission_read_access = require_admin  # Only admins can read permission lists

# Granular management permissions (for specific operations)
require_role_manage_access = require_admin_or_permission("role:manage_client")
require_group_manage_access = require_admin_or_permission("group:manage_client")
require_permission_manage_access = require_admin_or_permission("permission:manage_client")

# Self-access dependencies (users can access their own data)
def require_self_access():
    """Allows users to access only their own data."""
    async def _require_self_access(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # This is for endpoints like /users/me where users access their own data
        return current_user
    return _require_self_access

# Client-scoped read access (for within-client operations)  
def require_client_scoped_read():
    """Users can read data within their own client scope."""
    async def _require_client_scoped_read(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Check if user is admin (can read cross-client) or has client account
        is_admin = user_has_any_role(current_user, ["super_admin", "admin", "client_admin"])
        
        if is_admin:
            return current_user
            
        if not current_user.client_account:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No client account associated with user"
            )
            
        return current_user
    return _require_client_scoped_read

# Scoped permission dependencies for better granularity
def require_user_read_self():
    """Users can read their own user data only."""
    async def _require_user_read_self(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Any authenticated user can read their own data
        return current_user
    return _require_user_read_self

def require_user_read_client_scope():
    """Users can read users within their client scope."""
    async def _require_user_read_client(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Admin OR user with user:read permission within client scope
        is_admin = user_has_any_role(current_user, ["super_admin", "admin", "client_admin"])
        
        if is_admin:
            return current_user
            
        # Check for scoped permission
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)
        if "user:read_client" in user_permissions:
            return current_user
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Required: admin role or 'user:read_client' permission"
        )
    return _require_user_read_client

def require_group_read_client_scope():
    """Users can read groups within their client scope."""
    async def _require_group_read_client(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Admin OR user with group:read permission within client scope
        is_admin = user_has_any_role(current_user, ["super_admin", "admin", "client_admin"])
        
        if is_admin:
            return current_user
            
        # Check for scoped permission
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)
        if "group:read_client" in user_permissions:
            return current_user
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Required: admin role or 'group:read_client' permission"
        )
    return _require_group_read_client 