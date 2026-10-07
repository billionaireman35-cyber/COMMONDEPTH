"""add post likes

Revision ID: 1f4a8c2d9b71
Revises: 0d7191da1ea6
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f4a8c2d9b71"
down_revision: Union[str, Sequence[str], None] = "0d7191da1ea6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "post_likes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "post_id",
            "user_id",
            name="uq_post_likes_post_user",
        ),
    )

    op.create_index(
        "ix_post_likes_post_created",
        "post_likes",
        ["post_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_post_likes_user_created",
        "post_likes",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_post_likes_user_created",
        table_name="post_likes",
    )
    op.drop_index(
        "ix_post_likes_post_created",
        table_name="post_likes",
    )
    op.drop_table("post_likes")
