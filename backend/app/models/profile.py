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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    avatar: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    banner: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    biography: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(160),
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

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_profiles_user_id",
        ),
        UniqueConstraint(
            "username",
            name="uq_profiles_username",
        ),
        Index(
            "ix_profiles_username",
            "username",
        ),
        CheckConstraint(
            "visibility IN ('public', 'private')",
            name="ck_profiles_visibility",
        ),
    )
