"""
System Email Service
Handles email sending for system administration only (super admin level).
This is NOT for platform or client-level emails.
"""
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


class SystemEmailService:
    """
    Email service for system-level communications only.
    Uses async SMTP for non-blocking email sending.
    """
    
    def __init__(self):
        # SMTP Configuration from settings
        self.smtp_host = settings.SYSTEM_SMTP_HOST
        self.smtp_port = settings.SYSTEM_SMTP_PORT
        self.smtp_user = settings.SYSTEM_SMTP_USER
        self.smtp_password = settings.SYSTEM_SMTP_PASSWORD
        self.use_tls = settings.SYSTEM_SMTP_USE_TLS
        
        # System email settings
        self.from_email = settings.SYSTEM_EMAIL_FROM
        self.from_name = settings.SYSTEM_EMAIL_FROM_NAME
        
        # Initialize Jinja2 for templates
        template_dir = Path(__file__).parent.parent / "email_templates" / "system"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    async def send_email(
        self, 
        to_email: str, 
        subject: str, 
        template_name: str,
        template_data: Dict[str, Any],
        to_name: Optional[str] = None
    ) -> bool:
        """
        Send an email using a template.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Name of the template file (without extension)
            template_data: Data to pass to the template
            to_name: Optional recipient name
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # Load and render templates
            html_template = self.jinja_env.get_template(f"{template_name}.html")
            html_content = html_template.render(**template_data)
            
            # Try to load text template (optional)
            text_content = None
            try:
                text_template = self.jinja_env.get_template(f"{template_name}.txt")
                text_content = text_template.render(**template_data)
            except:
                pass  # Text template is optional
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = f"{to_name} <{to_email}>" if to_name else to_email
            msg['Date'] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            # Add text part if available
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            
            # Add HTML part
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email asynchronously
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user if self.smtp_user else None,
                password=self.smtp_password if self.smtp_password else None,
                start_tls=self.use_tls
            )
            
            logger.info(f"System email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send system email to {to_email}: {str(e)}")
            return False
    
    async def send_password_reset_email(
        self, 
        email: str, 
        name: str, 
        reset_token: str
    ) -> bool:
        """
        Send password reset email to system administrator.
        """
        frontend_url = settings.FRONTEND_URL
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
        
        template_data = {
            "user_name": name,
            "reset_link": reset_link,
            "expiry_hours": 1,
            "system_name": "Outlabs Auth",
            "current_year": datetime.now().year
        }
        
        return await self.send_email(
            to_email=email,
            to_name=name,
            subject="Reset Your Password - Outlabs Auth System",
            template_name="password_reset",
            template_data=template_data
        )
    
    async def send_system_invitation_email(
        self,
        email: str,
        inviter_name: str,
        invitation_token: str,
        role_name: str = "System Administrator"
    ) -> bool:
        """
        Send invitation email for new system administrator.
        """
        frontend_url = settings.FRONTEND_URL
        invitation_link = f"{frontend_url}/invitation?token={invitation_token}"
        
        template_data = {
            "inviter_name": inviter_name,
            "invitation_link": invitation_link,
            "role_name": role_name,
            "system_name": "Outlabs Auth",
            "current_year": datetime.now().year
        }
        
        return await self.send_email(
            to_email=email,
            subject=f"Invitation to join Outlabs Auth as {role_name}",
            template_name="system_invitation",
            template_data=template_data
        )
    
    async def send_security_alert_email(
        self,
        email: str,
        name: str,
        alert_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """
        Send security alert to system administrator.
        """
        template_data = {
            "user_name": name,
            "alert_type": alert_type,
            "details": details,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "system_name": "Outlabs Auth",
            "current_year": datetime.now().year
        }
        
        return await self.send_email(
            to_email=email,
            to_name=name,
            subject=f"Security Alert: {alert_type}",
            template_name="security_alert",
            template_data=template_data
        )


# Create singleton instance
system_email_service = SystemEmailService()