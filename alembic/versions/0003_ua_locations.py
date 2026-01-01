"""add ua_locations table and hromada column

Revision ID: 0003_ua_locations
Revises: 0002_locations
Create Date: 2026-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_ua_locations"
down_revision = "0002_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("hromada", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_users_region_district_hromada", "users", ["region", "district", "hromada"], unique=False
    )

    op.create_table(
        "ua_locations",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("level1", sa.String(length=32), nullable=True),
        sa.Column("level2", sa.String(length=32), nullable=True),
        sa.Column("level3", sa.String(length=32), nullable=True),
        sa.Column("level4", sa.String(length=32), nullable=True),
        sa.Column("level_extra", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=2), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ua_locations_category"), "ua_locations", ["category"], unique=False)
    op.create_index(op.f("ix_ua_locations_level1"), "ua_locations", ["level1"], unique=False)
    op.create_index(op.f("ix_ua_locations_level2"), "ua_locations", ["level2"], unique=False)
    op.create_index(op.f("ix_ua_locations_level3"), "ua_locations", ["level3"], unique=False)
    op.create_index(op.f("ix_ua_locations_level4"), "ua_locations", ["level4"], unique=False)
    op.create_index(op.f("ix_ua_locations_level_extra"), "ua_locations", ["level_extra"], unique=False)
    op.create_index("ix_ua_locations_l1_l2", "ua_locations", ["level1", "level2"], unique=False)
    op.create_index(
        "ix_ua_locations_l1_l2_l3", "ua_locations", ["level1", "level2", "level3"], unique=False
    )
    op.create_index(
        "ix_ua_locations_l1_l2_l3_cat",
        "ua_locations",
        ["level1", "level2", "level3", "category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_region_district_hromada", table_name="users")
    op.drop_column("users", "hromada")

    op.drop_index("ix_ua_locations_l1_l2_l3_cat", table_name="ua_locations")
    op.drop_index("ix_ua_locations_l1_l2_l3", table_name="ua_locations")
    op.drop_index("ix_ua_locations_l1_l2", table_name="ua_locations")
    op.drop_index(op.f("ix_ua_locations_level_extra"), table_name="ua_locations")
    op.drop_index(op.f("ix_ua_locations_level4"), table_name="ua_locations")
    op.drop_index(op.f("ix_ua_locations_level3"), table_name="ua_locations")
    op.drop_index(op.f("ix_ua_locations_level2"), table_name="ua_locations")
    op.drop_index(op.f("ix_ua_locations_level1"), table_name="ua_locations")
    op.drop_index(op.f("ix_ua_locations_category"), table_name="ua_locations")
    op.drop_table("ua_locations")
