"""Add persistent Creator Profile details."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261016_030000"
down_revision = "20261016_020000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("profession", sa.String(120), nullable=False),
        sa.Column("niche", sa.String(120), nullable=False),
        sa.Column(
            "content_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("introduction", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            name="uq_creator_profiles_user_id",
        ),
        sa.CheckConstraint(
            "length(trim(profession)) BETWEEN 1 AND 120",
            name="ck_creator_profiles_profession_length",
        ),
        sa.CheckConstraint(
            "length(trim(niche)) BETWEEN 1 AND 120",
            name="ck_creator_profiles_niche_length",
        ),
        sa.CheckConstraint(
            "length(trim(introduction)) BETWEEN 1 AND 3000",
            name="ck_creator_profiles_introduction_length",
        ),
    )
    op.create_index(
        "ix_creator_profiles_niche",
        "creator_profiles",
        ["niche"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_creator_profiles_niche",
        table_name="creator_profiles",
    )
    op.drop_table("creator_profiles")
