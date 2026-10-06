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


class Story(Base):
    __tablename__ = "stories"

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

    visibility: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="public",
        server_default="public",
    )

    text_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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
            "ix_stories_author_created",
            "author_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_stories_expires_at",
            "expires_at",
        ),
        CheckConstraint(
            "visibility IN ('public', 'followers')",
            name="ck_stories_visibility",
        ),
        CheckConstraint(
            "text_content IS NULL OR length(text_content) <= 5000",
            name="ck_stories_text_content_length",
        ),
    )


class StoryMedia(Base):
    __tablename__ = "story_media"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    story_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="RESTRICT"),
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
            "story_id",
            "media_asset_id",
            name="uq_story_media_story_asset",
        ),
        UniqueConstraint(
            "story_id",
            "position",
            name="uq_story_media_story_position",
        ),
        Index(
            "ix_story_media_story_position",
            "story_id",
            "position",
        ),
        Index(
            "ix_story_media_asset_id",
            "media_asset_id",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_story_media_position_nonnegative",
        ),
    )


class StoryView(Base):
    __tablename__ = "story_views"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    story_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    viewer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "story_id",
            "viewer_id",
            name="uq_story_views_story_viewer",
        ),
        Index(
            "ix_story_views_story_viewer",
            "story_id",
            "viewer_id",
        ),
        Index(
            "ix_story_views_viewer_viewed",
            "viewer_id",
            "viewed_at",
        ),
    )


class StoryReply(Base):
    __tablename__ = "story_replies"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    story_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="RESTRICT"),
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
            "ix_story_replies_story_created",
            "story_id",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "length(content) > 0",
            name="ck_story_replies_content_nonempty",
        ),
        CheckConstraint(
            "length(content) <= 5000",
            name="ck_story_replies_content_length",
        ),
    )


class StoryReaction(Base):
    __tablename__ = "story_reactions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    story_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    reaction_type: Mapped[str] = mapped_column(
        String(32),
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

    __table_args__ = (
        UniqueConstraint(
            "story_id",
            "user_id",
            name="uq_story_reactions_story_user",
        ),
        Index(
            "ix_story_reactions_story_created",
            "story_id",
            "created_at",
        ),
        CheckConstraint(
            "length(reaction_type) > 0",
            name="ck_story_reactions_type_nonempty",
        ),
    )
