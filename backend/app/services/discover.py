import base64
import binascii
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.content import Post
from app.repositories.discover import DiscoverRepository


class DiscoverError(Exception):
    pass


class InvalidDiscoverListError(DiscoverError):
    pass


DISCOVER_DEFAULT_LIMIT = 1000
DISCOVER_MAX_LIMIT = 1000


def _encode_discover_cursor(
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


def _decode_discover_cursor(
    cursor: str,
) -> tuple[datetime, UUID]:
    if not cursor:
        raise InvalidDiscoverListError("Invalid discover cursor.")

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
        raise InvalidDiscoverListError(
            "Invalid discover cursor."
        ) from None


def list_discover_posts(
    db: Session,
    *,
    limit: int = DISCOVER_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Post], str | None]:
    if limit < 1 or limit > DISCOVER_MAX_LIMIT:
        raise InvalidDiscoverListError("Invalid discover limit.")

    cursor_created_at = None
    cursor_post_id = None

    if cursor is not None:
        cursor_created_at, cursor_post_id = _decode_discover_cursor(cursor)

    repository = DiscoverRepository(db)

    posts = repository.list_public_posts(
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_post_id=cursor_post_id,
    )

    next_cursor = None

    if len(posts) > limit:
        posts = posts[:limit]
        last_post = posts[-1]

        next_cursor = _encode_discover_cursor(
            created_at=last_post.created_at,
            post_id=last_post.id,
        )

    return posts, next_cursor
