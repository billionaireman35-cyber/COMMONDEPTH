from uuid import UUID

from sqlalchemy.orm import Session

from app.models.media import PostMedia
from app.repositories.content import ContentRepository
from app.repositories.media import MediaRepository


class PostMediaError(Exception):
    """Base error for post-media attachment operations."""


class PostMediaValidationError(PostMediaError):
    """Raised when a media attachment request is invalid."""


class PostMediaNotFoundError(PostMediaError):
    """Raised when the post or media asset cannot be found."""


class PostMediaAccessDeniedError(PostMediaError):
    """Raised when the authenticated user does not own the resource."""


def attach_media_to_post(
    db: Session,
    *,
    post_id: UUID,
    media_asset_id: UUID,
    user_id: UUID,
    position: int,
) -> PostMedia:
    if position < 0:
        raise PostMediaValidationError(
            "Media position must be greater than or equal to zero."
        )

    content_repository = ContentRepository(db)
    media_repository = MediaRepository(db)

    post = content_repository.get_by_id(post_id)
    if post is None or post.deleted_at is not None:
        raise PostMediaNotFoundError("Post not found.")

    if post.author_id != user_id:
        raise PostMediaAccessDeniedError(
            "You are not allowed to attach media to this post."
        )

    asset = media_repository.get_asset(media_asset_id)
    if asset is None:
        raise PostMediaNotFoundError("Media asset not found.")

    if asset.owner_id != user_id:
        raise PostMediaAccessDeniedError(
            "You are not allowed to attach this media asset."
        )

    if asset.deleted_at is not None or asset.status in {"deleted", "failed"}:
        raise PostMediaValidationError(
            "Media asset is not available for attachment."
        )

    if asset.status not in {"processing", "ready"}:
        raise PostMediaValidationError(
            "Media asset upload has not completed."
        )

    upload = media_repository.get_upload_by_asset_id(media_asset_id)
    if upload is None:
        raise PostMediaValidationError(
            "Media asset does not have a valid upload record."
        )

    if upload.status != "completed":
        raise PostMediaValidationError(
            "Media asset upload has not completed."
        )

    existing_asset = media_repository.get_post_media(
        post_id=post_id,
        media_asset_id=media_asset_id,
    )
    if existing_asset is not None:
        raise PostMediaValidationError(
            "Media asset is already attached to this post."
        )

    existing_position = media_repository.get_post_media_by_position(
        post_id=post_id,
        position=position,
    )
    if existing_position is not None:
        raise PostMediaValidationError(
            "Media position is already in use."
        )

    attachment = PostMedia(
        post_id=post_id,
        media_asset_id=media_asset_id,
        position=position,
    )

    media_repository.add_post_media(attachment)

    try:
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        raise PostMediaError(
            "Media could not be attached to the post."
        ) from None

    return attachment
