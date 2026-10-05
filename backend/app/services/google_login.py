from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.identity import Session as IdentitySession
from app.repositories.identity import IdentityRepository
from app.services.google_oidc import (
    GoogleOIDCError,
    verify_google_id_token,
)


GOOGLE_PROVIDER = "google"
SESSION_LIFETIME = timedelta(days=30)
AUTHENTICATION_FAILED_MESSAGE = "Authentication failed."


class GoogleAuthenticationError(Exception):
    """Raised when Google authentication cannot be completed."""


class GoogleAuthenticationServiceError(GoogleAuthenticationError):
    """Raised when an unexpected Google authentication failure occurs."""


@dataclass(frozen=True)
class GoogleLoginResult:
    user_id: UUID
    session_id: UUID
    session_token: str
    session_expires_at: datetime


def _generate_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode("utf-8")).hexdigest()
    return token, token_hash


def login_with_google(
    db: Session,
    *,
    id_token_value: str,
) -> GoogleLoginResult:
    settings = get_settings()

    try:
        claims = verify_google_id_token(
            id_token_value,
            client_id=settings.google_client_id,
        )

        repository = IdentityRepository(db)

        identity = repository.get_identity_by_provider_subject(
            GOOGLE_PROVIDER,
            claims.subject,
        )

        if identity is None:
            raise GoogleAuthenticationError(
                AUTHENTICATION_FAILED_MESSAGE
            )

        if identity.disabled_at is not None:
            raise GoogleAuthenticationError(
                AUTHENTICATION_FAILED_MESSAGE
            )

        user = repository.get_user(identity.user_id)

        if user is None or user.status != "active":
            raise GoogleAuthenticationError(
                AUTHENTICATION_FAILED_MESSAGE
            )

        now = datetime.now(timezone.utc)
        session_token, token_hash = _generate_session_token()
        session_expires_at = now + SESSION_LIFETIME

        session = IdentitySession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=session_expires_at,
        )
        repository.add_session(session)

        identity.last_used_at = now

        db.flush()
        db.commit()

        return GoogleLoginResult(
            user_id=user.id,
            session_id=session.id,
            session_token=session_token,
            session_expires_at=session_expires_at,
        )

    except GoogleAuthenticationError:
        db.rollback()
        raise
    except GoogleOIDCError:
        db.rollback()
        raise GoogleAuthenticationError(
            AUTHENTICATION_FAILED_MESSAGE
        ) from None
    except IntegrityError:
        db.rollback()
        raise GoogleAuthenticationServiceError(
            AUTHENTICATION_FAILED_MESSAGE
        ) from None
    except Exception:
        db.rollback()
        raise GoogleAuthenticationServiceError(
            AUTHENTICATION_FAILED_MESSAGE
        ) from None
