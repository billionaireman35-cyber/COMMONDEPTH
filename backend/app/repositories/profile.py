from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import Profile


class ProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Profile | None:
        statement = select(Profile).where(Profile.user_id == user_id)
        return self.db.scalar(statement)

    def get_by_username(self, username: str) -> Profile | None:
        statement = select(Profile).where(Profile.username == username)
        return self.db.scalar(statement)

    def add(self, profile: Profile) -> Profile:
        self.db.add(profile)
        return profile
