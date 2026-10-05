from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import Device, PasswordCredential, Session as IdentitySession, User, UserIdentity
from app.repositories.identity import IdentityRepository
from app.services.password import hash_password


PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
SESSION_LIFETIME = timedelta(days=30)
EMAIL_PROVIDER = "email"


class RegistrationError(Exception):
    """Base class for safe identity-registration service errors."""


class InvalidRegistrationInputError(RegistrationError):
    """Raised when registration input violates the service contract."""


class DuplicateIdentityError(RegistrationError):
    """Raised when the requested authentication identity already exists."""


class RegistrationPersistenceConflictError(RegistrationError):
    """Raised when persistence fails because of an integrity conflict."""


class RegistrationServiceError(RegistrationError):
    """Raised when an unexpected registration failure occurs."""


@dataclass(frozen=True)
class DeviceRegistrationInput:
    platform: str
    name: str | None = None
    device_identifier_hash: str | None = None


@dataclass(frozen=True)
class RegistrationResult:
    user_id: UUID
    session_id: UUID
    session_token: str
    session_expires_at: datetime


def _normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise InvalidRegistrationInputError("Invalid email.")

    normalized = email.strip().lower()

    if not normalized:
        raise InvalidRegistrationInputError("Invalid email.")

    return normalized


def _validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise InvalidRegistrationInputError("Invalid password.")

    if not password:
        raise InvalidRegistrationInputError("Invalid password.")

    if len(password) < PASSWORD_MIN_LENGTH:
        raise InvalidRegistrationInputError("Password does not meet the minimum length.")

    if len(password) > PASSWORD_MAX_LENGTH:
        raise InvalidRegistrationInputError("Password exceeds the maximum length.")


def _validate_device(device: DeviceRegistrationInput | None) -> None:
    if device is None:
        return

    if not isinstance(device.platform, str) or not device.platform.strip():
        raise InvalidRegistrationInputError("Invalid device platform.")

    if len(device.platform) > 64:
        raise InvalidRegistrationInputError("Device platform is too long.")

    if device.name is not None:
        if not isinstance(device.name, str):
            raise InvalidRegistrationInputError("Invalid device name.")
        if len(device.name) > 128:
            raise InvalidRegistrationInputError("Device name is too long.")

    if device.device_identifier_hash is not None:
        if not isinstance(device.device_identifier_hash, str):
            raise InvalidRegistrationInputError("Invalid device identifier hash.")
        if len(device.device_identifier_hash) > 512:
            raise InvalidRegistrationInputError(
                "Device identifier hash is too long."
            )


def _generate_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode("utf-8")).hexdigest()
    return token, token_hash


def register_identity(
    db: Session,
    *,
    email: str,
    password: str,
    device: DeviceRegistrationInput | None = None,
) -> RegistrationResult:
    """
    Execute one complete email/password registration transaction.

    The service owns commit/rollback. The repository only performs
    persistence operations.
    """
    normalized_email = _normalize_email(email)
    _validate_password(password)
    _validate_device(device)

    repository = IdentityRepository(db)

    try:
        existing_identity = repository.get_identity_by_provider_subject(
            EMAIL_PROVIDER,
            normalized_email,
        )
        if existing_identity is not None:
            raise DuplicateIdentityError("Registration identity already exists.")

        password_hash = hash_password(password)
        now = datetime.now(timezone.utc)
        session_token, token_hash = _generate_session_token()
        session_expires_at = now + SESSION_LIFETIME

        user = User(status="active")
        repository.add_user(user)
        db.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider=EMAIL_PROVIDER,
            provider_subject=normalized_email,
        )
        repository.add_identity(identity)
        db.flush()

        credential = PasswordCredential(
            user_identity_id=identity.id,
            password_hash=password_hash,
            password_changed_at=now,
        )
        repository.add_password_credential(credential)

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
        db.flush()

        db.commit()

        return RegistrationResult(
            user_id=user.id,
            session_id=session.id,
            session_token=session_token,
            session_expires_at=session_expires_at,
        )

    except DuplicateIdentityError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise RegistrationPersistenceConflictError(
            "Registration could not be completed."
        ) from None
    except RegistrationError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise RegistrationServiceError(
            "Registration could not be completed."
        ) from None
