from pydantic import BaseModel, EmailStr

class PasswordResetRequestSchema(BaseModel):
    """
    Schema for requesting a password reset.
    """
    email: EmailStr

class PasswordResetConfirmSchema(BaseModel):
    """
    Schema for confirming a password reset with a token.
    """
    token: str
    new_password: str

class PasswordChangeSchema(BaseModel):
    """
    Schema for a user changing their own password.
    """
    current_password: str
    new_password: str 