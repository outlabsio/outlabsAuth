from beanie import PydanticObjectId
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Tuple, Optional

from .services.security_service import security_service
from .services.user_service import user_service
from .services.role_service import role_service
from .services.group_service import group_service
from .services.client_account_service import client_account_service
from .models.user_model import UserModel
from .schemas.auth_schema import TokenDataSchema

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)

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

def has_permission(required_permission: str):
    """
    Dependency factory to check if the current user has the required permission.
    Now includes permissions from both direct roles and group memberships.
    Uses clean permission names (e.g., "user:create", "listings:manage").
    """
    async def _has_permission(
        user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
    ):
        current_user, _ = user_and_token
        
        # Get all effective permissions (direct roles + group memberships)
        # Returns clean permission names from resolved ObjectIds
        user_permissions = await group_service.get_user_effective_permissions(current_user.id)
        
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
    """
    async def _has_hierarchical_access(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ):
        # Extract target client ID from path parameters
        target_client_id = request.path_params.get(target_client_field)
        if not target_client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameter: {target_client_field}"
            )
        
        # Get user's effective permissions
        user_permissions = await group_service.get_user_effective_permissions(current_user.id)
        
        # Check if user is super admin (has all permissions)
        is_super_admin = "client_account:create" in user_permissions and "client_account:delete" in user_permissions
        
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

async def get_current_user(
    user_and_token: Tuple[UserModel, TokenDataSchema] = Depends(get_current_user_with_token)
) -> UserModel:
    return user_and_token[0] 