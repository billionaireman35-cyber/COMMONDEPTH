from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.integrations.media_storage.supabase import get_supabase_s3_storage
from app.integrations.media_storage import MediaStorage
from app.services.session_authentication import (
    AuthenticatedSession,
    SessionAuthenticationError,
    authenticate_session,
)

_bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthenticatedSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    try:
        return authenticate_session(
            db,
            session_token=credentials.credentials,
        )
    except SessionAuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        ) from None


def get_media_storage() -> MediaStorage:
    """Return the configured MediaStorage implementation."""
    return get_supabase_s3_storage()
