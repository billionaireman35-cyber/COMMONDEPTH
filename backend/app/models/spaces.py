from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Space(Base):
    __tablename__ = "spaces"

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
    space_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(80),
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
    membership_policy: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="open",
        server_default="open",
    )
    avatar_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    banner_asset_id: Mapped[UUID | None] = mapped_column(
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

    __table_args__ = (
        UniqueConstraint("slug", name="uq_spaces_slug"),
        CheckConstraint(
            "space_type IN ('creator', 'community', 'organization')",
            name="ck_spaces_type",
        ),
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 100",
            name="ck_spaces_name_length",
        ),
        CheckConstraint(
            "length(slug) BETWEEN 3 AND 80",
            name="ck_spaces_slug_length",
        ),
        CheckConstraint(
            "slug ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])$'",
            name="ck_spaces_slug_format",
        ),
        CheckConstraint(
            "visibility IN ('public', 'private')",
            name="ck_spaces_visibility",
        ),
        CheckConstraint(
            "membership_policy IN ('open', 'approval')",
            name="ck_spaces_membership_policy",
        ),
        Index("ix_spaces_owner_created", "owner_id", "created_at"),
        Index("ix_spaces_type_visibility", "space_type", "visibility"),
    )


class SpaceMembership(Base):
    __tablename__ = "space_memberships"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    space_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="member",
        server_default="member",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
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
            "space_id",
            "user_id",
            name="uq_space_memberships_space_user",
        ),
        CheckConstraint(
            "role IN ('owner', 'admin', 'moderator', 'member')",
            name="ck_space_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active', 'pending', 'removed')",
            name="ck_space_memberships_status",
        ),
        Index(
            "ix_space_memberships_user_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_space_memberships_space_status",
            "space_id",
            "status",
        ),
    )
