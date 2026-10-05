from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

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
