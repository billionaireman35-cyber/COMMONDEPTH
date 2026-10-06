from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.identity import User
from app.services.onboarding import get_curated_follow_suggestions


client = TestClient(app)


def _register(email: str) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "VeryStrongPassword123!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["user_id"], body["session_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_profile(token: str, username: str) -> None:
    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": username},
    )
    assert response.status_code == 201


def test_curated_follow_suggestions_apply_approved_filters() -> None:
    suffix = uuid4().hex[:8]
    viewer_username = f"viewer_{suffix}"
    followed_username = f"followed_{suffix}"
    inactive_username = f"inactive_{suffix}"
    valid_username = f"valid_{suffix}"

    viewer_id, viewer_token = _register(f"viewer-{suffix}@example.com")
    followed_id, followed_token = _register(f"followed-{suffix}@example.com")
    inactive_id, inactive_token = _register(f"inactive-{suffix}@example.com")
    valid_id, valid_token = _register(f"valid-{suffix}@example.com")

    _create_profile(viewer_token, viewer_username)
    _create_profile(followed_token, followed_username)
    _create_profile(inactive_token, inactive_username)
    _create_profile(valid_token, valid_username)

    follow_response = client.post(
        f"/api/v1/social/follow/{followed_username}",
        headers=_auth_header(viewer_token),
    )
    assert follow_response.status_code == 201

    db = SessionLocal()
    try:
        inactive_user = db.get(User, inactive_id)
        assert inactive_user is not None
        inactive_user.status = "suspended"
        db.commit()

        settings = get_settings()
        original = settings.onboarding_curated_usernames
        settings.onboarding_curated_usernames = (
            f"{valid_username},{followed_username},"
            f"{inactive_username},{viewer_username}"
        )

        try:
            suggestions = get_curated_follow_suggestions(
                db,
                viewer_user_id=viewer_id,
            )
        finally:
            settings.onboarding_curated_usernames = original
    finally:
        db.close()

    assert [profile.username for profile in suggestions] == [valid_username]
    assert followed_id != viewer_id
    assert valid_id != viewer_id


def test_curated_follow_suggestions_preserve_private_profile_fields() -> None:
    suffix = uuid4().hex[:8]

    viewer_id, viewer_token = _register(f"viewer-private-{suffix}@example.com")
    _, target_token = _register(f"target-private-{suffix}@example.com")
    target_username = f"private_{suffix}"

    _create_profile(viewer_token, f"viewer_{suffix}")

    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(target_token),
        json={
            "username": target_username,
            "visibility": "private",
            "display_name": "Private Creator",
            "biography": "Private biography",
            "location": "Private Location",
            "banner": "https://example.com/private-banner",
        },
    )
    assert response.status_code == 201

    settings = get_settings()
    original = settings.onboarding_curated_usernames
    settings.onboarding_curated_usernames = target_username

    db = SessionLocal()
    try:
        suggestions = get_curated_follow_suggestions(
            db,
            viewer_user_id=viewer_id,
        )
    finally:
        settings.onboarding_curated_usernames = original
        db.close()

    assert len(suggestions) == 1
    assert suggestions[0].username == target_username
    assert suggestions[0].visibility == "private"


def test_follow_suggestions_endpoint_returns_curated_profiles() -> None:
    suffix = uuid4().hex[:8]
    viewer_id, viewer_token = _register(f"endpoint-viewer-{suffix}@example.com")
    _, target_token = _register(f"endpoint-target-{suffix}@example.com")
    target_username = f"creator_{suffix}"

    _create_profile(viewer_token, f"viewer_{suffix}")
    _create_profile(target_token, target_username)

    settings = get_settings()
    original = settings.onboarding_curated_usernames
    settings.onboarding_curated_usernames = target_username

    try:
        response = client.get(
            "/api/v1/onboarding/follow-suggestions",
            headers=_auth_header(viewer_token),
        )
    finally:
        settings.onboarding_curated_usernames = original

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["username"] == target_username
    assert response.json()[0]["user_id"] != viewer_id


def test_follow_suggestions_endpoint_requires_authentication() -> None:
    response = client.get("/api/v1/onboarding/follow-suggestions")

    assert response.status_code == 401
