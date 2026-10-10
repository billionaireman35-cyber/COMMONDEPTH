from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.content import (
    Post,
    PostBookmark,
    PostComment,
    PostLike,
    PostRepost,
)
from app.models.identity import User
from app.models.social import Follow


@dataclass(frozen=True)
class PostEngagementSummary:
    like_count: int
    comment_count: int
    repost_count: int
    viewer_has_liked: bool
    viewer_has_reposted: bool
    viewer_has_bookmarked: bool


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


    def get_post_bookmark(
        self,
        *,
        post_id: UUID,
        user_id: UUID,
    ) -> PostBookmark | None:
        statement = select(PostBookmark).where(
            PostBookmark.post_id == post_id,
            PostBookmark.user_id == user_id,
        )
        return self.db.scalar(statement)

    def add_post_bookmark(
        self,
        bookmark: PostBookmark,
    ) -> PostBookmark:
        self.db.add(bookmark)
        return bookmark

    def delete_post_bookmark(
        self,
        bookmark: PostBookmark,
    ) -> None:
        self.db.delete(bookmark)

    def list_saved_posts(
        self,
        *,
        user_id: UUID,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_bookmark_id: UUID | None = None,
    ) -> list[tuple[PostBookmark, Post]]:
        follower_exists = exists(
            select(Follow.id).where(
                Follow.follower_id == user_id,
                Follow.following_id == Post.author_id,
            )
        )

        statement = (
            select(PostBookmark, Post)
            .join(Post, Post.id == PostBookmark.post_id)
            .join(User, User.id == Post.author_id)
            .where(
                PostBookmark.user_id == user_id,
                Post.deleted_at.is_(None),
                User.status == "active",
                or_(
                    Post.visibility == "public",
                    Post.author_id == user_id,
                    follower_exists,
                ),
            )
            .order_by(
                PostBookmark.created_at.desc(),
                PostBookmark.id.desc(),
            )
            .limit(limit)
        )

        if (
            cursor_created_at is not None
            and cursor_bookmark_id is not None
        ):
            statement = statement.where(
                (PostBookmark.created_at < cursor_created_at)
                | (
                    (PostBookmark.created_at == cursor_created_at)
                    & (PostBookmark.id < cursor_bookmark_id)
                )
            )

        return [
            (bookmark, post)
            for bookmark, post in self.db.execute(statement).all()
        ]

    def get_post_repost(
        self,
        *,
        post_id: UUID,
        user_id: UUID,
    ) -> PostRepost | None:
        statement = select(PostRepost).where(
            PostRepost.post_id == post_id,
            PostRepost.user_id == user_id,
        )
        return self.db.scalar(statement)

    def add_post_repost(self, repost: PostRepost) -> PostRepost:
        self.db.add(repost)
        return repost

    def delete_post_repost(self, repost: PostRepost) -> None:
        self.db.delete(repost)

    def count_post_reposts(self, *, post_id: UUID) -> int:
        statement = select(func.count()).select_from(PostRepost).where(
            PostRepost.post_id == post_id,
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

        repost_counts = {
            post_id: int(count)
            for post_id, count in self.db.execute(
                select(
                    PostRepost.post_id,
                    func.count().label("repost_count"),
                )
                .where(PostRepost.post_id.in_(unique_post_ids))
                .group_by(PostRepost.post_id)
            ).all()
        }

        viewer_reposted_post_ids = {
            post_id
            for (post_id,) in self.db.execute(
                select(PostRepost.post_id).where(
                    PostRepost.post_id.in_(unique_post_ids),
                    PostRepost.user_id == viewer_user_id,
                )
            ).all()
        }

        viewer_bookmarked_post_ids = {
            post_id
            for (post_id,) in self.db.execute(
                select(PostBookmark.post_id).where(
                    PostBookmark.post_id.in_(unique_post_ids),
                    PostBookmark.user_id == viewer_user_id,
                )
            ).all()
        }

        return {
            post_id: PostEngagementSummary(
                like_count=like_counts.get(post_id, 0),
                comment_count=comment_counts.get(post_id, 0),
                repost_count=repost_counts.get(post_id, 0),
                viewer_has_liked=post_id in viewer_liked_post_ids,
                viewer_has_reposted=post_id in viewer_reposted_post_ids,
                viewer_has_bookmarked=(
                    post_id in viewer_bookmarked_post_ids
                ),
            )
            for post_id in unique_post_ids
        }
