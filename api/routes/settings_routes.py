from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from api.dependencies import get_current_user, require_permissions
from api.models.user_model import UserModel
from api.models.system_settings import SystemSettingsModel, EmailConfig
from api.services.email_service import system_email_service
from api.config import settings

router = APIRouter()

class EmailSettingsRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: Optional[str] = None
    use_tls: bool = True
    from_email: EmailStr
    from_name: str

class EmailSettingsResponse(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str = "********"  # Always masked in response
    use_tls: bool
    from_email: str
    from_name: str

class TestEmailResponse(BaseModel):
    message: str

@router.get("/email", response_model=EmailSettingsResponse, dependencies=[Depends(require_permissions(all_of=["system:manage_settings"]))])
async def get_email_settings():
    """Get current email settings"""
    # Try to get existing settings
    system_settings = await SystemSettingsModel.find_one()
    
    if not system_settings or not system_settings.email_config:
        # Return default settings from environment
        return EmailSettingsResponse(
            smtp_host=settings.SYSTEM_SMTP_HOST,
            smtp_port=settings.SYSTEM_SMTP_PORT,
            smtp_user=settings.SYSTEM_SMTP_USER,
            smtp_password="********",
            use_tls=settings.SYSTEM_SMTP_USE_TLS,
            from_email=settings.SYSTEM_EMAIL_FROM,
            from_name=settings.SYSTEM_EMAIL_FROM_NAME
        )
    
    return EmailSettingsResponse(
        smtp_host=system_settings.email_config.smtp_host,
        smtp_port=system_settings.email_config.smtp_port,
        smtp_user=system_settings.email_config.smtp_user,
        smtp_password="********",
        use_tls=system_settings.email_config.use_tls,
        from_email=system_settings.email_config.from_email,
        from_name=system_settings.email_config.from_name
    )

@router.put("/email", response_model=EmailSettingsResponse, dependencies=[Depends(require_permissions(all_of=["system:manage_settings"]))])
async def update_email_settings(request: EmailSettingsRequest):
    """Update email settings"""
    # Get or create system settings
    system_settings = await SystemSettingsModel.find_one()
    if not system_settings:
        system_settings = SystemSettingsModel()
    
    # Create email config
    email_config = EmailConfig(
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        smtp_user=request.smtp_user,
        smtp_password=request.smtp_password if request.smtp_password else (
            system_settings.email_config.smtp_password if system_settings.email_config else settings.SYSTEM_SMTP_PASSWORD
        ),
        use_tls=request.use_tls,
        from_email=request.from_email,
        from_name=request.from_name
    )
    
    # Update settings
    system_settings.update_email_config(email_config)
    await system_settings.save()
    
    # Update the email service with new settings
    system_email_service.update_config(
        smtp_host=email_config.smtp_host,
        smtp_port=email_config.smtp_port,
        smtp_user=email_config.smtp_user,
        smtp_password=email_config.smtp_password,
        use_tls=email_config.use_tls,
        from_email=email_config.from_email,
        from_name=email_config.from_name
    )
    
    return EmailSettingsResponse(
        smtp_host=email_config.smtp_host,
        smtp_port=email_config.smtp_port,
        smtp_user=email_config.smtp_user,
        smtp_password="********",
        use_tls=email_config.use_tls,
        from_email=email_config.from_email,
        from_name=email_config.from_name
    )

@router.post("/email/test", response_model=TestEmailResponse, dependencies=[Depends(require_permissions(all_of=["system:manage_settings"]))])
async def send_test_email(current_user: UserModel = Depends(get_current_user)):
    """Send a test email to the current user"""
    try:
        await system_email_service.send_email(
            to_email=current_user.email,
            subject="Test Email from Outlabs Auth",
            template_name="test_email",
            template_data={
                "user_name": f"{current_user.first_name} {current_user.last_name}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "current_year": datetime.now().year
            }
        )
        return TestEmailResponse(message=f"Test email sent successfully to {current_user.email}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test email: {str(e)}"
        )