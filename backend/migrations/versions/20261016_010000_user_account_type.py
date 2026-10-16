"""Add persistent account types to users."""

from alembic import op
import sqlalchemy as sa


revision = "20261016_010000"
down_revision = "20261014_060000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "account_type",
            sa.String(length=24),
            server_default="individual",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_account_type",
        "users",
        "account_type IN ('individual', 'creator', 'organization')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_account_type",
        "users",
        type_="check",
    )
    op.drop_column("users", "account_type")
