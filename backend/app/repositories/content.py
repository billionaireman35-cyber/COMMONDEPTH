from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.content import Post
from app.models.identity import User
from app.models.social import Follow


class ContentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, post_id: UUID) -> Post | None:
        statement = select(Post).where(Post.id == post_id)
        return self.db.scalar(statement)

    def add(self, post: Post) -> Post:
        self.db.add(post)
        return post

    def list_by_author(
        self,
        *,
        author_id: UUID,
        viewer_user_id: UUID,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_post_id: UUID | None = None,
    ) -> list[Post]:
        follower_exists = exists(
            select(Follow.id).where(
                Follow.follower_id == viewer_user_id,
                Follow.following_id == Post.author_id,
            )
        )

        statement = (
            select(Post)
            .join(User, User.id == Post.author_id)
            .where(
                Post.author_id == author_id,
                User.status == "active",
                Post.deleted_at.is_(None),
                or_(
                    Post.visibility == "public",
                    Post.author_id == viewer_user_id,
                    follower_exists,
                ),
            )
            .order_by(
                Post.created_at.desc(),
                Post.id.desc(),
            )
            .limit(limit)
        )

        if cursor_created_at is not None and cursor_post_id is not None:
            statement = statement.where(
                (Post.created_at < cursor_created_at)
                | (
                    (Post.created_at == cursor_created_at)
                    & (Post.id < cursor_post_id)
                )
            )

        return list(self.db.scalars(statement).all())

    def count_by_author(
        self,
        *,
        author_id: UUID,
        viewer_user_id: UUID | None,
    ) -> int:
        """Count non-deleted posts visible to this viewer."""
        statement = (
            select(func.count(Post.id))
            .join(User, User.id == Post.author_id)
            .where(
                Post.author_id == author_id,
                User.status == "active",
                Post.deleted_at.is_(None),
            )
        )

        if viewer_user_id is None:
            statement = statement.where(Post.visibility == "public")
        else:
            follower_exists = exists(
                select(Follow.id).where(
                    Follow.follower_id == viewer_user_id,
                    Follow.following_id == Post.author_id,
                )
            )
            statement = statement.where(
                or_(
                    Post.visibility == "public",
                    Post.author_id == viewer_user_id,
                    follower_exists,
                )
            )

        return int(self.db.scalar(statement) or 0)
