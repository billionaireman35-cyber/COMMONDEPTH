"""Add Spaces and Space memberships."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261014_060000"
down_revision = "20261014_050000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("space_type", sa.String(24), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "visibility",
            sa.String(16),
            server_default="public",
            nullable=False,
        ),
        sa.Column(
            "membership_policy",
            sa.String(16),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "avatar_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "banner_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
            nullable=True,
        ),
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
        sa.UniqueConstraint("slug", name="uq_spaces_slug"),
        sa.CheckConstraint(
            "space_type IN ('creator', 'community', 'organization')",
            name="ck_spaces_type",
        ),
        sa.CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 100",
            name="ck_spaces_name_length",
        ),
        sa.CheckConstraint(
            "length(slug) BETWEEN 3 AND 80",
            name="ck_spaces_slug_length",
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])$'",
            name="ck_spaces_slug_format",
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'private')",
            name="ck_spaces_visibility",
        ),
        sa.CheckConstraint(
            "membership_policy IN ('open', 'approval')",
            name="ck_spaces_membership_policy",
        ),
    )
    op.create_index(
        "ix_spaces_owner_created",
        "spaces",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_spaces_type_visibility",
        "spaces",
        ["space_type", "visibility"],
    )

    op.create_table(
        "space_memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(24),
            server_default="member",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default="active",
            nullable=False,
        ),
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
            "space_id",
            "user_id",
            name="uq_space_memberships_space_user",
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'moderator', 'member')",
            name="ck_space_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'pending', 'removed')",
            name="ck_space_memberships_status",
        ),
    )
    op.create_index(
        "ix_space_memberships_user_status",
        "space_memberships",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_space_memberships_space_status",
        "space_memberships",
        ["space_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_space_memberships_space_status",
        table_name="space_memberships",
    )
    op.drop_index(
        "ix_space_memberships_user_status",
        table_name="space_memberships",
    )
    op.drop_table("space_memberships")

    op.drop_index("ix_spaces_type_visibility", table_name="spaces")
    op.drop_index("ix_spaces_owner_created", table_name="spaces")
    op.drop_table("spaces")
