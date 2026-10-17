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
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"

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
    profession: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    niche: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    content_types: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    introduction: Mapped[str] = mapped_column(
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

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_creator_profiles_user_id",
        ),
        CheckConstraint(
            "length(trim(profession)) BETWEEN 1 AND 120",
            name="ck_creator_profiles_profession_length",
        ),
        CheckConstraint(
            "length(trim(niche)) BETWEEN 1 AND 120",
            name="ck_creator_profiles_niche_length",
        ),
        CheckConstraint(
            "length(trim(introduction)) BETWEEN 1 AND 3000",
            name="ck_creator_profiles_introduction_length",
        ),
        Index(
            "ix_creator_profiles_niche",
            "niche",
        ),
    )
