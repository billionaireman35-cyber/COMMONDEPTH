"""Add uploaded avatar and banner asset references to profiles."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261012_040000"
down_revision = "20261011_040000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("avatar_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("banner_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_profiles_avatar_asset_id_media_assets",
        "profiles",
        "media_assets",
        ["avatar_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_profiles_banner_asset_id_media_assets",
        "profiles",
        "media_assets",
        ["banner_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_profiles_avatar_asset_id",
        "profiles",
        ["avatar_asset_id"],
    )
    op.create_index(
        "ix_profiles_banner_asset_id",
        "profiles",
        ["banner_asset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_banner_asset_id", table_name="profiles")
    op.drop_index("ix_profiles_avatar_asset_id", table_name="profiles")
    op.drop_constraint(
        "fk_profiles_banner_asset_id_media_assets",
        "profiles",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_profiles_avatar_asset_id_media_assets",
        "profiles",
        type_="foreignkey",
    )
    op.drop_column("profiles", "banner_asset_id")
    op.drop_column("profiles", "avatar_asset_id")
