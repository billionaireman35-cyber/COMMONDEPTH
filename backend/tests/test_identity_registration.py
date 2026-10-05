import threading
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.identity import (
    Device,
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)
from app.repositories.identity import IdentityRepository
from app.services import identity_registration
from app.services.identity_registration import (
    DeviceRegistrationInput,
    DuplicateIdentityError,
    InvalidRegistrationInputError,
    RegistrationPersistenceConflictError,
    RegistrationResult,
    register_identity,
)


def _email() -> str:
    return f"identity-registration-{uuid4()}@example.invalid"


def _cleanup_user(user_id) -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(IdentitySession).where(IdentitySession.user_id == user_id)
        )
        db.execute(
            delete(Device).where(Device.user_id == user_id)
        )

        identity_ids = db.scalars(
            select(UserIdentity.id).where(UserIdentity.user_id == user_id)
        ).all()

        if identity_ids:
            db.execute(
                delete(PasswordCredential).where(
                    PasswordCredential.user_identity_id.in_(identity_ids)
                )
            )
            db.execute(
                delete(UserIdentity).where(UserIdentity.id.in_(identity_ids))
            )

        db.execute(delete(User).where(User.id == user_id))
        db.commit()
    finally:
        db.close()


def _registration_count(email: str) -> dict[str, int]:
    db = SessionLocal()
    try:
        user_count = db.scalar(select(func.count()).select_from(User).join(
            UserIdentity,
            UserIdentity.user_id == User.id,
        ).where(
            UserIdentity.provider == "email",
            UserIdentity.provider_subject == email,
        ))

        identity_count = db.scalar(
            select(func.count()).select_from(UserIdentity).where(
                UserIdentity.provider == "email",
                UserIdentity.provider_subject == email,
            )
        )

        credential_count = db.scalar(
            select(func.count())
            .select_from(PasswordCredential)
            .join(
                UserIdentity,
                PasswordCredential.user_identity_id == UserIdentity.id,
            )
            .where(
                UserIdentity.provider == "email",
                UserIdentity.provider_subject == email,
            )
        )

        session_count = db.scalar(
            select(func.count())
            .select_from(IdentitySession)
            .join(
                User,
                IdentitySession.user_id == User.id,
            )
            .join(
                UserIdentity,
                UserIdentity.user_id == User.id,
            )
            .where(
                UserIdentity.provider == "email",
                UserIdentity.provider_subject == email,
            )
        )

        return {
            "users": int(user_count or 0),
            "identities": int(identity_count or 0),
            "credentials": int(credential_count or 0),
            "sessions": int(session_count or 0),
        }
    finally:
        db.close()


def test_successful_registration() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"

    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=email,
            password=password,
        )

        assert isinstance(result, RegistrationResult)
        assert result.user_id is not None
        assert result.session_id is not None
        assert result.session_token
        assert result.session_expires_at.tzinfo is not None

        user = db.get(User, result.user_id)
        assert user is not None

        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == result.user_id,
            )
        )
        assert identity is not None
        assert identity.provider == "email"
        assert identity.provider_subject == email
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_normalized_email_identity() -> None:
    email = _email()
    supplied_email = f"  {email.upper()}  "

    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=supplied_email,
            password="CommonDepth-Test-Password-2026!",
        )

        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == result.user_id,
            )
        )

        assert identity is not None
        assert identity.provider_subject == email
        assert identity.provider_subject != supplied_email

        plus_email = f"{uuid4()}+tag@example.invalid"
        plus_result = register_identity(
            db,
            email=plus_email,
            password="CommonDepth-Test-Password-2026!",
        )

        plus_identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == plus_result.user_id,
            )
        )
        assert plus_identity is not None
        assert plus_identity.provider_subject == plus_email

        _cleanup_user(result.user_id)
        _cleanup_user(plus_result.user_id)
    finally:
        db.close()


def test_12_character_password_is_accepted() -> None:
    email = _email()

    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=email,
            password="123456789012",
        )
        assert result.user_id is not None
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


@pytest.mark.parametrize(
    "password",
    [
        "",
    ],
)
def test_empty_password_is_rejected(password: str) -> None:
    db = SessionLocal()
    try:
        with pytest.raises(InvalidRegistrationInputError):
            register_identity(
                db,
                email=_email(),
                password=password,
            )
    finally:
        db.close()


def test_password_below_minimum_is_rejected() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(InvalidRegistrationInputError):
            register_identity(
                db,
                email=_email(),
                password="12345678901",
            )
    finally:
        db.close()


def test_password_above_maximum_is_rejected() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(InvalidRegistrationInputError):
            register_identity(
                db,
                email=_email(),
                password="x" * 129,
            )
    finally:
        db.close()


def test_password_hash_is_not_plaintext() -> None:
    email = _email()
    password = "CommonDepth-Test-Password-2026!"

    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=email,
            password=password,
        )

        credential = db.scalar(
            select(PasswordCredential)
            .join(
                UserIdentity,
                PasswordCredential.user_identity_id == UserIdentity.id,
            )
            .where(UserIdentity.user_id == result.user_id)
        )

        assert credential is not None
        assert credential.password_hash != password
        assert password not in credential.password_hash
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_user_starts_active() -> None:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        user = db.get(User, result.user_id)

        assert user is not None
        assert user.status == "active"
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_user_identity_references_user() -> None:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == result.user_id,
            )
        )

        assert identity is not None
        assert identity.user_id == result.user_id
        assert db.get(User, identity.user_id) is not None
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_password_credential_references_user_identity() -> None:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        credential = db.scalar(
            select(PasswordCredential)
            .join(
                UserIdentity,
                PasswordCredential.user_identity_id == UserIdentity.id,
            )
            .where(UserIdentity.user_id == result.user_id)
        )

        assert credential is not None

        identity = db.get(UserIdentity, credential.user_identity_id)
        assert identity is not None
        assert identity.user_id == result.user_id
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_optional_device_references_user() -> None:
    email = _email()

    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=email,
            password="CommonDepth-Test-Password-2026!",
            device=DeviceRegistrationInput(
                platform="android",
                name="CommonDepth Test Device",
                device_identifier_hash="test-device-hash",
            ),
        )

        device = db.scalar(
            select(Device).where(Device.user_id == result.user_id)
        )

        assert device is not None
        assert device.user_id == result.user_id
        assert device.platform == "android"
        assert device.name == "CommonDepth Test Device"
        assert device.device_identifier_hash == "test-device-hash"
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_authenticated_session_is_created() -> None:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        session = db.get(IdentitySession, result.session_id)

        assert session is not None
        assert session.user_id == result.user_id
        assert session.revoked_at is None
        assert session.expires_at > session.created_at
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_session_expires_in_30_days() -> None:
    db = SessionLocal()
    try:
        before = datetime.now(timezone.utc)

        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=30)
        expected_max = after + timedelta(days=30)

        assert expected_min <= result.session_expires_at <= expected_max
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_raw_session_token_is_not_persisted() -> None:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        session = db.get(IdentitySession, result.session_id)

        assert session is not None
        assert session.token_hash != result.session_token
        assert session.token_hash == sha256(
            result.session_token.encode("utf-8")
        ).hexdigest()
        assert result.session_token not in session.token_hash
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()


def test_duplicate_identity_is_rejected() -> None:
    email = _email()
    db = SessionLocal()

    try:
        first = register_identity(
            db,
            email=email,
            password="CommonDepth-Test-Password-2026!",
        )

        with pytest.raises(DuplicateIdentityError):
            register_identity(
                db,
                email=email.upper(),
                password="Another-Password-2026!",
            )

        counts = _registration_count(email)

        assert counts["users"] == 1
        assert counts["identities"] == 1
        assert counts["credentials"] == 1
        assert counts["sessions"] == 1
    finally:
        if "first" in locals():
            _cleanup_user(first.user_id)
        db.close()


def test_transaction_rolls_back_on_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _email()

    def fail_hash_password(password: str) -> str:
        raise RuntimeError("forced test failure")

    monkeypatch.setattr(
        identity_registration,
        "hash_password",
        fail_hash_password,
    )

    db = SessionLocal()
    try:
        with pytest.raises(identity_registration.RegistrationServiceError):
            register_identity(
                db,
                email=email,
                password="CommonDepth-Test-Password-2026!",
            )

        assert _registration_count(email) == {
            "users": 0,
            "identities": 0,
            "credentials": 0,
            "sessions": 0,
        }
    finally:
        db.close()


def test_no_partial_registration_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _email()

    original_add_session = IdentityRepository.add_session

    def fail_session_persistence(
        repository: IdentityRepository,
        session: IdentitySession,
    ) -> IdentitySession:
        raise RuntimeError("forced session persistence failure")

    monkeypatch.setattr(
        IdentityRepository,
        "add_session",
        fail_session_persistence,
    )

    db = SessionLocal()
    try:
        with pytest.raises(identity_registration.RegistrationServiceError):
            register_identity(
                db,
                email=email,
                password="CommonDepth-Test-Password-2026!",
            )

        assert _registration_count(email) == {
            "users": 0,
            "identities": 0,
            "credentials": 0,
            "sessions": 0,
        }
    finally:
        monkeypatch.setattr(
            IdentityRepository,
            "add_session",
            original_add_session,
        )
        db.close()


def test_concurrent_duplicate_registration_allows_only_one_user() -> None:
    email = _email()
    barrier = threading.Barrier(2)
    results: list[RegistrationResult] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def attempt() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)

            result = register_identity(
                db,
                email=email,
                password="CommonDepth-Test-Password-2026!",
            )

            with lock:
                results.append(result)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            db.close()

    first = threading.Thread(target=attempt)
    second = threading.Thread(target=attempt)

    first.start()
    second.start()
    first.join(timeout=30)
    second.join(timeout=30)

    assert not first.is_alive()
    assert not second.is_alive()

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(
        errors[0],
        (DuplicateIdentityError, RegistrationPersistenceConflictError),
    )

    counts = _registration_count(email)

    assert counts["users"] == 1
    assert counts["identities"] == 1
    assert counts["credentials"] == 1
    assert counts["sessions"] == 1

    _cleanup_user(results[0].user_id)


def test_database_integrity_error_is_translated_to_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = _email()

    original_get_identity = IdentityRepository.get_identity_by_provider_subject

    def hide_existing_identity(
        repository: IdentityRepository,
        provider: str,
        provider_subject: str,
    ):
        return None

    monkeypatch.setattr(
        IdentityRepository,
        "get_identity_by_provider_subject",
        hide_existing_identity,
    )

    db = SessionLocal()

    try:
        existing = User(status="active")
        db.add(existing)
        db.flush()

        existing_identity = UserIdentity(
            user_id=existing.id,
            provider="email",
            provider_subject=email,
        )
        db.add(existing_identity)
        db.commit()

        with pytest.raises(RegistrationPersistenceConflictError):
            register_identity(
                db,
                email=email,
                password="CommonDepth-Test-Password-2026!",
            )

        assert _registration_count(email) == {
            "users": 1,
            "identities": 1,
            "credentials": 0,
            "sessions": 0,
        }
    finally:
        monkeypatch.setattr(
            IdentityRepository,
            "get_identity_by_provider_subject",
            original_get_identity,
        )
        db.rollback()

        cleanup = SessionLocal()
        try:
            cleanup.execute(
                delete(UserIdentity).where(
                    UserIdentity.user_id == existing.id
                )
            )
            cleanup.execute(delete(User).where(User.id == existing.id))
            cleanup.commit()
        finally:
            cleanup.close()

        db.close()


def test_registration_result_contains_no_sensitive_information() -> None:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=_email(),
            password="CommonDepth-Test-Password-2026!",
        )

        public_fields = set(vars(result))

        assert public_fields == {
            "user_id",
            "session_id",
            "session_token",
            "session_expires_at",
        }

        assert not hasattr(result, "password")
        assert not hasattr(result, "password_hash")
        assert not hasattr(result, "provider_secret")
        assert not hasattr(result, "private_key")
        assert not hasattr(result, "seed_phrase")
        assert not hasattr(result, "wallet_credentials")
        assert not hasattr(result, "device_identifier_hash")
    finally:
        if "result" in locals():
            _cleanup_user(result.user_id)
        db.close()
