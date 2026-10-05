from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.schemas.profile import (
    ProfileCreateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.services.profile import (
    InvalidProfileInputError,
    ProfileAlreadyExistsError,
    ProfileError,
    ProfileNotFoundError,
    UsernameAlreadyExistsError,
    create_profile,
    get_my_profile,
    get_profile_by_username,
    update_profile,
    _UNSET,
)
from app.services.session_authentication import (
    AuthenticatedSession,
    SessionAuthenticationError,
    authenticate_session,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])

_optional_bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_authenticated_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _optional_bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> AuthenticatedSession | None:
    if credentials is None:
        return None

    if credentials.scheme.lower() != "bearer":
        return None

    try:
        return authenticate_session(
            db,
            session_token=credentials.credentials,
        )
    except SessionAuthenticationError:
        return None


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    request: ProfileCreateRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        profile = create_profile(
            db,
            user_id=authenticated.user_id,
            username=request.username,
            display_name=request.display_name,
            avatar=request.avatar,
            banner=request.banner,
            biography=request.biography,
            location=request.location,
            visibility=request.visibility,
        )
    except InvalidProfileInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except (
        ProfileAlreadyExistsError,
        UsernameAlreadyExistsError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except ProfileError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile could not be created.",
        ) from None

    return ProfileResponse.model_validate(profile)


@router.get(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def me(
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        profile = get_my_profile(
            db,
            user_id=authenticated.user_id,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    return ProfileResponse.model_validate(profile)


@router.patch(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_me(
    request: ProfileUpdateRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    try:
        fields = request.model_fields_set
        profile = update_profile(
            db,
            user_id=authenticated.user_id,
            username=request.username if "username" in fields else _UNSET,
            display_name=(
                request.display_name
                if "display_name" in fields
                else _UNSET
            ),
            avatar=request.avatar if "avatar" in fields else _UNSET,
            banner=request.banner if "banner" in fields else _UNSET,
            biography=(
                request.biography
                if "biography" in fields
                else _UNSET
            ),
            location=request.location if "location" in fields else _UNSET,
            visibility=(
                request.visibility
                if "visibility" in fields
                else _UNSET
            ),
        )
    except InvalidProfileInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except ProfileError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile could not be updated.",
        ) from None

    return ProfileResponse.model_validate(profile)


@router.get(
    "/{username}",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_by_username(
    username: str,
    authenticated: AuthenticatedSession | None = Depends(
        get_optional_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    viewer_user_id: UUID | None = (
        authenticated.user_id if authenticated is not None else None
    )

    try:
        profile = get_profile_by_username(
            db,
            username=username,
            viewer_user_id=viewer_user_id,
        )
    except (
        InvalidProfileInputError,
        ProfileNotFoundError,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        ) from None

    return ProfileResponse.model_validate(profile)
