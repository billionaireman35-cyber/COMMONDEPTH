import base64
import binascii
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings

from app.models.content import Post
from app.integrations.media_storage import MediaStorage
from app.repositories.engagement import EngagementRepository
from app.repositories.feed import FeedRepository
from app.services.content import (
    PostReadModel,
    build_post_media_read_models,
)


class FeedError(Exception):
    pass


class InvalidFeedListError(FeedError):
    pass


FEED_DEFAULT_LIMIT = 20
FEED_MAX_LIMIT = 50


def _configured_editorial_usernames() -> list[str]:
    configured = get_settings().feed_editorial_usernames
    return [
        username.strip().lower()
        for username in configured.split(",")
        if username.strip()
    ]


def _merge_feed_posts(
    *,
    following_posts: list[Post],
    editorial_posts: list[Post],
    limit: int,
) -> list[Post]:
    merged: dict[UUID, Post] = {}

    for post in following_posts:
        merged[post.id] = post

    for post in editorial_posts:
        merged[post.id] = post

    return sorted(
        merged.values(),
        key=lambda post: (post.created_at, post.id),
        reverse=True,
    )[:limit]


def _encode_feed_cursor(
    *,
    created_at: datetime,
    post_id: UUID,
) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(post_id),
    }

    encoded = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).decode("ascii")

    return encoded.rstrip("=")


def _decode_feed_cursor(
    cursor: str,
) -> tuple[datetime, UUID]:
    if not cursor:
        raise InvalidFeedListError("Invalid feed cursor.")

    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(
            (cursor + padding).encode("ascii")
        )
        payload = json.loads(decoded.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError

        created_at = payload.get("created_at")
        post_id = payload.get("id")

        if not isinstance(created_at, str):
            raise ValueError

        if not isinstance(post_id, str):
            raise ValueError

        parsed_created_at = datetime.fromisoformat(created_at)
        parsed_post_id = UUID(post_id)

        return parsed_created_at, parsed_post_id

    except (
        binascii.Error,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise InvalidFeedListError(
            "Invalid feed cursor."
        ) from None


def list_feed_posts(
    db: Session,
    *,
    viewer_user_id: UUID,
    limit: int = FEED_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Post], str | None]:
    if limit < 1 or limit > FEED_MAX_LIMIT:
        raise InvalidFeedListError("Invalid feed limit.")

    cursor_created_at = None
    cursor_post_id = None

    if cursor is not None:
        (
            cursor_created_at,
            cursor_post_id,
        ) = _decode_feed_cursor(cursor)

    repository = FeedRepository(db)

    following_posts = repository.list_following_posts(
        viewer_user_id=viewer_user_id,
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_post_id=cursor_post_id,
    )

    editorial_posts = repository.list_editorial_posts(
        editorial_usernames=_configured_editorial_usernames(),
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_post_id=cursor_post_id,
    )

    posts = _merge_feed_posts(
        following_posts=following_posts,
        editorial_posts=editorial_posts,
        limit=limit + 1,
    )

    next_cursor = None

    if len(posts) > limit:
        posts = posts[:limit]
        last_post = posts[-1]

        next_cursor = _encode_feed_cursor(
            created_at=last_post.created_at,
            post_id=last_post.id,
        )

    return posts, next_cursor

def list_feed_post_read_models(
    db: Session,
    *,
    viewer_user_id: UUID,
    storage: MediaStorage,
    limit: int = FEED_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[PostReadModel], str | None]:
    posts, next_cursor = list_feed_posts(
        db,
        viewer_user_id=viewer_user_id,
        limit=limit,
        cursor=cursor,
    )

    post_ids = [post.id for post in posts]

    summaries = EngagementRepository(db).get_post_engagement_summaries(
        post_ids=post_ids,
        viewer_user_id=viewer_user_id,
    )

    media_by_post = build_post_media_read_models(
        db,
        post_ids=post_ids,
        storage=storage,
    )

    return [
        PostReadModel(
            post=post,
            engagement=summaries[post.id],
            media=media_by_post.get(post.id, []),
        )
        for post in posts
    ], next_cursor
