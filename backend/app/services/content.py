import base64
import binascii
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.content import Post
from app.repositories.content import ContentRepository
from app.repositories.identity import IdentityRepository
from app.repositories.social import SocialRepository


class ContentError(Exception):
    pass


class InvalidPostInputError(ContentError):
    pass


class InactiveUserError(ContentError):
    pass


class PostAccessDeniedError(ContentError):
    pass


class PostNotFoundError(ContentError):
    pass


class InvalidPostListError(ContentError):
    pass


POST_DEFAULT_LIMIT = 20
POST_MAX_LIMIT = 50


def _encode_post_list_cursor(
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


def _decode_post_list_cursor(
    cursor: str,
) -> tuple[datetime, UUID]:
    if not cursor:
        raise InvalidPostListError("Invalid post list cursor.")

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
        raise InvalidPostListError(
            "Invalid post list cursor."
        ) from None


def list_posts_by_author(
    db: Session,
    *,
    author_id: UUID,
    viewer_user_id: UUID,
    limit: int = POST_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Post], str | None]:
    if limit < 1 or limit > POST_MAX_LIMIT:
        raise InvalidPostListError("Invalid post list limit.")

    cursor_created_at = None
    cursor_post_id = None

    if cursor is not None:
        (
            cursor_created_at,
            cursor_post_id,
        ) = _decode_post_list_cursor(cursor)

    repository = ContentRepository(db)

    posts = repository.list_by_author(
        author_id=author_id,
        viewer_user_id=viewer_user_id,
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_post_id=cursor_post_id,
    )

    next_cursor = None

    if len(posts) > limit:
        posts = posts[:limit]
        last_post = posts[-1]
        next_cursor = _encode_post_list_cursor(
            created_at=last_post.created_at,
            post_id=last_post.id,
        )

    return posts, next_cursor


def create_post(
    db: Session,
    *,
    user_id: UUID,
    content: str,
    visibility: str = "public",
) -> Post:
    normalized_content = content.strip()

    if not normalized_content:
        raise InvalidPostInputError("Post content cannot be empty.")

    if len(normalized_content) > 5000:
        raise InvalidPostInputError("Post content must not exceed 5000 characters.")

    if visibility not in {"public", "followers"}:
        raise InvalidPostInputError("Invalid post visibility.")

    repository = ContentRepository(db)
    identity_repository = IdentityRepository(db)

    try:
        user = identity_repository.get_user(user_id)

        if user is None:
            raise InactiveUserError("User is not active.")

        if user.status != "active":
            raise InactiveUserError("User is not active.")

        post = Post(
            author_id=user_id,
            content=normalized_content,
            visibility=visibility,
        )

        repository.add(post)
        db.flush()
        db.commit()
        db.refresh(post)

        return post

    except (InvalidPostInputError, InactiveUserError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise ContentError("Post could not be created.") from None



def get_post(
    db: Session,
    *,
    post_id: UUID,
    viewer_user_id: UUID,
) -> Post:
    repository = ContentRepository(db)
    post = repository.get_by_id(post_id)

    if post is None or post.deleted_at is not None:
        raise PostNotFoundError("Post not found.")

    if post.visibility == "public":
        return post

    if post.author_id == viewer_user_id:
        return post

    follow = SocialRepository(db).get_follow(
        follower_id=viewer_user_id,
        following_id=post.author_id,
    )

    if follow is None:
        raise PostAccessDeniedError("Post not found.")

    return post



def delete_post(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
) -> None:
    repository = ContentRepository(db)
    post = repository.get_by_id(post_id)

    if post is None or post.deleted_at is not None:
        raise PostNotFoundError("Post not found.")

    if post.author_id != user_id:
        raise PostAccessDeniedError("You are not allowed to delete this post.")

    try:
        post.deleted_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise ContentError("Post could not be deleted.") from None
