from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.identity import Session as IdentitySession
from app.models.identity import User
from app.models.profile import Profile
from app.services.profile_verification import (
    ProfileNotFoundForVerificationError,
    verify_profile,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_profiles() -> None:
    db = SessionLocal()
    try:
        db.query(Profile).delete()
        db.commit()
    finally:
        db.close()


def _db() -> Session:
    return SessionLocal()


def _register(
    *,
    email: str | None = None,
    password: str = "VeryStrongPassword123!",
) -> tuple[str, str]:
    email = email or f"user-{uuid4()}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201
    body = response.json()

    return body["user_id"], body["session_token"]


def _auth_header(session_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_token}"}


def test_create_profile_accepts_two_character_username() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": "ai"},
    )

    assert response.status_code == 201
    assert response.json()["username"] == "ai"


def test_create_profile_normalizes_username() -> None:
    user_id, token = _register()

    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "  Alice_123  ",
            "display_name": "Alice",
        },
    )

    assert response.status_code == 201
    body = response.json()

    assert body["user_id"] == user_id
    assert body["username"] == "alice_123"
    assert body["display_name"] == "Alice"
    assert body["visibility"] == "public"


def test_create_profile_rejects_invalid_username() -> None:
    _, token = _register()

    for username in (
        "a" * 31,
        "1alice",
        "alice-name",
        "alice name",
        "_alice",
    ):
        response = client.post(
            "/api/v1/profiles",
            headers=_auth_header(token),
            json={"username": username},
        )

        assert response.status_code == 400


def test_create_profile_requires_authentication() -> None:
    response = client.post(
        "/api/v1/profiles",
        json={"username": "alice"},
    )

    assert response.status_code == 401


def test_get_my_profile_requires_authentication() -> None:
    response = client.get("/api/v1/profiles/me")

    assert response.status_code == 401


def test_patch_profile_requires_authentication() -> None:
    response = client.patch(
        "/api/v1/profiles/me",
        json={"display_name": "Alice"},
    )

    assert response.status_code == 401


def test_duplicate_profile_returns_conflict() -> None:
    _, token = _register()

    first = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": "alice"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": "anotheralice"},
    )
    assert second.status_code == 409


def test_duplicate_username_returns_conflict() -> None:
    _, token_a = _register()
    _, token_b = _register()

    first = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token_a),
        json={"username": "alice"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token_b),
        json={"username": "alice"},
    )
    assert second.status_code == 409


def test_get_my_profile_returns_owned_profile() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "biography": "Hello",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/me",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"
    assert body["biography"] == "Hello"


def test_patch_profile_updates_fields() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "biography": "Old biography",
        },
    )
    assert created.status_code == 201

    response = client.patch(
        "/api/v1/profiles/me",
        headers=_auth_header(token),
        json={
            "display_name": "Alice Updated",
            "biography": "New biography",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["username"] == "alice"
    assert body["display_name"] == "Alice Updated"
    assert body["biography"] == "New biography"


def test_patch_profile_can_clear_nullable_fields() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "biography": "Biography",
            "location": "Nigeria",
        },
    )
    assert created.status_code == 201

    response = client.patch(
        "/api/v1/profiles/me",
        headers=_auth_header(token),
        json={
            "display_name": None,
            "biography": None,
            "location": None,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["display_name"] is None
    assert body["biography"] is None
    assert body["location"] is None


def test_patch_profile_omitted_fields_remain_unchanged() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "biography": "Keep this",
        },
    )
    assert created.status_code == 201

    response = client.patch(
        "/api/v1/profiles/me",
        headers=_auth_header(token),
        json={"display_name": "Updated"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["display_name"] == "Updated"
    assert body["biography"] == "Keep this"


def test_patch_profile_username_normalizes() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": "alice"},
    )
    assert created.status_code == 201

    response = client.patch(
        "/api/v1/profiles/me",
        headers=_auth_header(token),
        json={"username": "  Alice_123  "},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice_123"


def test_patch_duplicate_username_returns_conflict() -> None:
    _, token_a = _register()
    _, token_b = _register()

    first = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token_a),
        json={"username": "alice"},
    )
    second = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token_b),
        json={"username": "bob"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.patch(
        "/api/v1/profiles/me",
        headers=_auth_header(token_b),
        json={"username": "alice"},
    )

    assert response.status_code == 409


def test_public_profile_can_be_viewed_anonymously() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": "alice"},
    )
    assert created.status_code == 201

    response = client.get("/api/v1/profiles/alice")

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_private_profile_is_discoverable_to_anonymous_viewer() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "avatar": "https://example.com/avatar.png",
            "banner": "https://example.com/banner.png",
            "biography": "Private biography",
            "location": "Private location",
            "visibility": "private",
        },
    )
    assert created.status_code == 201

    response = client.get("/api/v1/profiles/alice")

    assert response.status_code == 200

    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"
    assert body["avatar"] == "https://example.com/avatar.png"
    assert body["visibility"] == "private"
    assert "banner" not in body
    assert "biography" not in body
    assert "location" not in body

def test_private_profile_is_visible_to_owner() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "visibility": "private",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/alice",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_private_profile_is_discoverable_to_other_user() -> None:
    _, owner_token = _register()
    _, viewer_token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(owner_token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "biography": "Private biography",
            "location": "Private location",
            "visibility": "private",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/alice",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200

    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"
    assert body["visibility"] == "private"
    assert "biography" not in body
    assert "location" not in body

def test_unknown_profile_returns_not_found() -> None:
    response = client.get(
        "/api/v1/profiles/nonexistent",
    )

    assert response.status_code == 404


def test_extra_user_id_is_rejected() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "user_id": str(uuid4()),
        },
    )

    assert response.status_code == 422


def test_invalid_visibility_returns_bad_request() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "visibility": "everyone",
        },
    )

    assert response.status_code == 400


def test_profile_persists_in_database() -> None:
    user_id, token = _register()

    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={"username": "alice"},
    )
    assert response.status_code == 201

    db = _db()
    try:
        profile = (
            db.query(Profile)
            .filter(Profile.user_id == user_id)
            .one()
        )

        assert profile.username == "alice"
        assert profile.visibility == "public"
    finally:
        db.rollback()
        db.close()


def test_profile_search_requires_authentication() -> None:
    response = client.get(
        "/api/v1/profiles/search",
        params={"q": "alice"},
    )

    assert response.status_code == 401


def test_profile_search_finds_username_and_display_name() -> None:
    _, viewer_token = _register()

    _, alice_token = _register()
    alice = client.post(
        "/api/v1/profiles",
        headers=_auth_header(alice_token),
        json={
            "username": "alice",
            "display_name": "Alice Johnson",
        },
    )
    assert alice.status_code == 201

    _, bob_token = _register()
    bob = client.post(
        "/api/v1/profiles",
        headers=_auth_header(bob_token),
        json={
            "username": "bob_builder",
            "display_name": "The Builder",
        },
    )
    assert bob.status_code == 201

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={"q": "alice"},
    )

    assert response.status_code == 200
    items = response.json()["items"]

    assert len(items) == 1
    assert items[0]["username"] == "alice"
    assert items[0]["display_name"] == "Alice Johnson"


def test_profile_search_matches_display_name_case_insensitively() -> None:
    _, viewer_token = _register()

    _, owner_token = _register()
    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(owner_token),
        json={
            "username": "alice",
            "display_name": "Alice Johnson",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={"q": "JOHNSON"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["username"] == "alice"


def test_profile_search_excludes_viewer() -> None:
    user_id, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(token),
        params={"q": "alice"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_profile_search_includes_private_profiles_without_private_fields() -> None:
    _, viewer_token = _register()

    _, owner_token = _register()
    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(owner_token),
        json={
            "username": "alice",
            "display_name": "Alice",
            "banner": "https://example.com/banner.png",
            "biography": "Private biography",
            "location": "Private location",
            "visibility": "private",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={"q": "alice"},
    )

    assert response.status_code == 200

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["username"] == "alice"
    assert items[0]["display_name"] == "Alice"
    assert items[0]["visibility"] == "private"
    assert "banner" not in items[0]
    assert "biography" not in items[0]
    assert "location" not in items[0]

def test_profile_search_excludes_inactive_users() -> None:
    _, viewer_token = _register()

    owner_id, owner_token = _register()
    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(owner_token),
        json={
            "username": "alice",
            "display_name": "Alice",
        },
    )
    assert created.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == owner_id).one()
        user.status = "suspended"
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={"q": "alice"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_profile_search_returns_deterministic_order() -> None:
    _, viewer_token = _register()

    for username in ("alice", "albert", "alex"):
        _, token = _register()
        created = client.post(
            "/api/v1/profiles",
            headers=_auth_header(token),
            json={"username": username},
        )
        assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={
            "q": "al",
            "limit": 50,
        },
    )

    assert response.status_code == 200
    assert [
        item["username"]
        for item in response.json()["items"]
    ] == ["albert", "alex", "alice"]


def test_profile_search_cursor_paginates() -> None:
    _, viewer_token = _register()

    for username in ("alice", "albert", "alex"):
        _, token = _register()
        created = client.post(
            "/api/v1/profiles",
            headers=_auth_header(token),
            json={"username": username},
        )
        assert created.status_code == 201

    first = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={
            "q": "al",
            "limit": 2,
        },
    )

    assert first.status_code == 200
    first_body = first.json()

    assert [
        item["username"]
        for item in first_body["items"]
    ] == ["albert", "alex"]
    assert first_body["next_cursor"]

    second = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={
            "q": "al",
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
    )

    assert second.status_code == 200
    second_body = second.json()

    assert [
        item["username"]
        for item in second_body["items"]
    ] == ["alice"]
    assert second_body["next_cursor"] is None


def test_profile_search_rejects_invalid_input() -> None:
    _, token = _register()

    for params in (
        {"q": ""},
        {"q": "   "},
        {"q": "a" * 101},
        {"q": "alice", "limit": 0},
        {"q": "alice", "limit": 51},
        {"q": "alice", "cursor": "not-a-valid-cursor"},
    ):
        response = client.get(
            "/api/v1/profiles/search",
            headers=_auth_header(token),
            params=params,
        )

        assert response.status_code == 400


def test_profile_search_does_not_expose_authentication_fields() -> None:
    _, viewer_token = _register()

    _, owner_token = _register()
    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(owner_token),
        json={
            "username": "alice",
            "display_name": "Alice",
        },
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/profiles/search",
        headers=_auth_header(viewer_token),
        params={"q": "alice"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]

    assert "email" not in item
    assert "provider" not in item
    assert "provider_subject" not in item
    assert "session_token" not in item
    assert "token_hash" not in item
    assert "password_hash" not in item

def test_profile_verification_is_read_only_and_defaults_to_unverified() -> None:
    _, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice",
            "display_name": "Alice",
        },
    )

    assert created.status_code == 201
    body = created.json()

    assert body["verified_at"] is None

    attempted_verification = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "alice2",
            "verified_at": "2026-10-08T00:00:00Z",
        },
    )

    assert attempted_verification.status_code == 422



def test_profile_verification_service_marks_profile_verified() -> None:
    user_id, token = _register()

    created = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": "verified_user",
            "display_name": "Verified User",
        },
    )

    assert created.status_code == 201
    assert created.json()["verified_at"] is None

    db = _db()
    try:
        verified = verify_profile(
            db,
            user_id=user_id,
        )
        assert verified.verified_at is not None
        first_verified_at = verified.verified_at
    finally:
        db.close()

    db = _db()
    try:
        profile = db.query(Profile).filter(Profile.user_id == user_id).one()
        assert profile.verified_at == first_verified_at
    finally:
        db.close()

    db = _db()
    try:
        verified_again = verify_profile(
            db,
            user_id=user_id,
        )
        assert verified_again.verified_at == first_verified_at
    finally:
        db.close()


def test_profile_verification_service_rejects_missing_profile() -> None:
    user_id, _ = _register()

    db = _db()
    try:
        with pytest.raises(ProfileNotFoundForVerificationError):
            verify_profile(
                db,
                user_id=user_id,
            )
    finally:
        db.close()
