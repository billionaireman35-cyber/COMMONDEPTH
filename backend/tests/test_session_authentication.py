from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.identity import (
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)
from app.services.identity_registration import register_identity
from app.services.session_authentication import (
    SessionAuthenticationError,
    authenticate_session,
    revoke_session,
)


def _email() -> str:
    return f"session-auth-{uuid4()}@example.invalid"


def _cleanup_user(user_id) -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(IdentitySession).where(
                IdentitySession.user_id == user_id,
            )
        )

        from sqlalchemy import select

        identity_ids = db.scalars(
            select(UserIdentity.id).where(
                UserIdentity.user_id == user_id,
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


def _register():
    db = SessionLocal()
    result = register_identity(
        db,
        email=_email(),
        password="CommonDepth-Test-Password-2026!",
    )
    db.close()
    return result


def test_valid_session_authenticates_and_updates_last_used_at() -> None:
    result = _register()

    try:
        db = SessionLocal()
        try:
            session = db.get(IdentitySession, result.session_id)
            assert session is not None
            assert session.last_used_at is None

            authenticated = authenticate_session(
                db,
                session_token=result.session_token,
            )

            assert authenticated.session_id == result.session_id
            assert authenticated.user_id == result.user_id
            assert authenticated.session_expires_at == session.expires_at

            db.refresh(session)
            assert session.last_used_at is not None
        finally:
            db.close()
    finally:
        _cleanup_user(result.user_id)


def test_unknown_session_token_is_generic_authentication_failure() -> None:
    with pytest.raises(SessionAuthenticationError) as exc_info:
        db = SessionLocal()
        try:
            authenticate_session(
                db,
                session_token="unknown-session-token",
            )
        finally:
            db.close()

    assert str(exc_info.value) == "Authentication failed."


def test_raw_token_is_hashed_before_lookup() -> None:
    result = _register()

    try:
        db = SessionLocal()
        try:
            session = db.get(IdentitySession, result.session_id)
            assert session is not None
            assert session.token_hash == sha256(
                result.session_token.encode("utf-8")
            ).hexdigest()
        finally:
            db.close()
    finally:
        _cleanup_user(result.user_id)


def test_expired_session_is_rejected() -> None:
    result = _register()

    try:
        db = SessionLocal()
        try:
            session = db.get(IdentitySession, result.session_id)
            assert session is not None
            session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

            with pytest.raises(SessionAuthenticationError):
                authenticate_session(
                    db,
                    session_token=result.session_token,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(result.user_id)


def test_revoked_session_is_rejected() -> None:
    result = _register()

    try:
        db = SessionLocal()
        try:
            revoke_session(
                db,
                session_token=result.session_token,
            )

            session = db.get(IdentitySession, result.session_id)
            assert session is not None
            assert session.revoked_at is not None
            assert session.revoke_reason == "logout"

            with pytest.raises(SessionAuthenticationError):
                authenticate_session(
                    db,
                    session_token=result.session_token,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(result.user_id)


def test_logout_is_idempotent() -> None:
    result = _register()

    try:
        db = SessionLocal()
        try:
            revoke_session(
                db,
                session_token=result.session_token,
            )

            first = db.get(IdentitySession, result.session_id)
            assert first is not None
            first_revoked_at = first.revoked_at

            revoke_session(
                db,
                session_token=result.session_token,
            )

            db.refresh(first)
            assert first.revoked_at == first_revoked_at
            assert first.revoke_reason == "logout"
        finally:
            db.close()
    finally:
        _cleanup_user(result.user_id)


@pytest.mark.parametrize(
    "status",
    [
        "suspended",
        "deactivated",
        "pending_deletion",
        "deleted",
    ],
)
def test_non_active_user_cannot_authenticate_session(status: str) -> None:
    result = _register()

    try:
        db = SessionLocal()
        try:
            user = db.get(User, result.user_id)
            assert user is not None
            user.status = status
            db.commit()

            with pytest.raises(SessionAuthenticationError):
                authenticate_session(
                    db,
                    session_token=result.session_token,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(result.user_id)
