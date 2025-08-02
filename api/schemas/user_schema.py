"""
User schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator
from api.models.user_model import UserStatus


class UserEntityRole(BaseModel):
    """User's role within an entity"""
    id: str
    name: str
    display_name: str
    permissions: List[str]


class UserEntity(BaseModel):
    """Entity information for user response"""
    id: str
    name: str
    slug: str
    entity_type: str
    entity_class: str
    parent_id: Optional[str] = None
    roles: List[UserEntityRole]
    status: str
    joined_at: datetime


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
    status: UserStatus
    is_system_user: bool
    email_verified: bool
    last_login: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    entities: List[UserEntity] = Field(default_factory=list)
    
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
    status: Optional[UserStatus] = Field(None, description="Filter by user status")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UserStatusUpdate(BaseModel):
    """Update user status request schema"""
    status: UserStatus = Field(..., description="New user status")


class UserEntityAssignment(BaseModel):
    """Entity and role assignment for user"""
    entity_id: str
    role_ids: List[str] = Field(default_factory=list)
    status: str = Field(default="active")
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class UserCreateRequest(BaseModel):
    """User creation request schema"""
    email: EmailStr
    password: Optional[str] = Field(None, min_length=8)
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    entity_assignments: List[UserEntityAssignment] = Field(default_factory=list)
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    send_welcome_email: bool = Field(default=True)
    
    @field_validator('password')
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if v is None:  # Allow None for password generation
            return v
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserUpdateRequest(BaseModel):
    """User update request schema"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    status: Optional[UserStatus] = None
    entity_assignments: Optional[List[UserEntityAssignment]] = None


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
    suspended_users: int
    banned_users: int
    terminated_users: int
    recent_signups: int  # Users created in last 30 days
    recent_logins: int   # Users logged in in last 30 days


class UserBulkActionRequest(BaseModel):
    """Bulk action request schema"""
    user_ids: List[str] = Field(..., min_items=1, max_items=100)
    status: UserStatus = Field(..., description="New status to apply to users")
    
    @field_validator('status')
    def validate_status(cls, v):
        """Validate status value"""
        # Only allow certain bulk status updates
        allowed_statuses = [UserStatus.ACTIVE, UserStatus.INACTIVE, UserStatus.SUSPENDED, UserStatus.BANNED]
        if v not in allowed_statuses:
            raise ValueError(f"Bulk status update must be one of: {', '.join([s.value for s in allowed_statuses])}")
        return v


class UserBulkActionResponse(BaseModel):
    """Bulk action response schema"""
    successful: List[str]
    failed: List[Dict[str, str]]  # [{"user_id": "id", "error": "message"}]
    total_processed: int
    total_successful: int
    total_failed: int