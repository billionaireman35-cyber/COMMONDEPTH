from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.identity import (
    Device,
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)
from app.services.identity_registration import register_identity
from app.services.identity_login import (
    AuthenticationError,
    DeviceLoginInput,
    LoginResult,
    login_identity,
)


def _email() -> str:
    return f"identity-login-{uuid4()}@example.invalid"


def _cleanup_user(user_id) -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(IdentitySession).where(
                IdentitySession.user_id == user_id
            )
        )
        db.execute(
            delete(Device).where(
                Device.user_id == user_id
            )
        )

        identity_ids = db.scalars(
            select(UserIdentity.id).where(
                UserIdentity.user_id == user_id
            )
        ).all()

        if identity_ids:
            db.execute(
                delete(PasswordCredential).where(
                    PasswordCredential.user_identity_id.in_(identity_ids)
                )
            )
            db.execute(
                delete(UserIdentity).where(
                    UserIdentity.id.in_(identity_ids)
                )
            )

        db.execute(
            delete(User).where(User.id == user_id)
        )
        db.commit()
    finally:
        db.close()


def _register(email: str, password: str = "CommonDepth-Test-Password-2026!"):
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=email,
            password=password,
        )
        return result.user_id
    finally:
        db.close()


def test_successful_email_login() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        result = login_identity(
            db,
            email=email,
            password=password,
        )

        assert isinstance(result, LoginResult)
        assert result.user_id == user_id
        assert result.session_id is not None
        assert result.session_token
        assert result.session_expires_at.tzinfo is not None
    finally:
        _cleanup_user(user_id)
        db.close()


def test_email_is_normalized_before_login() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        result = login_identity(
            db,
            email=f"  {email.upper()}  ",
            password=password,
        )

        assert result.user_id == user_id
    finally:
        _cleanup_user(user_id)
        db.close()


def test_wrong_password_returns_generic_authentication_error() -> None:
    email = _email()
    user_id = _register(email)

    db = SessionLocal()
    try:
        with pytest.raises(AuthenticationError) as exc_info:
            login_identity(
                db,
                email=email,
                password="Definitely-Wrong-Password-2026!",
            )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        _cleanup_user(user_id)
        db.close()


def test_unknown_email_returns_same_generic_authentication_error() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(AuthenticationError) as exc_info:
            login_identity(
                db,
                email=_email(),
                password="CommonDepth-Test-Password-2026!",
            )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        db.close()


@pytest.mark.parametrize(
    "user_status",
    [
        "suspended",
        "deactivated",
        "pending_deletion",
        "deleted",
    ],
)
def test_non_active_user_cannot_login(user_status: str) -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        assert user is not None
        user.status = user_status
        db.commit()

        with pytest.raises(AuthenticationError) as exc_info:
            login_identity(
                db,
                email=email,
                password=password,
            )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        _cleanup_user(user_id)
        db.close()


def test_disabled_email_identity_cannot_login() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == user_id,
                UserIdentity.provider == "email",
            )
        )
        assert identity is not None

        identity.disabled_at = datetime.now(timezone.utc)
        db.commit()

        with pytest.raises(AuthenticationError) as exc_info:
            login_identity(
                db,
                email=email,
                password=password,
            )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        _cleanup_user(user_id)
        db.close()


def test_missing_password_credential_cannot_login() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == user_id,
                UserIdentity.provider == "email",
            )
        )
        assert identity is not None

        credential = db.get(
            PasswordCredential,
            identity.id,
        )
        assert credential is not None

        db.delete(credential)
        db.commit()

        with pytest.raises(AuthenticationError) as exc_info:
            login_identity(
                db,
                email=email,
                password=password,
            )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        _cleanup_user(user_id)
        db.close()


def test_successful_login_creates_new_session() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    registration_user_id = _register(email, password)

    db = SessionLocal()
    try:
        existing_sessions = db.scalars(
            select(IdentitySession).where(
                IdentitySession.user_id == registration_user_id
            )
        ).all()

        result = login_identity(
            db,
            email=email,
            password=password,
        )

        assert result.user_id == registration_user_id
        assert result.session_id not in {
            session.id for session in existing_sessions
        }

        session = db.get(IdentitySession, result.session_id)
        assert session is not None
        assert session.user_id == registration_user_id
        assert session.revoked_at is None
    finally:
        _cleanup_user(registration_user_id)
        db.close()


def test_login_session_expires_in_30_days() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        before = datetime.now(timezone.utc)

        result = login_identity(
            db,
            email=email,
            password=password,
        )

        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=30)
        expected_max = after + timedelta(days=30)

        assert expected_min <= result.session_expires_at <= expected_max
    finally:
        _cleanup_user(user_id)
        db.close()


def test_raw_login_session_token_is_not_persisted() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        result = login_identity(
            db,
            email=email,
            password=password,
        )

        session = db.get(
            IdentitySession,
            result.session_id,
        )
        assert session is not None

        assert session.token_hash != result.session_token
        assert session.token_hash == sha256(
            result.session_token.encode("utf-8")
        ).hexdigest()
        assert result.session_token not in session.token_hash
    finally:
        _cleanup_user(user_id)
        db.close()


def test_successful_login_updates_identity_last_used_at() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == user_id,
                UserIdentity.provider == "email",
            )
        )
        assert identity is not None
        assert identity.last_used_at is None

        result = login_identity(
            db,
            email=email,
            password=password,
        )

        db.refresh(identity)

        assert identity.last_used_at is not None
        assert identity.last_used_at.tzinfo is not None
        assert identity.last_used_at <= result.session_expires_at
    finally:
        _cleanup_user(user_id)
        db.close()


def test_successful_login_does_not_update_user_last_seen_at() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        assert user is not None
        assert user.last_seen_at is None

        login_identity(
            db,
            email=email,
            password=password,
        )

        db.refresh(user)

        assert user.last_seen_at is None
    finally:
        _cleanup_user(user_id)
        db.close()


def test_login_with_device_creates_device_and_associates_session() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"
    user_id = _register(email, password)

    db = SessionLocal()
    try:
        result = login_identity(
            db,
            email=email,
            password=password,
            device=DeviceLoginInput(
                platform="android",
                name="CommonDepth Login Device",
                device_identifier_hash="login-device-hash",
            ),
        )

        device = db.scalar(
            select(Device).where(
                Device.user_id == user_id,
                Device.device_identifier_hash == "login-device-hash",
            )
        )
        assert device is not None
        assert device.platform == "android"
        assert device.name == "CommonDepth Login Device"

        session = db.get(
            IdentitySession,
            result.session_id,
        )
        assert session is not None
        assert session.device_id == device.id
    finally:
        _cleanup_user(user_id)
        db.close()
