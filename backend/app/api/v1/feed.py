from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.schemas.content import PostListResponse, PostResponse
from app.services.feed import (
    InvalidFeedListError,
    list_feed_posts,
)
from app.services.session_authentication import AuthenticatedSession


router = APIRouter(prefix="/feed", tags=["feed"])


@router.get(
    "",
    response_model=PostListResponse,
)
def get_feed(
    limit: int = 20,
    cursor: str | None = None,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostListResponse:
    try:
        posts, next_cursor = list_feed_posts(
            db,
            viewer_user_id=authenticated.user_id,
            limit=limit,
            cursor=cursor,
        )
    except InvalidFeedListError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return PostListResponse(
        items=[
            PostResponse.model_validate(post)
            for post in posts
        ],
        next_cursor=next_cursor,
    )
