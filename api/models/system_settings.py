from beanie import Document
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone

class EmailConfig(BaseModel):
    """Email configuration settings"""
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: Optional[str] = None  # Stored encrypted
    use_tls: bool = True
    from_email: EmailStr
    from_name: str = "Outlabs Auth System"

class SystemSettingsModel(Document):
    """System-wide settings"""
    email_config: Optional[EmailConfig] = None
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
    
    class Settings:
        name = "system_settings"
        
    def update_email_config(self, config: EmailConfig):
        """Update email configuration"""
        self.email_config = config
        self.updated_at = datetime.now(timezone.utc)