from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FollowRequest(Base):
    __tablename__ = "follow_requests"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    requester_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    target_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
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
            "requester_id",
            "target_id",
            name="uq_follow_requests_requester_target",
        ),
        Index(
            "ix_follow_requests_target_status_created",
            "target_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_follow_requests_requester_status_created",
            "requester_id",
            "status",
            "created_at",
        ),
        CheckConstraint(
            "requester_id <> target_id",
            name="ck_follow_requests_no_self_request",
        ),
        CheckConstraint(
            "status IN ('pending', 'rejected')",
            name="ck_follow_requests_status",
        ),
    )


class Follow(Base):
    __tablename__ = "follows"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    follower_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    following_id: Mapped[UUID] = mapped_column(
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
            "follower_id",
            "following_id",
            name="uq_follows_follower_following",
        ),
        Index(
            "ix_follows_follower_created",
            "follower_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_follows_following_created",
            "following_id",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "follower_id <> following_id",
            name="ck_follows_no_self_follow",
        ),
    )
