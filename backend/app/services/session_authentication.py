from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy.orm import Session as DatabaseSession

from app.models.identity import Session as IdentitySession
from app.models.identity import User


AUTHENTICATION_FAILED_MESSAGE = "Authentication failed."
LOGOUT_REVOKE_REASON = "logout"


class SessionAuthenticationError(Exception):
    """Raised when a session cannot authenticate a request."""


@dataclass(frozen=True)
class AuthenticatedSession:
    session_id: UUID
    user_id: UUID
    session_expires_at: datetime


def _hash_session_token(session_token: str) -> str:
    return sha256(session_token.encode("utf-8")).hexdigest()


def authenticate_session(
    db: DatabaseSession,
    *,
    session_token: str,
) -> AuthenticatedSession:
    """
    Authenticate an opaque session token.

    Only the SHA-256 token hash is persisted. Unknown, expired, revoked,
    or otherwise unusable sessions intentionally produce the same error.
    """
    if not isinstance(session_token, str) or not session_token:
        raise SessionAuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    token_hash = _hash_session_token(session_token)

    session = db.query(IdentitySession).filter(
        IdentitySession.token_hash == token_hash,
    ).first()

    if session is None:
        raise SessionAuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    now = datetime.now(timezone.utc)

    if session.revoked_at is not None:
        raise SessionAuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    if session.expires_at <= now:
        raise SessionAuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    user = db.get(User, session.user_id)

    if user is None or user.status != "active":
        raise SessionAuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    session.last_used_at = now
    db.commit()

    return AuthenticatedSession(
        session_id=session.id,
        user_id=user.id,
        session_expires_at=session.expires_at,
    )


def revoke_session(
    db: DatabaseSession,
    *,
    session_token: str,
) -> None:
    """
    Revoke the session represented by an opaque session token.

    Logout is intentionally idempotent: an unknown, expired, or already
    revoked token does not reveal session state to the caller.
    """
    if not isinstance(session_token, str) or not session_token:
        return

    token_hash = _hash_session_token(session_token)

    session = db.query(IdentitySession).filter(
        IdentitySession.token_hash == token_hash,
    ).first()

    if session is None:
        return

    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoke_reason = LOGOUT_REVOKE_REASON
        db.commit()
