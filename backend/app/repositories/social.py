from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.profile import Profile
from app.models.social import Follow, FollowRequest


class SocialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_follow(
        self,
        *,
        follower_id: UUID,
        following_id: UUID,
    ) -> Follow | None:
        statement = select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.following_id == following_id,
        )
        return self.db.scalar(statement)

    def add_follow(self, follow: Follow) -> Follow:
        self.db.add(follow)
        return follow

    def delete_follow(self, follow: Follow) -> None:
        self.db.delete(follow)

    def count_followers(self, *, user_id: UUID) -> int:
        statement = (
            select(func.count(Follow.id))
            .join(User, User.id == Follow.follower_id)
            .join(Profile, Profile.user_id == User.id)
            .where(
                Follow.following_id == user_id,
                User.status == "active",
            )
        )
        return self.db.scalar(statement) or 0

    def count_following(self, *, user_id: UUID) -> int:
        statement = (
            select(func.count(Follow.id))
            .join(User, User.id == Follow.following_id)
            .join(Profile, Profile.user_id == User.id)
            .where(
                Follow.follower_id == user_id,
                User.status == "active",
            )
        )
        return self.db.scalar(statement) or 0

    def list_followers(
        self,
        *,
        user_id: UUID,
        limit: int,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[tuple[Follow, Profile]]:
        statement = (
            select(Follow, Profile)
            .join(User, User.id == Follow.follower_id)
            .join(Profile, Profile.user_id == User.id)
            .where(
                Follow.following_id == user_id,
                User.status == "active",
            )
        )

        if before_created_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    Follow.created_at < before_created_at,
                    (
                        (Follow.created_at == before_created_at)
                        & (Follow.id < before_id)
                    ),
                )
            )

        statement = (
            statement
            .order_by(Follow.created_at.desc(), Follow.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(statement).all())

    def list_following(
        self,
        *,
        user_id: UUID,
        limit: int,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[tuple[Follow, Profile]]:
        statement = (
            select(Follow, Profile)
            .join(User, User.id == Follow.following_id)
            .join(Profile, Profile.user_id == User.id)
            .where(
                Follow.follower_id == user_id,
                User.status == "active",
            )
        )

        if before_created_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    Follow.created_at < before_created_at,
                    (
                        (Follow.created_at == before_created_at)
                        & (Follow.id < before_id)
                    ),
                )
            )

        statement = (
            statement
            .order_by(Follow.created_at.desc(), Follow.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(statement).all())

    def get_follow_request(
        self,
        *,
        requester_id: UUID,
        target_id: UUID,
    ) -> FollowRequest | None:
        statement = select(FollowRequest).where(
            FollowRequest.requester_id == requester_id,
            FollowRequest.target_id == target_id,
        )
        return self.db.scalar(statement)

    def get_follow_request_by_id(
        self,
        request_id: UUID,
    ) -> FollowRequest | None:
        return self.db.get(FollowRequest, request_id)

    def add_follow_request(
        self,
        request: FollowRequest,
    ) -> FollowRequest:
        self.db.add(request)
        return request

    def delete_follow_request(
        self,
        request: FollowRequest,
    ) -> None:
        self.db.delete(request)
