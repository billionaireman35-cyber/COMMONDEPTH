from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import (
    Device,
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)
from app.repositories.identity import IdentityRepository
from app.services.password import verify_password


SESSION_LIFETIME = timedelta(days=30)
EMAIL_PROVIDER = "email"
AUTHENTICATION_FAILED_MESSAGE = "Authentication failed."


class AuthenticationError(Exception):
    """Raised when authentication cannot be completed successfully."""


class AuthenticationServiceError(AuthenticationError):
    """Raised when an unexpected authentication failure occurs."""


@dataclass(frozen=True)
class DeviceLoginInput:
    platform: str
    name: str | None = None
    device_identifier_hash: str | None = None


@dataclass(frozen=True)
class LoginResult:
    user_id: UUID
    session_id: UUID
    session_token: str
    session_expires_at: datetime


def _normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    normalized = email.strip().lower()

    if not normalized:
        raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    return normalized


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or not password:
        raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)


def _validate_device(device: DeviceLoginInput | None) -> None:
    if device is None:
        return

    if not isinstance(device.platform, str) or not device.platform.strip():
        raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    if len(device.platform) > 64:
        raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    if device.name is not None:
        if not isinstance(device.name, str):
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)
        if len(device.name) > 128:
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

    if device.device_identifier_hash is not None:
        if not isinstance(device.device_identifier_hash, str):
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)
        if len(device.device_identifier_hash) > 512:
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)


def _generate_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode("utf-8")).hexdigest()
    return token, token_hash


def login_identity(
    db: Session,
    *,
    email: str,
    password: str,
    device: DeviceLoginInput | None = None,
) -> LoginResult:
    """
    Authenticate an email/password identity and create a new session.

    Authentication failures intentionally use one generic external error
    so callers cannot distinguish unknown identities, disabled identities,
    inactive users, missing credentials, or incorrect passwords.
    """
    normalized_email = _normalize_email(email)
    _validate_password(password)
    _validate_device(device)

    repository = IdentityRepository(db)

    try:
        identity = repository.get_identity_by_provider_subject(
            EMAIL_PROVIDER,
            normalized_email,
        )

        if identity is None:
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

        if identity.disabled_at is not None:
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

        user = repository.get_user(identity.user_id)

        if user is None or user.status != "active":
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

        credential = db.get(PasswordCredential, identity.id)

        if credential is None:
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

        if not verify_password(password, credential.password_hash):
            raise AuthenticationError(AUTHENTICATION_FAILED_MESSAGE)

        now = datetime.now(timezone.utc)
        session_token, token_hash = _generate_session_token()
        session_expires_at = now + SESSION_LIFETIME

        created_device: Device | None = None

        if device is not None:
            created_device = Device(
                user_id=user.id,
                device_identifier_hash=device.device_identifier_hash,
                platform=device.platform.strip(),
                name=device.name,
            )
            repository.add_device(created_device)
            db.flush()

        session = IdentitySession(
            user_id=user.id,
            device_id=created_device.id if created_device is not None else None,
            token_hash=token_hash,
            expires_at=session_expires_at,
        )
        repository.add_session(session)

        identity.last_used_at = now

        db.flush()
        db.commit()

        return LoginResult(
            user_id=user.id,
            session_id=session.id,
            session_token=session_token,
            session_expires_at=session_expires_at,
        )

    except AuthenticationError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise AuthenticationServiceError(
            AUTHENTICATION_FAILED_MESSAGE
        ) from None
    except Exception:
        db.rollback()
        raise AuthenticationServiceError(
            AUTHENTICATION_FAILED_MESSAGE
        ) from None
