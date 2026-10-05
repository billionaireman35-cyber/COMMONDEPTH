from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    DeviceRegistrationRequest,
    LoginRequest,
    LoginResponse,
    CurrentUserResponse,
    RegistrationRequest,
    RegistrationResponse,
)
from app.services.identity_login import (
    AuthenticationError,
    DeviceLoginInput,
    login_identity,
)
from app.services.session_authentication import (
    SessionAuthenticationError,
    authenticate_session,
    revoke_session,
)
from app.services.identity_registration import (
    DeviceRegistrationInput,
    DuplicateIdentityError,
    InvalidRegistrationInputError,
    RegistrationPersistenceConflictError,
    RegistrationServiceError,
    register_identity,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer_scheme = HTTPBearer(auto_error=False)


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegistrationRequest,
    db: Session = Depends(get_db),
) -> RegistrationResponse:
    device = (
        DeviceRegistrationInput(
            platform=request.device.platform,
            name=request.device.name,
            device_identifier_hash=request.device.device_identifier_hash,
        )
        if request.device is not None
        else None
    )

    try:
        result = register_identity(
            db,
            email=request.email,
            password=request.password,
            device=device,
        )
    except InvalidRegistrationInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except DuplicateIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except RegistrationPersistenceConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration could not be completed.",
        ) from None
    except RegistrationServiceError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration could not be completed.",
        ) from None

    return RegistrationResponse(
        user_id=result.user_id,
        session_id=result.session_id,
        session_token=result.session_token,
        session_expires_at=result.session_expires_at,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    device = (
        DeviceLoginInput(
            platform=request.device.platform,
            name=request.device.name,
            device_identifier_hash=request.device.device_identifier_hash,
        )
        if request.device is not None
        else None
    )

    try:
        result = login_identity(
            db,
            email=request.email,
            password=request.password,
            device=device,
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        ) from None

    return LoginResponse(
        user_id=result.user_id,
        session_id=result.session_id,
        session_token=result.session_token,
        session_expires_at=result.session_expires_at,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
)
def me(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    try:
        authenticated = authenticate_session(
            db,
            session_token=credentials.credentials,
        )
    except SessionAuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        ) from None

    return CurrentUserResponse(
        user_id=authenticated.user_id,
        status="active",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    revoke_session(
        db,
        session_token=credentials.credentials,
    )
