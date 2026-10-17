from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.schemas.creator_profile import (
    CreatorProfileResponse,
    CreatorProfileSaveRequest,
)
from app.services.creator_profile import (
    CreatorAccountRequiredError,
    CreatorBaseProfileRequiredError,
    CreatorProfileError,
    CreatorProfileNotFoundError,
    CreatorProfileValidationError,
    get_my_creator_profile,
    save_creator_profile,
)
from app.services.session_authentication import AuthenticatedSession


router = APIRouter(
    prefix="/creator-profile",
    tags=["creator-profile"],
)


def _raise_creator_error(error: CreatorProfileError) -> None:
    if isinstance(error, CreatorAccountRequiredError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, CreatorBaseProfileRequiredError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, CreatorProfileNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, CreatorProfileValidationError):
        code = status.HTTP_400_BAD_REQUEST
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR

    detail = (
        str(error)
        if code != status.HTTP_500_INTERNAL_SERVER_ERROR
        else "Creator Profile operation failed."
    )
    raise HTTPException(status_code=code, detail=detail) from error


@router.get(
    "/me",
    response_model=CreatorProfileResponse,
    status_code=status.HTTP_200_OK,
)
def read_my_creator_profile(
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> CreatorProfileResponse:
    try:
        return get_my_creator_profile(
            db,
            user_id=authenticated.user_id,
        )
    except CreatorProfileError as error:
        _raise_creator_error(error)


@router.put(
    "/me",
    response_model=CreatorProfileResponse,
    status_code=status.HTTP_200_OK,
)
def save_my_creator_profile(
    request: CreatorProfileSaveRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> CreatorProfileResponse:
    try:
        return save_creator_profile(
            db,
            user_id=authenticated.user_id,
            profession=request.profession,
            niche=request.niche,
            content_types=request.content_types,
            introduction=request.introduction,
        )
    except CreatorProfileError as error:
        _raise_creator_error(error)
