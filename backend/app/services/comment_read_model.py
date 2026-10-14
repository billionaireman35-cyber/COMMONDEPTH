from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.media_storage import MediaStorage
from app.models.media import MediaAsset
from app.models.profile import Profile
from app.schemas.content import PostCommentResponse


def serialize_comment_responses(
    db: Session,
    comments: list,
    *,
    storage: MediaStorage,
) -> list[PostCommentResponse]:
    """Serialize comments with batched commenter identity and avatar data."""
    responses = [
        PostCommentResponse.model_validate(comment)
        for comment in comments
    ]
    user_ids: set[UUID] = {comment.user_id for comment in comments}

    if not user_ids:
        return responses

    statement = (
        select(
            Profile.user_id,
            Profile.username,
            Profile.display_name,
            Profile.avatar,
            MediaAsset.storage_key,
            MediaAsset.status,
            MediaAsset.deleted_at,
        )
        .select_from(Profile)
        .outerjoin(
            MediaAsset,
            Profile.avatar_asset_id == MediaAsset.id,
        )
        .where(Profile.user_id.in_(user_ids))
    )

    profiles = {
        row.user_id: row
        for row in db.execute(statement)
    }

    result: list[PostCommentResponse] = []

    for comment, response in zip(comments, responses):
        profile = profiles.get(comment.user_id)

        if profile is None:
            result.append(response)
            continue

        # Retain legacy avatar URLs unless a valid managed asset is available.
        avatar_url = profile.avatar

        if (
            profile.storage_key
            and profile.status == "ready"
            and profile.deleted_at is None
        ):
            try:
                avatar_url = storage.get_read_url(
                    storage_key=profile.storage_key,
                )
            except Exception:
                # Avatar URLs are optional; preserve comment availability
                # if the storage provider cannot sign a read URL.
                pass

        result.append(
            response.model_copy(
                update={
                    "username": profile.username,
                    "display_name": profile.display_name,
                    "avatar": avatar_url,
                }
            )
        )

    return result
