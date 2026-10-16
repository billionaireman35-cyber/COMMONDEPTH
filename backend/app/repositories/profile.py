from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.identity import User

from app.models.profile import Profile


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Profile | None:
        statement = select(Profile).where(Profile.user_id == user_id)
        return self.db.scalar(statement)

    def get_by_username(self, username: str) -> Profile | None:
        statement = select(Profile).where(Profile.username == username)
        return self.db.scalar(statement)

    def get_usernames_by_user_ids(
        self,
        user_ids: set[UUID],
    ) -> dict[UUID, str]:
        if not user_ids:
            return {}
        statement = select(Profile).where(Profile.user_id.in_(user_ids))
        profiles = self.db.scalars(statement).all()
        return {profile.user_id: profile.username for profile in profiles}

    def get_author_identities_by_user_ids(
        self,
        user_ids: set[UUID],
    ) -> dict[UUID, tuple[str, str]]:
        if not user_ids:
            return {}

        statement = (
            select(Profile.user_id, Profile.username, User.account_type)
            .join(User, User.id == Profile.user_id)
            .where(Profile.user_id.in_(user_ids))
        )
        rows = self.db.execute(statement).all()
        return {
            user_id: (username, account_type)
            for user_id, username, account_type in rows
        }

    def add(self, profile: Profile) -> Profile:
        self.db.add(profile)
        return profile


    def search_profiles(
        self,
        *,
        query: str,
        viewer_user_id: UUID,
        limit: int,
        cursor_username: str | None = None,
        cursor_profile_id: UUID | None = None,
    ) -> list[Profile]:
        normalized_query = query.lower()

        statement = (
            select(Profile)
            .join(User, User.id == Profile.user_id)
            .where(
                User.status == "active",
                Profile.user_id != viewer_user_id,
                or_(
                    Profile.username.startswith(
                        normalized_query,
                        autoescape=True,
                    ),
                    Profile.display_name.ilike(
                        f"%{_escape_like(query)}%",
                        escape="\\",
                    ),
                ),
            )
            .order_by(
                Profile.username.asc(),
                Profile.id.asc(),
            )
            .limit(limit)
        )

        if cursor_username is not None and cursor_profile_id is not None:
            statement = statement.where(
                or_(
                    Profile.username > cursor_username,
                    (
                        (Profile.username == cursor_username)
                        & (Profile.id > cursor_profile_id)
                    ),
                )
            )

        return list(self.db.scalars(statement).all())
