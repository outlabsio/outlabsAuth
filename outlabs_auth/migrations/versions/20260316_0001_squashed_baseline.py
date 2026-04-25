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

_TABLES_OWNED_BY_LATER_MIGRATIONS = frozenset({"auth_challenges"})


def _baseline_tables():
    return [table for table in SQLModel.metadata.sorted_tables if table.name not in _TABLES_OWNED_BY_LATER_MIGRATIONS]


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind, tables=_baseline_tables(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind, checkfirst=True)
