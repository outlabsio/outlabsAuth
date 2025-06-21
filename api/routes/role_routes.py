from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from ..database import get_database
from ..services.role_service import role_service
from ..schemas.role_schema import RoleCreateSchema, RoleUpdateSchema, RoleResponseSchema
from ..dependencies import has_permission

router = APIRouter(
    prefix="/v1/roles",
    tags=["Role Management"],
    dependencies=[Depends(has_permission("role:read"))]
)

@router.post("/", response_model=RoleResponseSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(has_permission("role:create"))])
async def create_role(
    role_data: RoleCreateSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create a new role.
    
    A role's `_id` should be a unique string identifier (e.g., "platform_admin").
    """
    existing_role = await role_service.get_role_by_id(db, role_data.id)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with ID '{role_data.id}' already exists."
        )
    
    new_role = await role_service.create_role(db, role_data)
    return new_role

@router.get("/", response_model=List[RoleResponseSchema])
async def get_all_roles(
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of all roles.
    """
    roles = await role_service.get_roles(db, skip=skip, limit=limit)
    return roles

@router.get("/{role_id}", response_model=RoleResponseSchema)
async def get_role_by_id(
    role_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieve a single role by its ID.
    """
    role = await role_service.get_role_by_id(db, role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found."
        )
    return role

@router.put("/{role_id}", response_model=RoleResponseSchema, dependencies=[Depends(has_permission("role:update"))])
async def update_role(
    role_id: str,
    role_data: RoleUpdateSchema,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update a role's details, such as its name, description, or permissions.
    """
    updated_role = await role_service.update_role(db, role_id, role_data)
    if updated_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found."
        )
    return updated_role

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_permission("role:delete"))])
async def delete_role(
    role_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Delete a role by its ID.
    
    Note: This will fail if the role is currently assigned to any users.
    (This logic needs to be implemented in the service).
    """
    deleted_count = await role_service.delete_role(db, role_id)
    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found."
        ) 