from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.schemas.content import (
    PostCreateRequest,
    PostListResponse,
    PostResponse,
)
from app.services.content import (
    ContentError,
    InactiveUserError,
    InvalidPostInputError,
    InvalidPostListError,
    PostAccessDeniedError,
    PostNotFoundError,
    create_post,
    delete_post,
    get_post,
    list_posts_by_author,
)
from app.services.session_authentication import AuthenticatedSession


router = APIRouter(prefix="/posts", tags=["posts"])


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    payload: PostCreateRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostResponse:
    try:
        post = create_post(
            db,
            user_id=authenticated.user_id,
            content=payload.content,
            visibility=payload.visibility,
        )
    except InvalidPostInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except ContentError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be created.",
        ) from None

    return PostResponse.model_validate(post)


@router.get(
    "/user/{user_id}",
    response_model=PostListResponse,
)
def list_user_posts(
    user_id: UUID,
    limit: int = 20,
    cursor: str | None = None,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostListResponse:
    try:
        posts, next_cursor = list_posts_by_author(
            db,
            author_id=user_id,
            viewer_user_id=authenticated.user_id,
            limit=limit,
            cursor=cursor,
        )
    except InvalidPostListError as exc:
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


@router.get(
    "/{post_id}",
    response_model=PostResponse,
)
def get(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostResponse:
    try:
        post = get_post(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
        )
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None

    return PostResponse.model_validate(post)


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
    except PostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this post.",
        ) from None
