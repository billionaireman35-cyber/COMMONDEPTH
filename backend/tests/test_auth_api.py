from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models.identity import (
    Device,
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)

client = TestClient(app)


def _email() -> str:
    return f"auth-api-{uuid4()}@example.invalid"


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
                delete(UserIdentity).where(
                    UserIdentity.id.in_(identity_ids)
                )
            )

        db.execute(delete(User).where(User.id == user_id))
        db.commit()
    finally:
        db.close()


def test_register_endpoint_creates_identity_and_session() -> None:
    email = _email()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"  {email.upper()}  ",
            "password": "CommonDepth-Test-Password-2026!",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert set(body) == {
        "user_id",
        "session_id",
        "session_token",
        "session_expires_at",
    }
    assert body["session_token"]

    db = SessionLocal()
    try:
        user = db.get(User, body["user_id"])
        assert user is not None
        assert user.status == "active"

        identity = db.scalar(
            select(UserIdentity).where(
                UserIdentity.user_id == user.id,
            )
        )
        assert identity is not None
        assert identity.provider == "email"
        assert identity.provider_subject == email

        credential = db.scalar(
            select(PasswordCredential).where(
                PasswordCredential.user_identity_id == identity.id,
            )
        )
        assert credential is not None
        assert credential.password_hash != "CommonDepth-Test-Password-2026!"
        assert credential.password_hash != body["session_token"]

        session = db.get(IdentitySession, body["session_id"])
        assert session is not None
        assert session.user_id == user.id
        assert session.token_hash != body["session_token"]
    finally:
        if "body" in locals() and body.get("user_id"):
            _cleanup_user(body["user_id"])
        db.close()


def test_register_endpoint_creates_optional_device() -> None:
    email = _email()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "CommonDepth-Test-Password-2026!",
            "device": {
                "platform": "android",
                "name": "Test Device",
                "device_identifier_hash": "hashed-device-identifier",
            },
        },
    )

    assert response.status_code == 201

    body = response.json()

    db = SessionLocal()
    try:
        device = db.scalar(
            select(Device).where(
                Device.user_id == body["user_id"],
            )
        )

        assert device is not None
        assert device.platform == "android"
        assert device.name == "Test Device"
        assert device.device_identifier_hash == "hashed-device-identifier"
    finally:
        _cleanup_user(body["user_id"])
        db.close()


def test_duplicate_registration_returns_conflict() -> None:
    email = _email()

    first = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "CommonDepth-Test-Password-2026!",
        },
    )

    assert first.status_code == 201

    user_id = first.json()["user_id"]

    try:
        second = client.post(
            "/api/v1/auth/register",
            json={
                "email": f" {email.upper()} ",
                "password": "Another-Valid-Password-2026!",
            },
        )

        assert second.status_code == 409
        assert second.json()["detail"] == "Registration identity already exists."
    finally:
        _cleanup_user(user_id)


def test_invalid_password_returns_bad_request() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": _email(),
            "password": "too-short",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Password does not meet the minimum length."
    )


def test_empty_password_returns_bad_request() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": _email(),
            "password": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid password."


def test_extra_registration_field_is_rejected() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": _email(),
            "password": "CommonDepth-Test-Password-2026!",
            "username": "unexpected",
        },
    )

    assert response.status_code == 422


def test_invalid_device_platform_returns_bad_request() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": _email(),
            "password": "CommonDepth-Test-Password-2026!",
            "device": {
                "platform": "",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid device platform."
