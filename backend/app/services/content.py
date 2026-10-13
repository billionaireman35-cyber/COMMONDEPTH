import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.content import Post, PostComment, PostRepost
from app.integrations.media_storage import MediaStorage
from app.repositories.media import MediaRepository
from app.repositories.content import ContentRepository
from app.repositories.engagement import (
    EngagementRepository,
    PostEngagementSummary,
)
from app.repositories.identity import IdentityRepository
from app.repositories.profile import ProfileRepository
from app.repositories.social import SocialRepository


@dataclass(frozen=True)
class PostMediaReadModel:
    id: UUID
    media_asset_id: UUID
    media_type: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    duration_ms: int | None
    url: str
    position: int


@dataclass(frozen=True)
class PostReadModel:
    post: Post
    author_username: str
    engagement: PostEngagementSummary
    media: list[PostMediaReadModel]


def build_author_usernames(
    db: Session,
    *,
    posts: list[Post],
) -> dict[UUID, str]:
    author_ids = {post.author_id for post in posts}
    return ProfileRepository(db).get_usernames_by_user_ids(author_ids)


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


class InvalidProfileActivityListError(ContentError):
    pass


@dataclass(frozen=True)
class ProfileReplyReadModel:
    comment: PostComment
    post: PostReadModel


@dataclass(frozen=True)
class ProfileRepostReadModel:
    repost: PostRepost
    post: PostReadModel


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



def build_post_media_read_models(
    db: Session,
    *,
    post_ids: list[UUID],
    storage: MediaStorage,
) -> dict[UUID, list[PostMediaReadModel]]:
    grouped = MediaRepository(db).list_ready_media_by_post_ids(
        post_ids=post_ids,
    )

    result: dict[UUID, list[PostMediaReadModel]] = {}

    for post_id, items in grouped.items():
        result[post_id] = [
            PostMediaReadModel(
                id=post_media.id,
                media_asset_id=asset.id,
                media_type=asset.media_type,
                mime_type=asset.mime_type,
                file_size=asset.file_size,
                width=asset.width,
                height=asset.height,
                duration_ms=asset.duration_ms,
                url=storage.get_read_url(
                    storage_key=asset.storage_key,
                ),
                position=post_media.position,
            )
            for post_media, asset in items
        ]

    return result


def get_post_read_model(
    db: Session,
    *,
    post_id: UUID,
    viewer_user_id: UUID,
    storage: MediaStorage,
) -> PostReadModel:
    post = get_post(
        db,
        post_id=post_id,
        viewer_user_id=viewer_user_id,
    )
    engagement = EngagementRepository(db).get_post_engagement_summaries(
        post_ids=[post.id],
        viewer_user_id=viewer_user_id,
    )[post.id]
    media = build_post_media_read_models(
        db,
        post_ids=[post.id],
        storage=storage,
    ).get(post.id, [])
    usernames = build_author_usernames(db, posts=[post])
    return PostReadModel(
        post=post,
        author_username=usernames.get(post.author_id, ""),
        engagement=engagement,
        media=media,
    )


def list_posts_by_author_read_model(
    db: Session,
    *,
    author_id: UUID,
    viewer_user_id: UUID,
    storage: MediaStorage,
    limit: int = POST_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[PostReadModel], str | None]:
    posts, next_cursor = list_posts_by_author(
        db,
        author_id=author_id,
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
    usernames = build_author_usernames(db, posts=posts)

    return [
        PostReadModel(
            post=post,
            author_username=usernames.get(post.author_id, ""),
            engagement=summaries[post.id],
            media=media_by_post.get(post.id, []),
        )
        for post in posts
    ], next_cursor


PROFILE_ACTIVITY_DEFAULT_LIMIT = 20
PROFILE_ACTIVITY_MAX_LIMIT = 50


def _encode_profile_activity_cursor(
    *,
    created_at: datetime,
    item_id: UUID,
    kind: str,
) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(item_id),
        "kind": kind,
    }
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_profile_activity_cursor(
    cursor: str,
    *,
    expected_kind: str,
) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )

        if not isinstance(payload, dict):
            raise ValueError("Invalid cursor payload.")

        if payload.get("kind") != expected_kind:
            raise ValueError("Cursor belongs to another activity list.")

        created_at = datetime.fromisoformat(payload["created_at"])
        item_id = UUID(payload["id"])

        if created_at.tzinfo is None:
            raise ValueError("Cursor timestamp must include a timezone.")

        return created_at, item_id
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        binascii.Error,
    ):
        raise InvalidProfileActivityListError(
            "Invalid profile activity cursor."
        ) from None


def _validate_profile_activity_request(
    db: Session,
    *,
    user_id: UUID,
    limit: int,
) -> None:
    if limit < 1 or limit > PROFILE_ACTIVITY_MAX_LIMIT:
        raise InvalidProfileActivityListError(
            "Invalid profile activity list limit."
        )

    profile_owner = IdentityRepository(db).get_user(user_id)
    if profile_owner is None or profile_owner.status != "active":
        raise InactiveUserError("Profile not found.")


def _build_profile_activity_post_read_models(
    db: Session,
    *,
    posts: list[Post],
    viewer_user_id: UUID,
    storage: MediaStorage,
) -> dict[UUID, PostReadModel]:
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
    usernames = build_author_usernames(db, posts=posts)

    return {
        post.id: PostReadModel(
            post=post,
            author_username=usernames.get(post.author_id, ""),
            engagement=summaries[post.id],
            media=media_by_post.get(post.id, []),
        )
        for post in posts
    }


def list_profile_replies_read_model(
    db: Session,
    *,
    user_id: UUID,
    viewer_user_id: UUID,
    storage: MediaStorage,
    limit: int = PROFILE_ACTIVITY_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[ProfileReplyReadModel], str | None]:
    _validate_profile_activity_request(
        db,
        user_id=user_id,
        limit=limit,
    )

    cursor_created_at = None
    cursor_comment_id = None

    if cursor is not None:
        cursor_created_at, cursor_comment_id = (
            _decode_profile_activity_cursor(
                cursor,
                expected_kind="reply",
            )
        )

    rows = EngagementRepository(db).list_profile_replies(
        user_id=user_id,
        viewer_user_id=viewer_user_id,
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_comment_id=cursor_comment_id,
    )

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last_comment, _ = rows[-1]
        next_cursor = _encode_profile_activity_cursor(
            created_at=last_comment.created_at,
            item_id=last_comment.id,
            kind="reply",
        )

    posts = [post for _, post in rows]
    post_models = _build_profile_activity_post_read_models(
        db,
        posts=posts,
        viewer_user_id=viewer_user_id,
        storage=storage,
    )

    return [
        ProfileReplyReadModel(
            comment=comment,
            post=post_models[post.id],
        )
        for comment, post in rows
    ], next_cursor


def list_profile_reposts_read_model(
    db: Session,
    *,
    user_id: UUID,
    viewer_user_id: UUID,
    storage: MediaStorage,
    limit: int = PROFILE_ACTIVITY_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[ProfileRepostReadModel], str | None]:
    _validate_profile_activity_request(
        db,
        user_id=user_id,
        limit=limit,
    )

    cursor_created_at = None
    cursor_repost_id = None

    if cursor is not None:
        cursor_created_at, cursor_repost_id = (
            _decode_profile_activity_cursor(
                cursor,
                expected_kind="repost",
            )
        )

    rows = EngagementRepository(db).list_profile_reposts(
        user_id=user_id,
        viewer_user_id=viewer_user_id,
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_repost_id=cursor_repost_id,
    )

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last_repost, _ = rows[-1]
        next_cursor = _encode_profile_activity_cursor(
            created_at=last_repost.created_at,
            item_id=last_repost.id,
            kind="repost",
        )

    posts = [post for _, post in rows]
    post_models = _build_profile_activity_post_read_models(
        db,
        posts=posts,
        viewer_user_id=viewer_user_id,
        storage=storage,
    )

    return [
        ProfileRepostReadModel(
            repost=repost,
            post=post_models[post.id],
        )
        for repost, post in rows
    ], next_cursor


def list_saved_posts_read_model(
    db: Session,
    *,
    viewer_user_id: UUID,
    storage: MediaStorage,
    limit: int = POST_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[PostReadModel], str | None]:
    if limit < 1 or limit > POST_MAX_LIMIT:
        raise InvalidPostListError("Invalid post list limit.")

    cursor_created_at = None
    cursor_bookmark_id = None

    if cursor is not None:
        cursor_created_at, cursor_bookmark_id = _decode_post_list_cursor(
            cursor
        )

    saved_rows = EngagementRepository(db).list_saved_posts(
        user_id=viewer_user_id,
        limit=limit + 1,
        cursor_created_at=cursor_created_at,
        cursor_bookmark_id=cursor_bookmark_id,
    )

    next_cursor = None

    if len(saved_rows) > limit:
        saved_rows = saved_rows[:limit]
        last_bookmark, _ = saved_rows[-1]
        next_cursor = _encode_post_list_cursor(
            created_at=last_bookmark.created_at,
            post_id=last_bookmark.id,
        )

    posts = [post for _, post in saved_rows]
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
    usernames = build_author_usernames(db, posts=posts)

    return [
        PostReadModel(
            post=post,
            author_username=usernames.get(post.author_id, ""),
            engagement=summaries[post.id],
            media=media_by_post.get(post.id, []),
        )
        for post in posts
    ], next_cursor


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
