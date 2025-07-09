"""
System Routes
API endpoints for system initialization and status
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, EmailStr

from api.services.system_service import system_service
from api.models import UserModel
from api.routes.auth_routes import get_current_user

router = APIRouter()


# Request/Response schemas
class SystemStatusResponse(BaseModel):
    """System status response"""
    initialized: bool = Field(..., description="Whether the system is initialized")
    user_count: int = Field(..., description="Number of users in the system")
    has_system_admin_role: bool = Field(..., description="Whether system admin role exists")
    has_root_entity: bool = Field(..., description="Whether root entity exists")
    version: str = Field(..., description="System version")
    requires_setup: bool = Field(..., description="Whether system requires setup")


class SystemInitializeRequest(BaseModel):
    """System initialization request"""
    email: EmailStr = Field(..., description="Email for the superuser")
    password: str = Field(..., min_length=8, description="Password for the superuser")
    first_name: Optional[str] = Field("System", description="First name")
    last_name: Optional[str] = Field("Administrator", description="Last name")


class SystemInitializeResponse(BaseModel):
    """System initialization response"""
    initialized: bool
    user: dict = Field(..., description="Created user information")
    root_entity: dict = Field(..., description="Root entity information")
    message: str


class SystemResetRequest(BaseModel):
    """System reset request"""
    confirmation: str = Field(..., description="Must be 'RESET_ENTIRE_SYSTEM' to proceed")


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """
    Get system initialization status
    
    This endpoint is public and used to determine if the system needs initialization.
    """
    status = await system_service.get_system_status()
    return SystemStatusResponse(**status)


@router.post("/initialize", response_model=SystemInitializeResponse)
async def initialize_system(request: SystemInitializeRequest):
    """
    Initialize the system with the first superuser
    
    This endpoint can only be called once when the system is not initialized.
    It creates:
    - The root platform entity
    - System roles (system_admin, platform_admin, etc.)
    - The first superuser with system_admin role
    """
    result = await system_service.initialize_system(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name
    )
    
    return SystemInitializeResponse(**result)


@router.post("/reset", include_in_schema=False)
async def reset_system(
    request: SystemResetRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    Reset the entire system (DANGEROUS - Development only)
    
    This endpoint is hidden from the API documentation and only works in development.
    Requires system_admin role and confirmation string.
    """
    # Check if user is system admin
    if not current_user.is_system_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can reset the system"
        )
    
    result = await system_service.reset_system(request.confirmation)
    return result