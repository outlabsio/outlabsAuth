"""
Email Service
Handles system email sending with templates and background processing
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import EmailStr

from api.config import settings
from api.models import UserModel, EntityModel

# Configure logging
logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending system emails with templates"""
    
    def __init__(self):
        # Template directory
        template_dir = Path(__file__).parent.parent / "email_templates"
        template_dir.mkdir(exist_ok=True)
        
        # Initialize Jinja2 environment
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Email queue for background processing
        self.email_queue: asyncio.Queue = asyncio.Queue()
        
        # Start background worker if SMTP is configured
        if self._is_smtp_configured():
            asyncio.create_task(self._email_worker())
            logger.info("Email service initialized with background worker")
        else:
            logger.warning("SMTP not configured, emails will be logged only")
    
    def _is_smtp_configured(self) -> bool:
        """Check if SMTP settings are configured"""
        return bool(
            settings.SMTP_HOST and 
            settings.SMTP_PORT and
            settings.SMTP_USERNAME and
            settings.SMTP_PASSWORD
        )
    
    async def _email_worker(self):
        """Background worker to process email queue"""
        logger.info("Email worker started")
        
        while True:
            try:
                # Get email from queue (blocks until available)
                email_data = await self.email_queue.get()
                
                # Send email
                await self._send_email_async(
                    to_email=email_data['to_email'],
                    subject=email_data['subject'],
                    html_body=email_data['html_body'],
                    text_body=email_data.get('text_body')
                )
                
                # Mark task as done
                self.email_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in email worker: {e}")
                # Continue processing other emails
    
    async def _send_email_async(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ):
        """Send email asynchronously"""
        try:
            # Run SMTP operations in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email_sync,
                to_email,
                subject,
                html_body,
                text_body
            )
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            # Don't raise - we don't want to crash the worker
    
    def _send_email_sync(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ):
        """Synchronous email sending via SMTP"""
        if not self._is_smtp_configured():
            # Log email instead of sending
            logger.info(f"📧 Email (not sent - SMTP not configured):")
            logger.info(f"   To: {to_email}")
            logger.info(f"   Subject: {subject}")
            logger.info(f"   Body preview: {text_body[:100] if text_body else html_body[:100]}...")
            return
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = to_email
        
        # Add text and HTML parts
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send via SMTP
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
    
    async def send_email(
        self,
        to_email: EmailStr,
        template_name: str,
        subject: str,
        context: Dict[str, Any],
        send_immediately: bool = False
    ):
        """
        Send email using template (non-blocking)
        
        Args:
            to_email: Recipient email
            template_name: Template name (without extension)
            subject: Email subject
            context: Template context variables
            send_immediately: If True, wait for sending; if False, queue it
        """
        # Add common context
        context.update({
            'app_name': 'outlabsAuth',
            'app_url': settings.APP_URL if hasattr(settings, 'APP_URL') else 'http://localhost:8030',
            'current_year': datetime.now().year,
            'support_email': settings.SMTP_FROM_EMAIL
        })
        
        # Render templates
        try:
            html_template = self.template_env.get_template(f"{template_name}.html")
            html_body = html_template.render(**context)
            
            # Try to render text version if it exists
            text_body = None
            try:
                text_template = self.template_env.get_template(f"{template_name}.txt")
                text_body = text_template.render(**context)
            except:
                # Text template is optional
                pass
            
        except Exception as e:
            logger.error(f"Failed to render email template {template_name}: {e}")
            return
        
        # Email data
        email_data = {
            'to_email': str(to_email),
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }
        
        if send_immediately:
            # Send immediately (still non-blocking)
            await self._send_email_async(
                to_email=str(to_email),
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )
        else:
            # Queue for background processing
            await self.email_queue.put(email_data)
            logger.info(f"Email queued for {to_email} with subject: {subject}")
    
    # System email methods
    
    async def send_welcome_email(self, user: UserModel):
        """Send welcome email to new user"""
        context = {
            'user': user,
            'first_name': user.profile.first_name if user.profile else 'User'
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='welcome',
            subject='Welcome to outlabsAuth',
            context=context
        )
    
    async def send_invitation_email(
        self,
        user: UserModel,
        temp_password: str,
        entity: EntityModel,
        invited_by: UserModel
    ):
        """Send invitation email with temporary password"""
        context = {
            'user': user,
            'temp_password': temp_password,
            'entity': entity,
            'invited_by': invited_by,
            'first_name': user.profile.first_name if user.profile else 'User',
            'entity_name': entity.name,
            'inviter_name': invited_by.profile.full_name if invited_by.profile else invited_by.email
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='invitation',
            subject=f'You have been invited to {entity.name}',
            context=context
        )
    
    async def send_password_reset_email(
        self,
        user: UserModel,
        reset_token: str
    ):
        """Send password reset email"""
        context = {
            'user': user,
            'reset_token': reset_token,
            'first_name': user.profile.first_name if user.profile else 'User',
            'reset_url': f"{context['app_url']}/reset-password?token={reset_token}"
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='password_reset',
            subject='Password Reset Request',
            context=context
        )
    
    async def send_password_changed_email(self, user: UserModel):
        """Send password changed notification"""
        context = {
            'user': user,
            'first_name': user.profile.first_name if user.profile else 'User',
            'change_time': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='password_changed',
            subject='Your Password Has Been Changed',
            context=context
        )
    
    async def send_email_verification(
        self,
        user: UserModel,
        verification_token: str
    ):
        """Send email verification"""
        context = {
            'user': user,
            'verification_token': verification_token,
            'first_name': user.profile.first_name if user.profile else 'User',
            'verify_url': f"{context['app_url']}/verify-email?token={verification_token}"
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='email_verification',
            subject='Verify Your Email Address',
            context=context
        )
    
    async def send_account_locked_email(
        self,
        user: UserModel,
        reason: str = "multiple failed login attempts"
    ):
        """Send account locked notification"""
        context = {
            'user': user,
            'reason': reason,
            'first_name': user.profile.first_name if user.profile else 'User'
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='account_locked',
            subject='Your Account Has Been Locked',
            context=context
        )
    
    async def send_admin_password_reset_email(
        self,
        user: UserModel,
        temp_password: str,
        reset_by: UserModel
    ):
        """Send admin password reset email"""
        context = {
            'user': user,
            'temp_password': temp_password,
            'reset_by': reset_by,
            'first_name': user.profile.first_name if user.profile else 'User',
            'admin_name': reset_by.profile.full_name if reset_by.profile else reset_by.email
        }
        
        await self.send_email(
            to_email=user.email,
            template_name='admin_password_reset',
            subject='Your Password Has Been Reset by an Administrator',
            context=context
        )


# Global email service instance
email_service = EmailService()