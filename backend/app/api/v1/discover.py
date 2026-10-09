from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authenticated_session,
    get_media_storage,
)
from app.core.database import get_db
from app.integrations.media_storage import MediaStorage
from app.schemas.content import PostResponse
from app.schemas.discover import DiscoverListResponse
from app.services.discover import (
    InvalidDiscoverListError,
    list_discover_post_read_models,
)
from app.services.session_authentication import AuthenticatedSession


router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("", response_model=DiscoverListResponse)
def discover(
    limit: int = 1000,
    cursor: str | None = None,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> DiscoverListResponse:
    try:
        read_models, next_cursor = list_discover_post_read_models(
            db,
            viewer_user_id=authenticated.user_id,
            limit=limit,
            cursor=cursor,
            storage=storage,
        )
    except InvalidDiscoverListError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return DiscoverListResponse(
        items=[
            PostResponse(
                id=read_model.post.id,
                author_id=read_model.post.author_id,
                content=read_model.post.content,
                visibility=read_model.post.visibility,
                created_at=read_model.post.created_at,
                updated_at=read_model.post.updated_at,
                like_count=read_model.engagement.like_count,
                comment_count=read_model.engagement.comment_count,
                viewer_has_liked=read_model.engagement.viewer_has_liked,
                media=[
                    {
                        "id": media.id,
                        "media_asset_id": media.media_asset_id,
                        "media_type": media.media_type,
                        "mime_type": media.mime_type,
                        "file_size": media.file_size,
                        "width": media.width,
                        "height": media.height,
                        "duration_ms": media.duration_ms,
                        "url": media.url,
                        "position": media.position,
                    }
                    for media in read_model.media
                ],
            )
            for read_model in read_models
        ],
        next_cursor=next_cursor,
    )
