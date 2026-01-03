"""drop settlement_type column

Revision ID: 0005_drop_settlement_type
Revises: 0004_hromada_scope
Create Date: 2026-01-02 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_drop_settlement_type"
down_revision = "0004_hromada_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_settlement_type")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("settlement_type")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("settlement_type", sa.String(length=16), nullable=False, server_default="city")
        )

    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE users ADD CONSTRAINT ck_users_settlement_type "
            "CHECK (settlement_type IN ('city','village'))"
        )
