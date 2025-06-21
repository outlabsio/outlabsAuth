from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from bson import ObjectId

from ..database import get_database
from ..services.client_account_service import client_account_service
from ..schemas.client_account_schema import ClientAccountCreateSchema, ClientAccountUpdateSchema, ClientAccountResponseSchema
from ..dependencies import has_permission, valid_object_id

router = APIRouter(
    prefix="/v1/client_accounts",
    tags=["Client Account Management"],
    dependencies=[Depends(has_permission("client_account:read"))]
)

@router.post("/", response_model=ClientAccountResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("client_account:create"))])
async def create_client_account(
    account_data: ClientAccountCreateSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    new_account = await client_account_service.create_client_account(db, account_data)
    return new_account

@router.get("/", response_model=List[ClientAccountResponseSchema])
async def get_all_client_accounts(
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = 0,
    limit: int = 100
):
    accounts = await client_account_service.get_client_accounts(db, skip=skip, limit=limit)
    return accounts

@router.get("/{account_id}", response_model=ClientAccountResponseSchema)
async def get_client_account_by_id(
    account_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    account = await client_account_service.get_client_account_by_id(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")
    return account

@router.put("/{account_id}", response_model=ClientAccountResponseSchema, dependencies=[Depends(has_permission("client_account:update"))])
async def update_client_account(
    account_data: ClientAccountUpdateSchema,
    account_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    updated_account = await client_account_service.update_client_account(db, account_id, account_data)
    if updated_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")
    return updated_account

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("client_account:delete"))])
async def delete_client_account(
    account_id: ObjectId = Depends(valid_object_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    deleted_count = await client_account_service.delete_client_account(db, account_id)
    if deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found") 