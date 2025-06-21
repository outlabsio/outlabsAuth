from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..database import get_database
from ..services.permission_service import permission_service
from ..schemas.permission_schema import PermissionCreateSchema, PermissionResponseSchema
from ..dependencies import has_permission

router = APIRouter(
    prefix="/v1/permissions",
    tags=["Permission Management"],
    dependencies=[Depends(has_permission("permission:read"))]
)

@router.post("/", response_model=PermissionResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("permission:create"))])
async def create_permission(
    permission_data: PermissionCreateSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create a new permission.
    
    Permissions should follow a convention like:
    `service:<resource>:<action>` (e.g., `billing:invoice:read`).
    
    This endpoint is for seeding and administrative purposes.
    """
    existing_permission = await permission_service.get_permission_by_id(db, permission_data.id)
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission with ID '{permission_data.id}' already exists."
        )
    
    new_permission = await permission_service.create_permission(db, permission_data)
    return new_permission

@router.get("/", response_model=List[PermissionResponseSchema])
async def get_all_permissions(
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of all permissions.
    """
    permissions = await permission_service.get_permissions(db, skip=skip, limit=limit)
    return permissions 