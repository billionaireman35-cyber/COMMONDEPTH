"""Add advertising campaigns and review history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261016_020000"
down_revision = "20261016_010000"
branch_labels = None
depends_on = None


CAMPAIGN_STATUSES = (
    "'draft', 'submitted', 'under_review', 'approved', "
    "'scheduled', 'active', 'completed', 'rejected', "
    "'suspended', 'cancelled'"
)


def upgrade() -> None:
    op.create_table(
        "ad_campaigns",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "organization_space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("primary_text", sa.Text(), nullable=False),
        sa.Column("headline", sa.String(160), nullable=True),
        sa.Column("destination_url", sa.String(2048), nullable=False),
        sa.Column(
            "target_topics",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column("budget_minor_units", sa.Integer(), nullable=False),
        sa.Column(
            "daily_budget_minor_units",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "currency",
            sa.String(3),
            server_default="NGN",
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "approved_content_fingerprint",
            sa.String(64),
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
        sa.CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 120",
            name="ck_ad_campaigns_name_length",
        ),
        sa.CheckConstraint(
            f"status IN ({CAMPAIGN_STATUSES})",
            name="ck_ad_campaigns_status",
        ),
        sa.CheckConstraint(
            "length(trim(primary_text)) BETWEEN 1 AND 5000",
            name="ck_ad_campaigns_primary_text_length",
        ),
        sa.CheckConstraint(
            "length(trim(destination_url)) BETWEEN 1 AND 2048",
            name="ck_ad_campaigns_destination_length",
        ),
        sa.CheckConstraint(
            "budget_minor_units > 0",
            name="ck_ad_campaigns_budget_positive",
        ),
        sa.CheckConstraint(
            "daily_budget_minor_units IS NULL "
            "OR daily_budget_minor_units > 0",
            name="ck_ad_campaigns_daily_budget_positive",
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_ad_campaigns_currency_format",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_ad_campaigns_schedule_order",
        ),
    )
    op.create_index(
        "ix_ad_campaigns_space_created",
        "ad_campaigns",
        ["organization_space_id", "created_at"],
    )
    op.create_index(
        "ix_ad_campaigns_status_schedule",
        "ad_campaigns",
        ["status", "starts_at", "ends_at"],
    )

    op.create_table(
        "ad_review_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ad_campaigns.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("previous_status", sa.String(24), nullable=True),
        sa.Column("resulting_status", sa.String(24), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN "
            "('created', 'edited', 'submitted', 'review_started', "
            "'approved', 'rejected', 'scheduled', 'activated', "
            "'completed', 'suspended', 'resumed', 'cancelled')",
            name="ck_ad_review_events_type",
        ),
        sa.CheckConstraint(
            f"previous_status IS NULL OR previous_status IN "
            f"({CAMPAIGN_STATUSES})",
            name="ck_ad_review_events_previous_status",
        ),
        sa.CheckConstraint(
            f"resulting_status IS NULL OR resulting_status IN "
            f"({CAMPAIGN_STATUSES})",
            name="ck_ad_review_events_resulting_status",
        ),
    )
    op.create_index(
        "ix_ad_review_events_campaign_created",
        "ad_review_events",
        ["campaign_id", "created_at"],
    )
    op.create_index(
        "ix_ad_review_events_actor_created",
        "ad_review_events",
        ["actor_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ad_review_events_actor_created",
        table_name="ad_review_events",
    )
    op.drop_index(
        "ix_ad_review_events_campaign_created",
        table_name="ad_review_events",
    )
    op.drop_table("ad_review_events")

    op.drop_index(
        "ix_ad_campaigns_status_schedule",
        table_name="ad_campaigns",
    )
    op.drop_index(
        "ix_ad_campaigns_space_created",
        table_name="ad_campaigns",
    )
    op.drop_table("ad_campaigns")
