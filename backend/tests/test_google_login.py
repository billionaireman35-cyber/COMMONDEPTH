from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.identity import (
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)
from app.services.google_login import (
    GoogleAuthenticationError,
    GoogleLoginResult,
    login_with_google,
)
from app.services.identity_registration import register_identity


def _email() -> str:
    return f"google-login-{uuid4()}@example.invalid"


def _cleanup_user(user_id) -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(IdentitySession).where(
                IdentitySession.user_id == user_id
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

        db.execute(delete(User).where(User.id == user_id))
        db.commit()
    finally:
        db.close()


def _create_google_user(
    *,
    subject: str,
    email: str | None = None,
) -> tuple:
    db = SessionLocal()
    try:
        user = User(status="active")
        db.add(user)
        db.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=subject,
        )
        db.add(identity)

        if email is not None:
            email_identity = UserIdentity(
                user_id=user.id,
                provider="email",
                provider_subject=email,
            )
            db.add(email_identity)

        db.commit()
        return user.id
    finally:
        db.close()


def _google_claims(subject: str, email: str | None = None):
    return type(
        "Claims",
        (),
        {
            "subject": subject,
            "email": email,
            "email_verified": True,
        },
    )()


def test_successful_google_login_creates_session() -> None:
    subject = f"google-sub-{uuid4()}"
    user_id = _create_google_user(subject=subject)

    db = SessionLocal()
    try:
        with patch(
            "app.services.google_login.verify_google_id_token",
            return_value=_google_claims(subject),
        ):
            result = login_with_google(
                db,
                id_token_value="valid-google-token",
            )

        assert isinstance(result, GoogleLoginResult)
        assert result.user_id == user_id
        assert result.session_token
        assert result.session_expires_at.tzinfo is not None

        session = db.get(IdentitySession, result.session_id)
        assert session is not None
        assert session.user_id == user_id
        assert session.revoked_at is None
        assert session.token_hash == sha256(
            result.session_token.encode("utf-8")
        ).hexdigest()
        assert session.token_hash != result.session_token
    finally:
        _cleanup_user(user_id)
        db.close()


def test_google_login_session_expires_in_30_days() -> None:
    subject = f"google-sub-{uuid4()}"
    user_id = _create_google_user(subject=subject)

    db = SessionLocal()
    try:
        before = datetime.now(timezone.utc)

        with patch(
            "app.services.google_login.verify_google_id_token",
            return_value=_google_claims(subject),
        ):
            result = login_with_google(
                db,
                id_token_value="valid-google-token",
            )

        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=30)
        expected_max = after + timedelta(days=30)

        assert expected_min <= result.session_expires_at <= expected_max
    finally:
        _cleanup_user(user_id)
        db.close()


def test_unknown_google_subject_is_rejected() -> None:
    db = SessionLocal()
    try:
        with patch(
            "app.services.google_login.verify_google_id_token",
            return_value=_google_claims("unknown-google-subject"),
        ):
            with pytest.raises(GoogleAuthenticationError) as exc_info:
                login_with_google(
                    db,
                    id_token_value="valid-google-token",
                )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        db.close()


def test_disabled_google_identity_is_rejected() -> None:
    subject = f"google-sub-{uuid4()}"
    user_id = _create_google_user(subject=subject)

    db = SessionLocal()
    try:
        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == user_id,
                UserIdentity.provider == "google",
            )
        )
        assert identity is not None

        identity.disabled_at = datetime.now(timezone.utc)
        db.commit()

        with patch(
            "app.services.google_login.verify_google_id_token",
            return_value=_google_claims(subject),
        ):
            with pytest.raises(GoogleAuthenticationError) as exc_info:
                login_with_google(
                    db,
                    id_token_value="valid-google-token",
                )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        _cleanup_user(user_id)
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
def test_non_active_user_cannot_login_with_google(
    user_status: str,
) -> None:
    subject = f"google-sub-{uuid4()}"
    user_id = _create_google_user(subject=subject)

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        assert user is not None
        user.status = user_status
        db.commit()

        with patch(
            "app.services.google_login.verify_google_id_token",
            return_value=_google_claims(subject),
        ):
            with pytest.raises(GoogleAuthenticationError) as exc_info:
                login_with_google(
                    db,
                    id_token_value="valid-google-token",
                )

        assert str(exc_info.value) == "Authentication failed."
    finally:
        _cleanup_user(user_id)
        db.close()


def test_google_email_match_does_not_automatically_merge() -> None:
    email = _email()

    registration_db = SessionLocal()
    try:
        registration = register_identity(
            registration_db,
            email=email,
            password="CommonDepth-Test-Password-2026!",
        )
        email_user_id = registration.user_id
    finally:
        registration_db.close()

    google_subject = f"google-sub-{uuid4()}"

    try:
        db = SessionLocal()

        with patch(
            "app.services.google_login.verify_google_id_token",
            return_value=_google_claims(
                google_subject,
                email=email,
            ),
        ):
            with pytest.raises(GoogleAuthenticationError) as exc_info:
                login_with_google(
                    db,
                    id_token_value="valid-google-token",
                )

        assert str(exc_info.value) == "Authentication failed."

        assert db.scalar(
            select(UserIdentity).where(
                UserIdentity.provider == "google",
                UserIdentity.provider_subject == google_subject,
            )
        ) is None
    finally:
        db.close()
        _cleanup_user(email_user_id)
