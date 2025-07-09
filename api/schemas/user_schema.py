"""
User schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserProfileUpdate(BaseModel):
    """Update user profile request schema"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    avatar_url: Optional[str] = Field(None, max_length=500)
    preferences: Optional[Dict[str, Any]] = None


class UserProfileResponse(BaseModel):
    """User profile response schema"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def full_name(self) -> str:
        """Get full name"""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown"


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    email: EmailStr
    profile: UserProfileResponse
    is_active: bool
    is_system_user: bool
    email_verified: bool
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response"""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserSearchParams(BaseModel):
    """User search parameters"""
    query: Optional[str] = Field(None, description="Search in email, first name, last name")
    entity_id: Optional[str] = Field(None, description="Filter by entity membership")
    status: Optional[str] = Field(None, description="Filter by status (active/inactive/locked)")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UserStatusUpdate(BaseModel):
    """Update user status request schema"""
    status: str = Field(..., description="New status (active/inactive/locked)")
    
    @field_validator('status')
    def validate_status(cls, v):
        """Validate status value"""
        valid_statuses = ["active", "inactive", "locked"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


class UserInviteRequest(BaseModel):
    """User invitation request schema"""
    email: EmailStr
    entity_id: str
    role_id: str
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    send_email: bool = Field(True, description="Whether to send invitation email")


class UserInviteResponse(BaseModel):
    """User invitation response schema"""
    user: UserResponse
    temporary_password: Optional[str] = None
    invitation_sent: bool
    message: str


class UserPasswordResetRequest(BaseModel):
    """Admin password reset request schema"""
    send_email: bool = Field(True, description="Whether to send new password via email")


class UserPasswordResetResponse(BaseModel):
    """Admin password reset response schema"""
    message: str
    temporary_password: Optional[str] = None
    email_sent: bool


class UserMembershipRole(BaseModel):
    """User membership role schema"""
    id: str
    name: str
    display_name: str
    permissions: List[str]


class UserMembershipEntity(BaseModel):
    """User membership entity schema"""
    id: str
    name: str
    entity_type: str
    entity_class: str


class UserMembershipResponse(BaseModel):
    """User membership response schema"""
    id: str
    entity: UserMembershipEntity
    roles: List[UserMembershipRole]
    status: str
    joined_at: datetime
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class UserMembershipListResponse(BaseModel):
    """User membership list response schema"""
    user_id: str
    memberships: List[UserMembershipResponse]
    total: int


class UserStatsResponse(BaseModel):
    """User statistics response schema"""
    total_users: int
    active_users: int
    inactive_users: int
    locked_users: int
    recent_signups: int  # Users created in last 30 days
    recent_logins: int   # Users logged in in last 30 days


class UserBulkActionRequest(BaseModel):
    """Bulk action request schema"""
    user_ids: List[str] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., description="Action to perform (activate/deactivate/lock)")
    
    @field_validator('action')
    def validate_action(cls, v):
        """Validate action value"""
        valid_actions = ["activate", "deactivate", "lock"]
        if v not in valid_actions:
            raise ValueError(f"Action must be one of: {', '.join(valid_actions)}")
        return v


class UserBulkActionResponse(BaseModel):
    """Bulk action response schema"""
    successful: List[str]
    failed: List[Dict[str, str]]  # [{"user_id": "id", "error": "message"}]
    total_processed: int
    total_successful: int
    total_failed: int