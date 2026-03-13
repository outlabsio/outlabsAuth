"""Add invite fields to users table

Adds invite_token, invite_token_expires, and invited_by_id columns
to support the user invitation system.

Revision ID: add_invite_fields
Revises: add_entity_local_roles
Create Date: 2026-03-13 00:01:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_invite_fields"
down_revision: Union[str, None] = "add_entity_local_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("invite_token", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("invite_token_expires", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "invited_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "invited_by_id")
    op.drop_column("users", "invite_token_expires")
    op.drop_column("users", "invite_token")
