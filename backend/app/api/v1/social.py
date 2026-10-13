from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session, get_media_storage
from app.core.database import get_db
from app.models.social import Follow
from app.schemas.social import (
    FollowersResponse,
    FollowingResponse,
    FollowResponse,
    FollowStatusResponse,
    SocialRelationshipCountsResponse,
)
from app.services.profile import InvalidProfileInputError
from app.services.profile_media import serialize_profile_discovery_response
from app.integrations.media_storage.protocol import MediaStorage
from app.services.session_authentication import AuthenticatedSession
from app.services.social import (
    AlreadyFollowingError,
    CannotFollowSelfError,
    FollowRequestNotFoundError,
    FollowRequestPendingError,
    FollowRequestUnauthorizedError,
    InvalidFollowRequestStateError,
    SocialError,
    SocialTargetInactiveError,
    SocialTargetNotFoundError,
    accept_follow_request,
    cancel_follow_request,
    follow_user,
    reject_follow_request,
    unfollow_user,
    InvalidSocialCursorError,
    SocialRelationshipAccessDeniedError,
    get_relationship_counts,
    get_viewer_follow_status,
    list_followers,
    list_following,
)


router = APIRouter(prefix="/social", tags=["social"])


@router.post(
    "/follow/{username}",
    response_model=FollowResponse,
    status_code=status.HTTP_201_CREATED,
)
def follow(
    username: str,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> FollowResponse:
    try:
        result = follow_user(
            db,
            follower_id=authenticated.user_id,
            username=username,
        )
    except CannotFollowSelfError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except SocialTargetInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except SocialTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except (
        AlreadyFollowingError,
        FollowRequestPendingError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except SocialError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Follow operation could not be completed.",
        ) from None

    if isinstance(result, Follow):
        return FollowResponse(status="following")

    return FollowResponse(status="pending")


@router.delete(
    "/follow/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unfollow(
    username: str,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> None:
    try:
        unfollow_user(
            db,
            follower_id=authenticated.user_id,
            username=username,
        )
    except SocialTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except FollowRequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None


@router.post(
    "/follow-requests/{request_id}/accept",
    response_model=FollowResponse,
    status_code=status.HTTP_200_OK,
)
def accept_request(
    request_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> FollowResponse:
    try:
        accept_follow_request(
            db,
            target_user_id=authenticated.user_id,
            request_id=request_id,
        )
    except FollowRequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except FollowRequestUnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except InvalidFollowRequestStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except SocialError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Follow request could not be accepted.",
        ) from None

    return FollowResponse(status="following")


@router.post(
    "/follow-requests/{request_id}/reject",
    response_model=FollowResponse,
    status_code=status.HTTP_200_OK,
)
def reject_request(
    request_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> FollowResponse:
    try:
        request = reject_follow_request(
            db,
            target_user_id=authenticated.user_id,
            request_id=request_id,
        )
    except FollowRequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except FollowRequestUnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except InvalidFollowRequestStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except SocialError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Follow request could not be rejected.",
        ) from None

    return FollowResponse(status="rejected")


@router.delete(
    "/follow-requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_request(
    request_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> None:
    try:
        cancel_follow_request(
            db,
            requester_user_id=authenticated.user_id,
            request_id=request_id,
        )
    except FollowRequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except FollowRequestUnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except InvalidFollowRequestStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except SocialError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Follow request could not be cancelled.",
        ) from None


@router.get(
    "/follow-status/{username}",
    response_model=FollowStatusResponse,
)
def viewer_follow_status(
    username: str,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> FollowStatusResponse:
    try:
        result = get_viewer_follow_status(
            db,
            username=username,
            viewer_user_id=authenticated.user_id,
        )
    except (SocialTargetNotFoundError, SocialTargetInactiveError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        ) from None
    except InvalidProfileInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return FollowStatusResponse(status=result)


@router.get(
    "/profiles/{username}/relationships",
    response_model=SocialRelationshipCountsResponse,
)
def relationship_counts(
    username: str,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> SocialRelationshipCountsResponse:
    try:
        follower_count, following_count = get_relationship_counts(
            db,
            username=username,
            viewer_user_id=authenticated.user_id,
        )
    except SocialRelationshipAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (SocialTargetNotFoundError, SocialTargetInactiveError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        ) from None
    except InvalidProfileInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return SocialRelationshipCountsResponse(
        follower_count=follower_count,
        following_count=following_count,
    )


@router.get(
    "/profiles/{username}/followers",
    response_model=FollowersResponse,
)
def followers(
    username: str,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=1024),
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> FollowersResponse:
    try:
        profiles, next_cursor = list_followers(
            db,
            username=username,
            viewer_user_id=authenticated.user_id,
            limit=limit,
            cursor=cursor,
        )
    except SocialRelationshipAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (SocialTargetNotFoundError, SocialTargetInactiveError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        ) from None
    except InvalidProfileInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    except InvalidSocialCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return FollowersResponse(
        items=[
            serialize_profile_discovery_response(
                db,
                profile,
                storage=storage,
            )
            for profile in profiles
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/profiles/{username}/following",
    response_model=FollowingResponse,
)
def following(
    username: str,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=1024),
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> FollowingResponse:
    try:
        profiles, next_cursor = list_following(
            db,
            username=username,
            viewer_user_id=authenticated.user_id,
            limit=limit,
            cursor=cursor,
        )
    except SocialRelationshipAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from None
    except (SocialTargetNotFoundError, SocialTargetInactiveError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        ) from None
    except InvalidProfileInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    except InvalidSocialCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return FollowingResponse(
        items=[
            serialize_profile_discovery_response(
                db,
                profile,
                storage=storage,
            )
            for profile in profiles
        ],
        next_cursor=next_cursor,
    )
