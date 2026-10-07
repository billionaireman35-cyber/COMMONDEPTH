import base64
import binascii
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.content import PostComment, PostLike
from app.repositories.engagement import EngagementRepository
from app.repositories.identity import IdentityRepository
from app.services.content import (
    ContentError,
    get_post,
)


class EngagementError(Exception):
    """Base class for engagement service errors."""


class EngagementUserInactiveError(EngagementError):
    """Raised when an inactive user attempts an engagement action."""


class PostLikeError(EngagementError):
    """Raised when a post-like operation cannot be completed."""


def _require_active_user(
    db: Session,
    *,
    user_id: UUID,
) -> None:
    user = IdentityRepository(db).get_user(user_id)

    if user is None or user.status != "active":
        raise EngagementUserInactiveError("User is not active.")


def like_post(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
) -> PostLike:
    _require_active_user(db, user_id=user_id)

    try:
        get_post(
            db,
            post_id=post_id,
            viewer_user_id=user_id,
        )
    except (ContentError,):
        raise

    repository = EngagementRepository(db)
    existing = repository.get_post_like(
        post_id=post_id,
        user_id=user_id,
    )

    if existing is not None:
        return existing

    like = PostLike(
        post_id=post_id,
        user_id=user_id,
    )
    repository.add_post_like(like)

    try:
        db.flush()
        db.commit()
        db.refresh(like)
        return like
    except Exception:
        db.rollback()
        raise PostLikeError("Post could not be liked.") from None


def unlike_post(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
) -> None:
    _require_active_user(db, user_id=user_id)

    try:
        get_post(
            db,
            post_id=post_id,
            viewer_user_id=user_id,
        )
    except (ContentError,):
        raise

    repository = EngagementRepository(db)
    existing = repository.get_post_like(
        post_id=post_id,
        user_id=user_id,
    )

    if existing is None:
        return

    repository.delete_post_like(existing)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise PostLikeError("Post could not be unliked.") from None


def get_post_like_count(
    db: Session,
    *,
    post_id: UUID,
    viewer_user_id: UUID,
) -> int:
    get_post(
        db,
        post_id=post_id,
        viewer_user_id=viewer_user_id,
    )

    return EngagementRepository(db).count_post_likes(
        post_id=post_id,
    )


class PostCommentError(EngagementError):
    """Raised when a post-comment operation cannot be completed."""


class InvalidPostCommentError(PostCommentError):
    """Raised when comment content is invalid."""


class PostCommentNotFoundError(PostCommentError):
    """Raised when a requested comment does not exist."""


class PostCommentUnauthorizedError(PostCommentError):
    """Raised when a user cannot delete a requested comment."""


COMMENT_DEFAULT_LIMIT = 20
COMMENT_MAX_LIMIT = 50


def _encode_post_comment_cursor(
    *,
    created_at: datetime,
    comment_id: UUID,
) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(comment_id),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).decode("ascii")
    return encoded.rstrip("=")


def _decode_post_comment_cursor(
    cursor: str,
) -> tuple[datetime, UUID]:
    if not cursor:
        raise InvalidPostCommentError("Invalid comment cursor.")

    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(
            (cursor + padding).encode("ascii")
        )
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError

        created_at = payload.get("created_at")
        comment_id = payload.get("id")
        if not isinstance(created_at, str):
            raise ValueError
        if not isinstance(comment_id, str):
            raise ValueError

        return datetime.fromisoformat(created_at), UUID(comment_id)
    except (
        binascii.Error,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise InvalidPostCommentError("Invalid comment cursor.") from None


def comment_on_post(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
    content: str,
) -> PostComment:
    _require_active_user(db, user_id=user_id)

    get_post(db, post_id=post_id, viewer_user_id=user_id)

    normalized_content = content.strip()

    if not normalized_content:
        raise InvalidPostCommentError("Comment cannot be empty.")

    if len(normalized_content) > 1000:
        raise InvalidPostCommentError(
            "Comment must be 1000 characters or fewer."
        )

    comment = PostComment(
        post_id=post_id,
        user_id=user_id,
        content=normalized_content,
    )

    repository = EngagementRepository(db)
    repository.add_post_comment(comment)

    try:
        db.flush()
        db.commit()
        db.refresh(comment)
        return comment
    except Exception:
        db.rollback()
        raise PostCommentError(
            "Comment could not be created."
        ) from None


def list_post_comments(
    db: Session,
    *,
    post_id: UUID,
    viewer_user_id: UUID,
    limit: int = COMMENT_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[PostComment], str | None]:
    _require_active_user(db, user_id=viewer_user_id)

    get_post(
        db,
        post_id=post_id,
        viewer_user_id=viewer_user_id,
    )

    if limit < 1 or limit > COMMENT_MAX_LIMIT:
        raise InvalidPostCommentError("Invalid comment list limit.")

    cursor_created_at = None
    cursor_comment_id = None

    if cursor is not None:
        cursor_created_at, cursor_comment_id = _decode_post_comment_cursor(
            cursor
        )

    comments = EngagementRepository(db).list_post_comments(
        post_id=post_id,
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_comment_id=cursor_comment_id,
    )

    next_cursor = None

    if len(comments) > limit:
        comments = comments[:limit]
        last_comment = comments[-1]
        next_cursor = _encode_post_comment_cursor(
            created_at=last_comment.created_at,
            comment_id=last_comment.id,
        )

    return comments, next_cursor


def delete_post_comment(
    db: Session,
    *,
    post_id: UUID,
    comment_id: UUID,
    user_id: UUID,
) -> None:
    _require_active_user(db, user_id=user_id)

    repository = EngagementRepository(db)
    comment = repository.get_post_comment(comment_id=comment_id)

    if (
        comment is None
        or comment.deleted_at is not None
        or comment.post_id != post_id
    ):
        raise PostCommentNotFoundError("Comment not found.")

    get_post(
        db,
        post_id=comment.post_id,
        viewer_user_id=user_id,
    )

    if comment.user_id != user_id:
        raise PostCommentUnauthorizedError(
            "You are not allowed to delete this comment."
        )

    comment.deleted_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise PostCommentError(
            "Comment could not be deleted."
        ) from None
