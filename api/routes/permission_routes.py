from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

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
    permission_data: PermissionCreateSchema
):
    """
    Create a new permission.
    
    Permissions should follow a convention like:
    `service:<resource>:<action>` (e.g., `billing:invoice:read`).
    
    This endpoint is for seeding and administrative purposes.
    """
    existing_permission = await permission_service.get_permission_by_id(permission_data.id)
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission with ID '{permission_data.id}' already exists."
        )
    
    new_permission = await permission_service.create_permission(permission_data)
    # Convert to dict and ensure proper field mapping for response
    perm_dict = new_permission.model_dump(by_alias=True)
    perm_dict["id"] = perm_dict.pop("_id", perm_dict.get("id"))
    return perm_dict

@router.get("/", response_model=List[PermissionResponseSchema])
async def get_all_permissions(
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of all permissions.
    """
    permissions = await permission_service.get_permissions(skip=skip, limit=limit)
    # Convert each permission to dict and ensure proper field mapping
    perm_dicts = []
    for permission in permissions:
        perm_dict = permission.model_dump(by_alias=True)
        perm_dict["id"] = perm_dict.pop("_id", perm_dict.get("id"))
        perm_dicts.append(perm_dict)
    return perm_dicts

@router.get("/{permission_id}", response_model=PermissionResponseSchema)
async def get_permission_by_id(
    permission_id: str
):
    """
    Retrieve a single permission by its ID.
    """
    permission = await permission_service.get_permission_by_id(permission_id)
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found."
        )
    # Convert to dict and ensure proper field mapping for response
    perm_dict = permission.model_dump(by_alias=True)
    perm_dict["id"] = perm_dict.pop("_id", perm_dict.get("id"))
    return perm_dict 