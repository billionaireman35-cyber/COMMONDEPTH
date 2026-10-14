from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session, get_media_storage
from app.core.database import get_db
from app.integrations.media_storage.protocol import MediaStorage
from app.models.media import MediaAsset
from app.models.social import Follow
from app.models.story import Story, StoryMedia
from app.schemas.stories import StoryCreateRequest, StoryResponse, StoryMediaResponse
from app.services.session_authentication import AuthenticatedSession
from app.services.stories import (
    StoryAccessDeniedError,
    StoryValidationError,
    create_story,
)

router = APIRouter(prefix="/stories", tags=["stories"])


def _serialize_story(
    db: Session,
    story: Story,
    storage: MediaStorage,
) -> StoryResponse:
    statement = (
        select(StoryMedia, MediaAsset)
        .join(MediaAsset, MediaAsset.id == StoryMedia.media_asset_id)
        .where(
            StoryMedia.story_id == story.id,
            MediaAsset.status == "ready",
            MediaAsset.deleted_at.is_(None),
        )
        .order_by(StoryMedia.position.asc(), StoryMedia.id.asc())
    )

    media = []
    for item, asset in db.execute(statement).all():
        try:
            url = storage.get_read_url(storage_key=asset.storage_key)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Story media is temporarily unavailable.",
            ) from None

        media.append(
            StoryMediaResponse(
                id=item.id,
                media_asset_id=asset.id,
                media_type=asset.media_type,
                position=item.position,
                media_url=url,
            )
        )

    return StoryResponse(
        id=story.id,
        author_id=story.author_id,
        visibility=story.visibility,
        text_content=story.text_content,
        expires_at=story.expires_at,
        created_at=story.created_at,
        media=media,
    )


@router.post(
    "",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_story(
    payload: StoryCreateRequest,
    authenticated: AuthenticatedSession = Depends(get_authenticated_session),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> StoryResponse:
    try:
        story = create_story(
            db,
            author_id=authenticated.user_id,
            visibility=payload.visibility,
            text_content=payload.text_content,
            media_asset_ids=payload.media_asset_ids,
        )
    except StoryAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except StoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return _serialize_story(db, story, storage)


@router.get("/home", response_model=list[StoryResponse])
def get_home_stories(
    authenticated: AuthenticatedSession = Depends(get_authenticated_session),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> list[StoryResponse]:
    viewer_id = authenticated.user_id
    followed_ids = select(Follow.following_id).where(
        Follow.follower_id == viewer_id
    )
    now = datetime.now(timezone.utc)

    statement = (
        select(Story)
        .where(
            Story.author_id.in_(followed_ids) | (Story.author_id == viewer_id),
            Story.expires_at > now,
            Story.deleted_at.is_(None),
        )
        .order_by(Story.created_at.desc(), Story.id.desc())
        .limit(100)
    )

    stories = db.execute(statement).scalars().all()
    return [_serialize_story(db, story, storage) for story in stories]
