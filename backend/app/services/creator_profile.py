from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.creator_profile import CreatorProfile
from app.models.identity import User
from app.models.profile import Profile


class CreatorProfileError(Exception):
    """Base error for Creator Profile operations."""


class CreatorAccountRequiredError(CreatorProfileError):
    """The authenticated account is not a Creator account."""


class CreatorBaseProfileRequiredError(CreatorProfileError):
    """The Creator must create their shared Profile first."""


class CreatorProfileNotFoundError(CreatorProfileError):
    """No Creator Profile exists for this account."""


class CreatorProfileValidationError(CreatorProfileError):
    """Creator Profile input is invalid."""


def _require_creator(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)

    if (
        user is None
        or user.status != "active"
        or user.deleted_at is not None
    ):
        raise CreatorAccountRequiredError(
            "An active Creator account is required."
        )

    if user.account_type != "creator":
        raise CreatorAccountRequiredError(
            "Only Creator accounts can manage Creator Profiles."
        )

    return user


def get_my_creator_profile(
    db: Session,
    *,
    user_id: UUID,
) -> CreatorProfile:
    _require_creator(db, user_id)

    creator_profile = (
        db.query(CreatorProfile)
        .filter(CreatorProfile.user_id == user_id)
        .one_or_none()
    )

    if creator_profile is None:
        raise CreatorProfileNotFoundError(
            "Creator Profile not found."
        )

    return creator_profile


def save_creator_profile(
    db: Session,
    *,
    user_id: UUID,
    profession: str,
    niche: str,
    content_types: list[str],
    introduction: str,
) -> CreatorProfile:
    _require_creator(db, user_id)

    base_profile = (
        db.query(Profile)
        .filter(Profile.user_id == user_id)
        .one_or_none()
    )
    if base_profile is None:
        raise CreatorBaseProfileRequiredError(
            "Create your shared Profile before saving Creator details."
        )

    profession = profession.strip()
    niche = niche.strip()
    introduction = introduction.strip()
    content_types = list(dict.fromkeys(
        item.strip().lower() for item in content_types
    ))

    if not profession or len(profession) > 120:
        raise CreatorProfileValidationError(
            "Profession must be between 1 and 120 characters."
        )
    if not niche or len(niche) > 120:
        raise CreatorProfileValidationError(
            "Niche must be between 1 and 120 characters."
        )
    if not introduction or len(introduction) > 3000:
        raise CreatorProfileValidationError(
            "Introduction must be between 1 and 3000 characters."
        )
    if not content_types or len(content_types) > 12:
        raise CreatorProfileValidationError(
            "Choose between 1 and 12 content types."
        )

    try:
        creator_profile = (
            db.query(CreatorProfile)
            .filter(CreatorProfile.user_id == user_id)
            .one_or_none()
        )

        if creator_profile is None:
            creator_profile = CreatorProfile(
                user_id=user_id,
                profession=profession,
                niche=niche,
                content_types=content_types,
                introduction=introduction,
            )
            db.add(creator_profile)
        else:
            creator_profile.profession = profession
            creator_profile.niche = niche
            creator_profile.content_types = content_types
            creator_profile.introduction = introduction

        db.commit()
        db.refresh(creator_profile)
        return creator_profile

    except IntegrityError:
        db.rollback()
        raise CreatorProfileError(
            "Creator Profile could not be saved."
        ) from None
    except Exception:
        db.rollback()
        raise
