from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.repositories.profile import ProfileRepository


class ProfileVerificationError(Exception):
    """Base class for profile verification service errors."""


class ProfileNotFoundForVerificationError(ProfileVerificationError):
    """Raised when the profile being verified does not exist."""


def verify_profile(
    db: Session,
    *,
    user_id: UUID,
) -> Profile:
    """Mark an existing profile as verified through a trusted internal path."""
    repository = ProfileRepository(db)
    profile = repository.get_by_user_id(user_id)

    if profile is None:
        raise ProfileNotFoundForVerificationError(
            "Profile not found."
        )

    if profile.verified_at is None:
        profile.verified_at = datetime.now(timezone.utc)
        db.flush()
        db.commit()

    return profile
