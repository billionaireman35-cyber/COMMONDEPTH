from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    owner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    media_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    storage_provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    thumbnail_storage_key: Mapped[str | None] = mapped_column(
        String(1024),
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
            "ix_media_assets_owner_created",
            "owner_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_media_assets_status_created",
            "status",
            "created_at",
        ),
        UniqueConstraint(
            "storage_provider",
            "storage_key",
            name="uq_media_assets_storage_location",
        ),
        CheckConstraint(
            "media_type IN ('image', 'video', 'audio')",
            name="ck_media_assets_media_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed', 'deleted')",
            name="ck_media_assets_status",
        ),
        CheckConstraint(
            "file_size > 0",
            name="ck_media_assets_file_size_positive",
        ),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="ck_media_assets_width_positive",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="ck_media_assets_height_positive",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms > 0",
            name="ck_media_assets_duration_positive",
        ),
    )


class MediaUpload(Base):
    __tablename__ = "media_uploads"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    media_asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        String(512),
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
        UniqueConstraint(
            "media_asset_id",
            name="uq_media_uploads_media_asset_id",
        ),
        Index(
            "ix_media_uploads_status_expires_at",
            "status",
            "expires_at",
        ),
        CheckConstraint(
            "status IN ('pending', 'uploading', 'completed', 'failed', 'expired')",
            name="ck_media_uploads_status",
        ),
    )


class PostMedia(Base):
    __tablename__ = "post_media"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    post_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    media_asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "media_asset_id",
            name="uq_post_media_post_asset",
        ),
        UniqueConstraint(
            "post_id",
            "position",
            name="uq_post_media_post_position",
        ),
        Index(
            "ix_post_media_post_position",
            "post_id",
            "position",
        ),
        Index(
            "ix_post_media_asset_id",
            "media_asset_id",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_post_media_position_nonnegative",
        ),
    )
