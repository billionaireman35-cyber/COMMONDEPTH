from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.story import Story, StoryMedia
from app.repositories.media import MediaRepository


class StoryValidationError(Exception):
    pass


class StoryAccessDeniedError(Exception):
    pass


def create_story(
    db: Session,
    *,
    author_id: UUID,
    visibility: str = "public",
    text_content: str | None = None,
    media_asset_ids: list[UUID] | None = None,
) -> Story:
    if visibility not in {"public", "followers"}:
        raise StoryValidationError("Invalid Story visibility.")

    text = text_content.strip() if text_content else None
    asset_ids = list(media_asset_ids or [])

    if text is not None and len(text) > 5000:
        raise StoryValidationError("Story text cannot exceed 5000 characters.")

    if len(asset_ids) > 10:
        raise StoryValidationError("A Story can contain at most 10 media items.")

    if len(set(asset_ids)) != len(asset_ids):
        raise StoryValidationError("Duplicate Story media is not allowed.")

    if not text and not asset_ids:
        raise StoryValidationError(
            "A Story must contain text or at least one media item."
        )

    media_repository = MediaRepository(db)

    try:
        for asset_id in asset_ids:
            asset = media_repository.get_asset(asset_id)

            if asset is None:
                raise StoryValidationError("Media asset not found.")

            if asset.owner_id != author_id:
                raise StoryAccessDeniedError(
                    "You are not allowed to use this media asset."
                )

            if asset.deleted_at is not None or asset.status in {
                "deleted",
                "failed",
            }:
                raise StoryValidationError(
                    "Media asset is not available for attachment."
                )

            if asset.status != "ready":
                raise StoryValidationError(
                    "Story media must be ready before publishing."
                )

            upload = media_repository.get_upload_by_asset_id(asset_id)

            if upload is None or upload.status != "completed":
                raise StoryValidationError(
                    "Media asset upload has not completed."
                )

        now = datetime.now(timezone.utc)
        story = Story(
            author_id=author_id,
            visibility=visibility,
            text_content=text,
            expires_at=now + timedelta(hours=24),
        )
        db.add(story)
        db.flush()

        for position, asset_id in enumerate(asset_ids):
            db.add(
                StoryMedia(
                    story_id=story.id,
                    media_asset_id=asset_id,
                    position=position,
                )
            )

        db.commit()
        db.refresh(story)
        return story

    except Exception:
        db.rollback()
        raise
