from uuid import UUID

from sqlalchemy import case, exists, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.identity import User
from app.models.profile import Profile
from app.models.social import Follow
from app.services.profile import normalize_username


def _configured_usernames() -> list[str]:
    raw = get_settings().onboarding_curated_usernames

    usernames: list[str] = []
    seen: set[str] = set()

    for value in raw.split(","):
        value = value.strip()
        if not value:
            continue

        username = normalize_username(value)
        if username not in seen:
            usernames.append(username)
            seen.add(username)

    return usernames


def get_curated_follow_suggestions(
    db: Session,
    *,
    viewer_user_id: UUID,
) -> list[Profile]:
    usernames = _configured_usernames()

    if not usernames:
        return []

    ordering = case(
        {username: index for index, username in enumerate(usernames)},
        value=Profile.username,
    )

    already_followed = exists(
        select(Follow.id).where(
            Follow.follower_id == viewer_user_id,
            Follow.following_id == Profile.user_id,
        )
    )

    statement = (
        select(Profile)
        .join(User, User.id == Profile.user_id)
        .where(
            User.status == "active",
            Profile.user_id != viewer_user_id,
            Profile.username.in_(usernames),
            ~already_followed,
        )
        .order_by(ordering, Profile.id.asc())
    )

    return list(db.scalars(statement).all())
