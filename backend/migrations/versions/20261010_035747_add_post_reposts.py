"""Add persistent post reposts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_post_reposts"
down_revision = "create_dev_fixture_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_reposts",
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
            name="fk_post_reposts_post_id_posts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_post_reposts_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_post_reposts",
        ),
        sa.UniqueConstraint(
            "post_id",
            "user_id",
            name="uq_post_reposts_post_user",
        ),
    )

    op.create_index(
        "ix_post_reposts_post_created",
        "post_reposts",
        ["post_id", "created_at"],
    )
    op.create_index(
        "ix_post_reposts_user_created",
        "post_reposts",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_post_reposts_user_created",
        table_name="post_reposts",
    )
    op.drop_index(
        "ix_post_reposts_post_created",
        table_name="post_reposts",
    )
    op.drop_table("post_reposts")
