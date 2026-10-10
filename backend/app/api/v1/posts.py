from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authenticated_session,
    get_media_storage,
)
from app.core.database import get_db
from app.integrations.media_storage import MediaStorage
from app.schemas.media import (
    PostMediaAttachRequest,
    PostMediaResponse,
)
from app.schemas.content import (
    PostCommentCreateRequest,
    PostCommentListResponse,
    PostCommentResponse,
    PostCreateRequest,
    PostLikeResponse,
    PostListResponse,
    PostBookmarkResponse,
    PostRepostResponse,
    PostResponse,
)
from app.services.post_media import (
    PostMediaAccessDeniedError,
    PostMediaError,
    PostMediaNotFoundError,
    PostMediaValidationError,
    attach_media_to_post,
)
from app.services.content import (
    ContentError,
    InactiveUserError,
    InvalidPostInputError,
    InvalidPostListError,
    PostAccessDeniedError,
    PostNotFoundError,
    PostReadModel,
    create_post,
    delete_post,
    get_post_read_model,
    list_posts_by_author_read_model,
    list_saved_posts_read_model,
)
from app.services.engagement import (
    EngagementUserInactiveError,
    InvalidPostCommentError,
    PostCommentError,
    PostCommentNotFoundError,
    PostCommentUnauthorizedError,
    PostLikeError,
    PostBookmarkError,
    PostRepostError,
    comment_on_post,
    delete_post_comment,
    get_post_like_count,
    get_post_repost_count,
    like_post,
    list_post_comments,
    repost_post,
    bookmark_post,
    unbookmark_post,
    unrepost_post,
    unlike_post,
)

from app.services.session_authentication import AuthenticatedSession


router = APIRouter(prefix="/posts", tags=["posts"])


def _post_response(read_model: PostReadModel) -> PostResponse:
    post = read_model.post
    engagement = read_model.engagement

    return PostResponse(
        id=post.id,
        author_id=post.author_id,
        content=post.content,
        visibility=post.visibility,
        created_at=post.created_at,
        updated_at=post.updated_at,
        like_count=engagement.like_count,
        comment_count=engagement.comment_count,
        repost_count=engagement.repost_count,
        viewer_has_liked=engagement.viewer_has_liked,
        viewer_has_reposted=engagement.viewer_has_reposted,
        viewer_has_bookmarked=engagement.viewer_has_bookmarked,
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
    storage: MediaStorage = Depends(get_media_storage),
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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

    read_model = get_post_read_model(
        db,
        post_id=post.id,
        viewer_user_id=authenticated.user_id,
        storage=storage,
    )

    return _post_response(read_model)


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
    storage: MediaStorage = Depends(get_media_storage),
) -> PostListResponse:
    try:
        read_models, next_cursor = list_posts_by_author_read_model(
            db,
            author_id=user_id,
            viewer_user_id=authenticated.user_id,
            storage=storage,
            limit=limit,
            cursor=cursor,
        )
    except InvalidPostListError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None

    return PostListResponse(
        items=[_post_response(read_model) for read_model in read_models],
        next_cursor=next_cursor,
    )


@router.get(
    "/saved",
    response_model=PostListResponse,
)
def list_saved_posts(
    limit: int = 20,
    cursor: str | None = None,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> PostListResponse:
    try:
        read_models, next_cursor = list_saved_posts_read_model(
            db,
            viewer_user_id=authenticated.user_id,
            storage=storage,
            limit=limit,
            cursor=cursor,
        )
    except InvalidPostListError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None

    return PostListResponse(
        items=[_post_response(read_model) for read_model in read_models],
        next_cursor=next_cursor,
    )


@router.post(
    "/{post_id}/media",
    response_model=PostMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_media(
    post_id: UUID,
    payload: PostMediaAttachRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostMediaResponse:
    try:
        attachment = attach_media_to_post(
            db,
            post_id=post_id,
            media_asset_id=payload.media_asset_id,
            user_id=authenticated.user_id,
            position=payload.position,
        )
    except PostMediaValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    except PostMediaNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except PostMediaAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except PostMediaError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Media could not be attached to the post.",
        ) from None

    return PostMediaResponse.model_validate(attachment)


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
    storage: MediaStorage = Depends(get_media_storage),
) -> PostResponse:
    try:
        read_model = get_post_read_model(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
            storage=storage,
        )
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None

    return _post_response(read_model)


@router.post(
    "/{post_id}/like",
    response_model=PostLikeResponse,
)
def like(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostLikeResponse:
    try:
        like_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
        count = get_post_like_count(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except PostLikeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be liked.",
        ) from None
    except PostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None

    return PostLikeResponse(liked=True, like_count=count)


@router.delete(
    "/{post_id}/like",
    response_model=PostLikeResponse,
)
def unlike(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostLikeResponse:
    try:
        unlike_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
        count = get_post_like_count(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except PostLikeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be unliked.",
        ) from None
    except PostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None

    return PostLikeResponse(liked=False, like_count=count)


@router.post(
    "/{post_id}/repost",
    response_model=PostRepostResponse,
)
def repost(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostRepostResponse:
    try:
        repost_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
        count = get_post_repost_count(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostRepostError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be reposted.",
        ) from None

    return PostRepostResponse(reposted=True, repost_count=count)


@router.delete(
    "/{post_id}/repost",
    response_model=PostRepostResponse,
)
def unrepost(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostRepostResponse:
    try:
        unrepost_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
        count = get_post_repost_count(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostRepostError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be unreposted.",
        ) from None

    return PostRepostResponse(reposted=False, repost_count=count)


@router.post(
    "/{post_id}/bookmark",
    response_model=PostBookmarkResponse,
)
def bookmark(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostBookmarkResponse:
    try:
        bookmark_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostBookmarkError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be bookmarked.",
        ) from None

    return PostBookmarkResponse(bookmarked=True)


@router.delete(
    "/{post_id}/bookmark",
    response_model=PostBookmarkResponse,
)
def unbookmark(
    post_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostBookmarkResponse:
    try:
        unbookmark_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostBookmarkError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post could not be unbookmarked.",
        ) from None

    return PostBookmarkResponse(bookmarked=False)


@router.post(
    "/{post_id}/comments",
    response_model=PostCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: UUID,
    payload: PostCommentCreateRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostCommentResponse:
    try:
        comment = comment_on_post(
            db,
            post_id=post_id,
            user_id=authenticated.user_id,
            content=payload.content,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except InvalidPostCommentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostCommentError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comment could not be created.",
        ) from None

    return PostCommentResponse.model_validate(comment)


@router.get(
    "/{post_id}/comments",
    response_model=PostCommentListResponse,
)
def get_comments(
    post_id: UUID,
    limit: int = 20,
    cursor: str | None = None,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> PostCommentListResponse:
    try:
        comments, next_cursor = list_post_comments(
            db,
            post_id=post_id,
            viewer_user_id=authenticated.user_id,
            limit=limit,
            cursor=cursor,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except InvalidPostCommentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostCommentError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comments could not be retrieved.",
        ) from None

    return PostCommentListResponse(
        items=[
            PostCommentResponse.model_validate(comment)
            for comment in comments
        ],
        next_cursor=next_cursor,
    )


@router.delete(
    "/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_comment(
    post_id: UUID,
    comment_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_post_comment(
            db,
            post_id=post_id,
            comment_id=comment_id,
            user_id=authenticated.user_id,
        )
    except EngagementUserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except PostCommentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found.",
        ) from None
    except PostCommentUnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        ) from None
    except PostCommentError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comment could not be deleted.",
        ) from None


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
