"""
Base document model for all Beanie ODM documents
"""
from datetime import datetime, timezone
from typing import Optional
from beanie import Document
from pydantic import Field


class BaseDocument(Document):
    """
    Base document class for all Beanie models in OutlabsAuth.

    Provides common fields and utilities for all models.
    """

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional tenant isolation (for multi-tenant mode)
    tenant_id: Optional[str] = None

    def save(self, *args, **kwargs):
        """Override save to update timestamp"""
        self.updated_at = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)

    class Settings:
        """Beanie document settings"""
        # This will be overridden in subclasses
        use_state_management = True
        validate_on_save = True
