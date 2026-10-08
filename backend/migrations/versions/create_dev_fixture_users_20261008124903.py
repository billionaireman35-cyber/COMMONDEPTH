"""create development fixture user registry

Revision ID: create_dev_fixture_users
Revises: fda1ba1ddde6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "create_dev_fixture_users"
down_revision = "fda1ba1ddde6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "development_fixture_users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "fixture_name",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_development_fixture_users_user_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            name="pk_development_fixture_users",
        ),
    )

    op.create_index(
        "ix_development_fixture_users_fixture_name",
        "development_fixture_users",
        ["fixture_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_development_fixture_users_fixture_name",
        table_name="development_fixture_users",
    )
    op.drop_table("development_fixture_users")
