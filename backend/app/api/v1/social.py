from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.models.social import Follow
from app.schemas.social import FollowResponse
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
