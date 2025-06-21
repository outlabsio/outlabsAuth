from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Union
from beanie import PydanticObjectId

from ..services.client_account_service import client_account_service
from ..schemas.client_account_schema import ClientAccountCreateSchema, ClientAccountUpdateSchema, ClientAccountResponseSchema
from ..dependencies import has_permission, valid_account_id

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

@router.get("/", responses={
    200: {"model": List[ClientAccountResponseSchema]}
})
async def get_all_client_accounts(
    skip: int = 0,
    limit: int = 100
):
    accounts = await client_account_service.get_client_accounts(skip=skip, limit=limit)
    
    # Use Pydantic v2 model validation for automatic ObjectId handling
    return [ClientAccountResponseSchema.model_validate(account, from_attributes=True) for account in accounts]

@router.get("/{account_id}", responses={
    200: {"model": ClientAccountResponseSchema},
    404: {"description": "Client account not found"}
})
async def get_client_account_by_id(
    account_id: PydanticObjectId = Depends(valid_account_id)
):
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
    account_id: PydanticObjectId = Depends(valid_account_id)
):
    updated_account = await client_account_service.update_client_account(account_id, account_data)
    if updated_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")
    
    # Use Pydantic v2 model validation for automatic ObjectId handling
    return ClientAccountResponseSchema.model_validate(updated_account, from_attributes=True)

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("client_account:delete"))])
async def delete_client_account(
    account_id: PydanticObjectId = Depends(valid_account_id)
):
    success = await client_account_service.delete_client_account(account_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found") 