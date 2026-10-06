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


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    host_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    visibility: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="public",
        server_default="public",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="scheduled",
        server_default="scheduled",
    )

    streaming_provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    provider_stream_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_playback_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    viewer_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    replay_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
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

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_live_sessions_host_created",
            "host_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_live_sessions_status_scheduled",
            "status",
            "scheduled_at",
        ),
        Index(
            "ix_live_sessions_status_started",
            "status",
            "started_at",
        ),
        CheckConstraint(
            "visibility IN ('public', 'followers')",
            name="ck_live_sessions_visibility",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'ended', 'cancelled', 'failed')",
            name="ck_live_sessions_status",
        ),
        CheckConstraint(
            "length(title) > 0",
            name="ck_live_sessions_title_nonempty",
        ),
        CheckConstraint(
            "length(title) <= 255",
            name="ck_live_sessions_title_length",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 5000",
            name="ck_live_sessions_description_length",
        ),
        CheckConstraint(
            "length(streaming_provider) > 0",
            name="ck_live_sessions_provider_nonempty",
        ),
        CheckConstraint(
            "viewer_count >= 0",
            name="ck_live_sessions_viewer_count_nonnegative",
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_live_sessions_end_after_start",
        ),
    )
