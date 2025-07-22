"""
Authentication schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str = Field(..., min_length=1)
    device_info: Optional[Dict[str, Any]] = None


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request schema"""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request schema"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema"""
    token: str
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class EmailVerificationRequest(BaseModel):
    """Email verification request schema"""
    token: str


class UserInfoResponse(BaseModel):
    """User info response schema"""
    id: str
    email: str
    profile: Dict[str, Any]
    is_active: bool
    email_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class ChangePasswordRequest(BaseModel):
    """Change password request schema"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


class RegisterRequest(BaseModel):
    """User registration request schema"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = None
    
    @field_validator('password')
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v