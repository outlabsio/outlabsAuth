"""Squashed post-tenant-removal baseline schema.

This baseline replaces historical tenant-era migration chains and creates
the current schema directly from SQLModel metadata.

Revision ID: 20260316_0001
Revises:
Create Date: 2026-03-16 00:01:00.000000+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

from outlabs_auth.models.sql import ALL_MODELS  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "20260316_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind, checkfirst=True)
