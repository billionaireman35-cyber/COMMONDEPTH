from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.schemas.discover import DiscoverListResponse
from app.services.discover import (
    InvalidDiscoverListError,
    list_discover_posts,
)
from app.services.session_authentication import AuthenticatedSession
from app.schemas.content import PostResponse


router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("", response_model=DiscoverListResponse)
def discover(
    limit: int = 1000,
    cursor: str | None = None,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> DiscoverListResponse:
    try:
        posts, next_cursor = list_discover_posts(
            db,
            limit=limit,
            cursor=cursor,
        )
    except InvalidDiscoverListError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return DiscoverListResponse(
        items=[
            PostResponse.model_validate(post)
            for post in posts
        ],
        next_cursor=next_cursor,
    )
