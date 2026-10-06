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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Reel(Base):
    __tablename__ = "reels"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    author_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    video_asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    cover_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )

    caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    visibility: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="public",
        server_default="public",
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
        Index("ix_reels_author_created", "author_id", "created_at", "id"),
        Index("ix_reels_created", "created_at", "id"),
        CheckConstraint(
            "visibility IN ('public', 'followers')",
            name="ck_reels_visibility",
        ),
        CheckConstraint(
            "caption IS NULL OR length(caption) <= 5000",
            name="ck_reels_caption_length",
        ),
    )


class ReelLike(Base):
    __tablename__ = "reel_likes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    reel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reels.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "reel_id",
            "user_id",
            name="uq_reel_likes_reel_user",
        ),
        Index(
            "ix_reel_likes_reel_created",
            "reel_id",
            "created_at",
        ),
        Index(
            "ix_reel_likes_user_created",
            "user_id",
            "created_at",
        ),
    )


class ReelComment(Base):
    __tablename__ = "reel_comments"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    reel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reels.id", ondelete="RESTRICT"),
        nullable=False,
    )

    author_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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
            "ix_reel_comments_reel_created",
            "reel_id",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "length(content) > 0",
            name="ck_reel_comments_content_nonempty",
        ),
        CheckConstraint(
            "length(content) <= 5000",
            name="ck_reel_comments_content_length",
        ),
    )


class ReelShare(Base):
    __tablename__ = "reel_shares"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    reel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reels.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_reel_shares_reel_created",
            "reel_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_reel_shares_user_created",
            "user_id",
            "created_at",
        ),
    )


class ReelSave(Base):
    __tablename__ = "reel_saves"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    reel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reels.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "reel_id",
            "user_id",
            name="uq_reel_saves_reel_user",
        ),
        Index(
            "ix_reel_saves_reel_created",
            "reel_id",
            "created_at",
        ),
        Index(
            "ix_reel_saves_user_created",
            "user_id",
            "created_at",
        ),
    )


class ReelAudio(Base):
    __tablename__ = "reel_audio"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    reel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reels.id", ondelete="RESTRICT"),
        nullable=False,
    )

    audio_asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    artist_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    start_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "reel_id",
            name="uq_reel_audio_reel",
        ),
        Index(
            "ix_reel_audio_asset_id",
            "audio_asset_id",
        ),
        CheckConstraint(
            "start_ms IS NULL OR start_ms >= 0",
            name="ck_reel_audio_start_nonnegative",
        ),
        CheckConstraint(
            "end_ms IS NULL OR end_ms > 0",
            name="ck_reel_audio_end_positive",
        ),
        CheckConstraint(
            "start_ms IS NULL OR end_ms IS NULL OR end_ms > start_ms",
            name="ck_reel_audio_range",
        ),
    )
