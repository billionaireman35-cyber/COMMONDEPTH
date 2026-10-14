"""Add one-to-one direct messaging."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261014_050000"
down_revision = "20261012_040000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "participant_one_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "participant_two_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
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
            "participant_one_id",
            "participant_two_id",
            name="uq_conversations_participant_pair",
        ),
        sa.CheckConstraint(
            "participant_one_id < participant_two_id",
            name="ck_conversations_canonical_pair",
        ),
    )
    op.create_index(
        "ix_conversations_participant_one_updated",
        "conversations",
        ["participant_one_id", "updated_at"],
    )
    op.create_index(
        "ix_conversations_participant_two_updated",
        "conversations",
        ["participant_two_id", "updated_at"],
    )

    op.create_table(
        "direct_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(body) BETWEEN 1 AND 5000",
            name="ck_direct_messages_body_length",
        ),
    )
    op.create_index(
        "ix_direct_messages_conversation_created",
        "direct_messages",
        ["conversation_id", "created_at", "id"],
    )
    op.create_index(
        "ix_direct_messages_sender_created",
        "direct_messages",
        ["sender_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_direct_messages_sender_created",
        table_name="direct_messages",
    )
    op.drop_index(
        "ix_direct_messages_conversation_created",
        table_name="direct_messages",
    )
    op.drop_table("direct_messages")
    op.drop_index(
        "ix_conversations_participant_two_updated",
        table_name="conversations",
    )
    op.drop_index(
        "ix_conversations_participant_one_updated",
        table_name="conversations",
    )
    op.drop_table("conversations")
