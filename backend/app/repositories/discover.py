from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Post
from app.models.identity import User


class DiscoverRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_public_posts(
        self,
        *,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_post_id: UUID | None = None,
    ) -> list[Post]:
        statement = (
            select(Post)
            .join(
                User,
                User.id == Post.author_id,
            )
            .where(
                User.status == "active",
                Post.visibility == "public",
                Post.deleted_at.is_(None),
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
