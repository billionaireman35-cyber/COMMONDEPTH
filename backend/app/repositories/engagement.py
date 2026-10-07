from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content import PostComment, PostLike


@dataclass(frozen=True)
class PostEngagementSummary:
    like_count: int
    comment_count: int
    viewer_has_liked: bool


class EngagementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_post_like(
        self,
        *,
        post_id: UUID,
        user_id: UUID,
    ) -> PostLike | None:
        statement = select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
        return self.db.scalar(statement)

    def add_post_like(self, like: PostLike) -> PostLike:
        self.db.add(like)
        return like

    def delete_post_like(self, like: PostLike) -> None:
        self.db.delete(like)

    def count_post_likes(self, *, post_id: UUID) -> int:
        statement = select(func.count()).select_from(PostLike).where(
            PostLike.post_id == post_id,
        )
        return int(self.db.scalar(statement) or 0)


    def get_post_comment(
        self,
        *,
        comment_id: UUID,
    ) -> PostComment | None:
        statement = select(PostComment).where(
            PostComment.id == comment_id,
        )
        return self.db.scalar(statement)

    def add_post_comment(self, comment: PostComment) -> PostComment:
        self.db.add(comment)
        return comment

    def list_post_comments(
        self,
        *,
        post_id: UUID,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_comment_id: UUID | None = None,
    ) -> list[PostComment]:
        statement = (
            select(PostComment)
            .where(
                PostComment.post_id == post_id,
                PostComment.deleted_at.is_(None),
            )
            .order_by(
                PostComment.created_at.desc(),
                PostComment.id.desc(),
            )
            .limit(limit)
        )

        if cursor_created_at is not None and cursor_comment_id is not None:
            statement = statement.where(
                (PostComment.created_at < cursor_created_at)
                | (
                    (PostComment.created_at == cursor_created_at)
                    & (PostComment.id < cursor_comment_id)
                )
            )

        return list(self.db.scalars(statement).all())

    def count_post_comments(self, *, post_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(PostComment)
            .where(
                PostComment.post_id == post_id,
                PostComment.deleted_at.is_(None),
            )
        )
        return int(self.db.scalar(statement) or 0)


    def get_post_engagement_summaries(
        self,
        *,
        post_ids: list[UUID],
        viewer_user_id: UUID,
    ) -> dict[UUID, PostEngagementSummary]:
        if not post_ids:
            return {}

        unique_post_ids = list(dict.fromkeys(post_ids))

        like_counts = {
            post_id: int(count)
            for post_id, count in self.db.execute(
                select(
                    PostLike.post_id,
                    func.count().label("like_count"),
                )
                .where(PostLike.post_id.in_(unique_post_ids))
                .group_by(PostLike.post_id)
            ).all()
        }

        comment_counts = {
            post_id: int(count)
            for post_id, count in self.db.execute(
                select(
                    PostComment.post_id,
                    func.count().label("comment_count"),
                )
                .where(
                    PostComment.post_id.in_(unique_post_ids),
                    PostComment.deleted_at.is_(None),
                )
                .group_by(PostComment.post_id)
            ).all()
        }

        viewer_liked_post_ids = {
            post_id
            for (post_id,) in self.db.execute(
                select(PostLike.post_id).where(
                    PostLike.post_id.in_(unique_post_ids),
                    PostLike.user_id == viewer_user_id,
                )
            ).all()
        }

        return {
            post_id: PostEngagementSummary(
                like_count=like_counts.get(post_id, 0),
                comment_count=comment_counts.get(post_id, 0),
                viewer_has_liked=post_id in viewer_liked_post_ids,
            )
            for post_id in unique_post_ids
        }
