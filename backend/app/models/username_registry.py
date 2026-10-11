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


class UsernameRegistry(Base):
    """Global registry of claimed and temporarily reserved usernames."""

    __tablename__ = "username_registry"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    username: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="claimed",
        server_default="claimed",
    )

    owner_type: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    profile_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "profiles.id",
            ondelete="RESTRICT",
            name="fk_username_registry_profile_id_profiles",
        ),
        nullable=True,
    )

    # Space ownership is staged until the Space model and table exist.
    space_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    reserved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
            "username",
            name="uq_username_registry_username",
        ),
        UniqueConstraint(
            "profile_id",
            name="uq_username_registry_profile",
        ),
        UniqueConstraint(
            "space_id",
            name="uq_username_registry_space",
        ),
        CheckConstraint(
            "username ~ '^[a-z][a-z0-9_]{1,29}$'",
            name="ck_username_registry_username_format",
        ),
        CheckConstraint(
            "status IN ('claimed', 'reserved')",
            name="ck_username_registry_status",
        ),
        CheckConstraint(
            "("
            "status = 'claimed' "
            "AND expires_at IS NULL "
            "AND reserved_at IS NULL "
            "AND ("
            "  (owner_type = 'profile' AND profile_id IS NOT NULL "
            "   AND space_id IS NULL) "
            "  OR "
            "  (owner_type = 'space' AND profile_id IS NULL "
            "   AND space_id IS NOT NULL)"
            ")"
            ") OR ("
            "status = 'reserved' "
            "AND owner_type IS NULL "
            "AND profile_id IS NULL "
            "AND space_id IS NULL "
            "AND reserved_at IS NOT NULL "
            "AND expires_at IS NOT NULL "
            "AND expires_at > reserved_at"
            ")",
            name="ck_username_registry_state",
        ),
        Index(
            "ix_username_registry_status_expiry",
            "status",
            "expires_at",
        ),
    )
