"""Add private post bookmarks."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_post_bookmarks"
down_revision = "add_post_reposts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_bookmarks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_post_bookmarks_post_id_posts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_post_bookmarks_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_post_bookmarks",
        ),
        sa.UniqueConstraint(
            "post_id",
            "user_id",
            name="uq_post_bookmarks_post_user",
        ),
    )

    op.create_index(
        "ix_post_bookmarks_post_created",
        "post_bookmarks",
        ["post_id", "created_at"],
    )
    op.create_index(
        "ix_post_bookmarks_user_created",
        "post_bookmarks",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_post_bookmarks_user_created",
        table_name="post_bookmarks",
    )
    op.drop_index(
        "ix_post_bookmarks_post_created",
        table_name="post_bookmarks",
    )
    op.drop_table("post_bookmarks")
