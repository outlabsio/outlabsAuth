from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from beanie import PydanticObjectId

from ..services.client_account_service import client_account_service
from ..services.user_service import user_service
from ..services.group_service import group_service
from ..dependencies import get_current_user, convert_user_to_response
from ..schemas.client_account_schema import ClientAccountCreateSchema, ClientAccountResponseSchema
from ..schemas.user_schema import SuperUserCreateSchema, UserResponseSchema
from ..models.user_model import UserModel

router = APIRouter(
    prefix="/v1/platform",
    tags=["Platform Management"]
)

@router.get("/status", summary="Get Platform Initialization Status")
async def get_platform_status():
    """
    Checks if the platform has been initialized (i.e., if any user exists).
    This is a public endpoint used by the frontend to determine if it should show
    the setup page or the login page.
    """
    user_count = await UserModel.count()
    return {"initialized": user_count > 0}

@router.post("/initialize", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED,
             summary="Initialize Platform and Create Super User",
             description="Creates the first super user account. This endpoint can only be used once.")
async def initialize_platform(user_data: SuperUserCreateSchema):
    """
    Initializes the platform by creating the first super user.
    This can only be done when there are no other users in the system.
    """
    users = await user_service.get_users(limit=1)
    if users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Platform has already been initialized."
        )

    # Use the user_service to create the super user
    super_user = await user_service.create_super_user(email=user_data.email, password=user_data.password)

    if not super_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create super user."
        )
    return convert_user_to_response(super_user)

@router.get("/analytics", responses={
    200: {"description": "Platform analytics data"}
})
async def get_platform_analytics(
    current_user = Depends(get_current_user)
):
    """
    Retrieve platform-wide analytics across all client accounts.
    Only available to platform staff with appropriate permissions.
    """
    # Check if user has platform analytics permission and is platform staff
    user_permissions = await user_service.get_user_effective_permissions(current_user.id)
    is_platform_staff = getattr(current_user, 'is_platform_staff', False)
    
    if not is_platform_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform analytics access restricted to platform staff."
        )
    
    if "client_account:read" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to read client accounts."
        )
    
    # Get all client accounts for metrics
    all_clients = await client_account_service.get_client_accounts()
    
    # Get all users for metrics  
    all_users = await user_service.get_users()
    
    # Calculate platform metrics
    total_clients = len(all_clients)
    total_users = len(all_users)
    
    # Separate platform vs real estate companies
    platform_clients = [c for c in all_clients if "Platform" in c.name]
    real_estate_clients = [c for c in all_clients if "Platform" not in c.name]
    
    # Platform staff vs real estate users
    platform_users = [u for u in all_users if getattr(u, 'is_platform_staff', False)]
    client_users = [u for u in all_users if not getattr(u, 'is_platform_staff', False)]
    
    analytics = {
        "total_clients": total_clients,
        "total_users": total_users,
        "platform_clients": len(platform_clients),
        "real_estate_clients": len(real_estate_clients),
        "platform_staff": len(platform_users),
        "client_users": len(client_users),
        "client_breakdown": [
            {
                "name": client.name,
                "description": client.description,
                "user_count": len([u for u in all_users if u.client_account and str(u.client_account.id) == str(client.id)])
            }
            for client in all_clients
        ]
    }
    
    return analytics

 