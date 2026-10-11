"""Add online nullable account proof-generation and protection columns.

Revision ID: 20261011_0026
Revises: 20260802_0025
"""

import sqlalchemy as sa
from alembic import context, op

revision = "20261011_0026"
down_revision = "20260802_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users", schema=schema)}
    for name, kind in (("session_security_epoch", sa.BigInteger()), ("platform_protected", sa.Boolean())):
        if name not in columns:
            op.add_column("users", sa.Column(name, kind, nullable=True), schema=schema)


def downgrade() -> None:
    # Removing the durable barrier could revive old credentials. A downgrade
    # requires an explicit anti-rewind recovery procedure, not a routine drop.
    raise RuntimeError("Account security state cannot be downgraded without a coordinated credential reset")
