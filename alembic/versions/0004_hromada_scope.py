"""allow hromada search scope

Revision ID: 0004_hromada_scope
Revises: 0003_ua_locations
Create Date: 2026-01-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_hromada_scope"
down_revision = "0003_ua_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_users_search_scope", "users", type_="check")
        op.create_check_constraint(
            "ck_users_search_scope",
            "users",
            "search_scope IN ('settlement','hromada','district','region','country')",
        )
    else:
        # For SQLite and other dialects, keep existing data; recreate table manually if needed.
        pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_users_search_scope", "users", type_="check")
        op.create_check_constraint(
            "ck_users_search_scope",
            "users",
            "search_scope IN ('settlement','district','region','country')",
        )
    else:
        pass

