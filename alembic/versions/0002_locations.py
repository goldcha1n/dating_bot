"""add location fields

Revision ID: 0002_locations
Revises: 0001_initial
Create Date: 2025-12-31 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_locations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("region", sa.String(length=128), nullable=False, server_default="Kyiv"))
    op.add_column("users", sa.Column("district", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("settlement", sa.String(length=128), nullable=False, server_default="Kyiv"))
    op.add_column(
        "users",
        sa.Column("settlement_type", sa.String(length=16), nullable=False, server_default="city"),
    )
    op.add_column(
        "users",
        sa.Column("search_scope", sa.String(length=16), nullable=False, server_default="region"),
    )

    op.create_index("ix_users_region", "users", ["region"], unique=False)
    op.create_index("ix_users_region_district", "users", ["region", "district"], unique=False)
    op.create_index(
        "ix_users_region_district_settlement",
        "users",
        ["region", "district", "settlement"],
        unique=False,
    )

    op.execute(
        """
        UPDATE users
        SET
            region = COALESCE(NULLIF(city, ''), 'Kyiv'),
            district = NULL,
            settlement = COALESCE(NULLIF(city, ''), 'Kyiv'),
            settlement_type = 'city',
            search_scope = CASE WHEN search_global THEN 'country' ELSE 'settlement' END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_users_region_district_settlement", table_name="users")
    op.drop_index("ix_users_region_district", table_name="users")
    op.drop_index("ix_users_region", table_name="users")
    op.drop_column("users", "search_scope")
    op.drop_column("users", "settlement_type")
    op.drop_column("users", "settlement")
    op.drop_column("users", "district")
    op.drop_column("users", "region")
