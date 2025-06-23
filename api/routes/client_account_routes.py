from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Union, Optional
from beanie import PydanticObjectId

from ..services.client_account_service import client_account_service
from ..schemas.client_account_schema import ClientAccountCreateSchema, ClientAccountUpdateSchema, ClientAccountResponseSchema
from ..dependencies import has_permission, valid_account_id, get_current_user, has_hierarchical_client_access
from ..services.group_service import group_service

router = APIRouter(
    prefix="/v1/client_accounts",
    tags=["Client Account Management"],
    dependencies=[Depends(has_permission("client_account:read"))]
)

@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("client_account:create"))], responses={
    201: {"model": ClientAccountResponseSchema},
    409: {"description": "Client account with this name already exists"}
})
async def create_client_account(
    account_data: ClientAccountCreateSchema
):
    new_account = await client_account_service.create_client_account(account_data)
    
    # Use the new Pydantic v2 method that automatically handles ObjectId serialization
    return ClientAccountResponseSchema.model_validate(new_account, from_attributes=True)

@router.post("/sub-clients", status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("client_account:create_sub"))], responses={
    201: {"model": ClientAccountResponseSchema},
    409: {"description": "Client account with this name already exists"},
    403: {"description": "Insufficient permissions to create sub-clients"}
})
async def create_sub_client_account(
    account_data: ClientAccountCreateSchema,
    current_user = Depends(get_current_user)
):
    """
    Create a sub-client account under the current user's client account.
    Only available to platform admins with client_account:create_sub permission.
    """
    # Get current user's client account ID
    user_client_id = str(current_user.client_account.id) if current_user.client_account else None
    if not user_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any client account."
        )
    
    # Create sub-client with hierarchical relationship
    new_account = await client_account_service.create_client_account(
        account_data, 
        created_by_client_id=user_client_id
    )
    
    return ClientAccountResponseSchema.model_validate(new_account, from_attributes=True)

@router.get("/", responses={
    200: {"model": List[ClientAccountResponseSchema]}
})
async def get_all_client_accounts(
    skip: int = 0,
    limit: int = 100,
    platform_scope: Optional[str] = Query(None, description="Filter by platform scope (platform/created/all)"),
    current_user = Depends(get_current_user)
):
    """
    Retrieve client accounts with hierarchical filtering based on user permissions.
    - Super admins: See all accounts
    - Platform admins with read_platform: See all accounts in their platform
    - Platform admins with read_created: See only accounts they created
    - Regular users: See only their own account
    """
    user_permissions = await group_service.get_user_effective_permissions(current_user.id)
    user_client_id = str(current_user.client_account.id) if current_user.client_account else None
    
    # Check if user is super admin
    is_super_admin = "client_account:create" in user_permissions and "client_account:delete" in user_permissions
    
    if is_super_admin:
        # Super admin sees everything
        accounts = await client_account_service.get_client_accounts(skip=skip, limit=limit)
    elif "client_account:read_platform" in user_permissions and user_client_id:
        # Platform admin with platform scope
        user_client = await client_account_service.get_client_account_by_id(PydanticObjectId(user_client_id))
        if user_client and user_client.platform_id:
            accounts = await client_account_service.get_client_accounts_by_platform(
                user_client.platform_id, skip=skip, limit=limit
            )
        else:
            accounts = []
    elif "client_account:read_created" in user_permissions and user_client_id:
        # Platform admin with created scope
        accounts = await client_account_service.get_client_accounts_created_by(
            user_client_id, skip=skip, limit=limit
        )
    else:
        # Regular user sees only their own account
        if user_client_id:
            user_account = await client_account_service.get_client_account_by_id(PydanticObjectId(user_client_id))
            accounts = [user_account] if user_account else []
        else:
            accounts = []
    
    # Use Pydantic v2 model validation for automatic ObjectId handling
    return [ClientAccountResponseSchema.model_validate(account, from_attributes=True) for account in accounts]

@router.get("/my-sub-clients", dependencies=[Depends(has_permission("client_account:read_created"))], responses={
    200: {"model": List[ClientAccountResponseSchema]}
})
async def get_my_sub_clients(
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(get_current_user)
):
    """
    Get all sub-clients created by the current user's client account.
    """
    user_client_id = str(current_user.client_account.id) if current_user.client_account else None
    if not user_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any client account."
        )
    
    sub_clients = await client_account_service.get_client_accounts_created_by(
        user_client_id, skip=skip, limit=limit
    )
    
    return [ClientAccountResponseSchema.model_validate(account, from_attributes=True) for account in sub_clients]

@router.get("/{account_id}", responses={
    200: {"model": ClientAccountResponseSchema},
    404: {"description": "Client account not found"}
})
async def get_client_account_by_id(
    account_id: PydanticObjectId = Depends(valid_account_id),
    current_user = Depends(has_hierarchical_client_access("account_id"))
):
    """
    Get a specific client account by ID with hierarchical access control.
    """
    account = await client_account_service.get_client_account_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")
    
    # Use Pydantic v2 model validation for automatic ObjectId handling
    return ClientAccountResponseSchema.model_validate(account, from_attributes=True)

@router.put("/{account_id}", dependencies=[Depends(has_permission("client_account:update"))], responses={
    200: {"model": ClientAccountResponseSchema},
    404: {"description": "Client account not found"}
})
async def update_client_account(
    account_data: ClientAccountUpdateSchema,
    account_id: PydanticObjectId = Depends(valid_account_id),
    current_user = Depends(has_hierarchical_client_access("account_id"))
):
    """
    Update a client account with hierarchical access control.
    """
    updated_account = await client_account_service.update_client_account(account_id, account_data)
    if updated_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")
    
    # Use Pydantic v2 model validation for automatic ObjectId handling
    return ClientAccountResponseSchema.model_validate(updated_account, from_attributes=True)

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("client_account:delete"))])
async def delete_client_account(
    account_id: PydanticObjectId = Depends(valid_account_id),
    current_user = Depends(has_hierarchical_client_access("account_id"))
):
    """
    Delete a client account with hierarchical access control.
    """
    success = await client_account_service.delete_client_account(account_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found") 