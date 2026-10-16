from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    organization_space_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    primary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    headline: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    destination_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    target_topics: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    budget_minor_units: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    daily_budget_minor_units: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
        server_default="NGN",
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_content_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 120",
            name="ck_ad_campaigns_name_length",
        ),
        CheckConstraint(
            "status IN "
            "('draft', 'submitted', 'under_review', 'approved', "
            "'scheduled', 'active', 'completed', 'rejected', "
            "'suspended', 'cancelled')",
            name="ck_ad_campaigns_status",
        ),
        CheckConstraint(
            "length(trim(primary_text)) BETWEEN 1 AND 5000",
            name="ck_ad_campaigns_primary_text_length",
        ),
        CheckConstraint(
            "length(trim(destination_url)) BETWEEN 1 AND 2048",
            name="ck_ad_campaigns_destination_length",
        ),
        CheckConstraint(
            "budget_minor_units > 0",
            name="ck_ad_campaigns_budget_positive",
        ),
        CheckConstraint(
            "daily_budget_minor_units IS NULL "
            "OR daily_budget_minor_units > 0",
            name="ck_ad_campaigns_daily_budget_positive",
        ),
        CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_ad_campaigns_currency_format",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_ad_campaigns_schedule_order",
        ),
        Index(
            "ix_ad_campaigns_space_created",
            "organization_space_id",
            "created_at",
        ),
        Index(
            "ix_ad_campaigns_status_schedule",
            "status",
            "starts_at",
            "ends_at",
        ),
    )


class AdReviewEvent(Base):
    __tablename__ = "ad_review_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ad_campaigns.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    previous_status: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )
    resulting_status: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN "
            "('created', 'edited', 'submitted', 'review_started', "
            "'approved', 'rejected', 'scheduled', 'activated', "
            "'completed', 'suspended', 'resumed', 'cancelled')",
            name="ck_ad_review_events_type",
        ),
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN "
            "('draft', 'submitted', 'under_review', 'approved', "
            "'scheduled', 'active', 'completed', 'rejected', "
            "'suspended', 'cancelled')",
            name="ck_ad_review_events_previous_status",
        ),
        CheckConstraint(
            "resulting_status IS NULL OR resulting_status IN "
            "('draft', 'submitted', 'under_review', 'approved', "
            "'scheduled', 'active', 'completed', 'rejected', "
            "'suspended', 'cancelled')",
            name="ck_ad_review_events_resulting_status",
        ),
        Index(
            "ix_ad_review_events_campaign_created",
            "campaign_id",
            "created_at",
        ),
        Index(
            "ix_ad_review_events_actor_created",
            "actor_user_id",
            "created_at",
        ),
    )
