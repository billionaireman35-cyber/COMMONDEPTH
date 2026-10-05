from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.identity import User
from app.models.profile import Profile
from app.models.social import Follow, FollowRequest


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_social() -> None:
    db = SessionLocal()
    try:
        db.query(FollowRequest).delete()
        db.query(Follow).delete()
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


def _create_profile(
    token: str,
    username: str,
    *,
    visibility: str = "public",
) -> dict:
    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": username,
            "visibility": visibility,
        },
    )

    assert response.status_code == 201

    return response.json()


def _get_request(
    *,
    requester_id: str,
    target_id: str,
) -> FollowRequest | None:
    db = _db()
    try:
        return (
            db.query(FollowRequest)
            .filter(
                FollowRequest.requester_id == requester_id,
                FollowRequest.target_id == target_id,
            )
            .first()
        )
    finally:
        db.close()


def test_follow_public_profile_creates_follow() -> None:
    _, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(target_token, "alice")

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 201
    assert response.json() == {"status": "following"}

    db = _db()
    try:
        follow = (
            db.query(Follow)
            .filter(Follow.following_id == target_id)
            .first()
        )
        assert follow is not None
    finally:
        db.close()


def test_follow_private_profile_creates_pending_request() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 201
    assert response.json() == {"status": "pending"}

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )

    assert request is not None
    assert request.status == "pending"


def test_follow_requires_authentication() -> None:
    response = client.post(
        "/api/v1/social/follow/alice",
    )

    assert response.status_code == 401


def test_unfollow_requires_authentication() -> None:
    response = client.delete(
        "/api/v1/social/follow/alice",
    )

    assert response.status_code == 401


def test_self_follow_is_rejected() -> None:
    _, token = _register()
    _create_profile(token, "alice")

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot follow yourself."


def test_follow_nonexistent_profile_returns_404() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/social/follow/doesnotexist",
        headers=_auth_header(token),
    )

    assert response.status_code == 404


def test_follow_inactive_user_returns_404() -> None:
    _, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(target_token, "alice")

    db = _db()
    try:
        target = db.get(User, target_id)
        assert target is not None
        target.status = "suspended"
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 404


def test_duplicate_follow_returns_conflict() -> None:
    _, follower_token = _register()
    _, target_token = _register()

    _create_profile(target_token, "alice")

    first = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert first.status_code == 201
    assert first.json() == {"status": "following"}

    second = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert second.status_code == 409
    assert second.json()["detail"] == "Already following this user."


def test_duplicate_pending_request_returns_conflict() -> None:
    _, follower_token = _register()
    _, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    first = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert first.status_code == 201
    assert first.json() == {"status": "pending"}

    second = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert second.status_code == 409
    assert second.json()["detail"] == (
        "A follow request is already pending."
    )


def test_accept_pending_request_creates_follow() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert follow_response.status_code == 201
    assert follow_response.json() == {"status": "pending"}

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    request_id = request.id

    response = client.post(
        f"/api/v1/social/follow-requests/{request_id}/accept",
        headers=_auth_header(target_token),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "following"}

    db = _db()
    try:
        follow = (
            db.query(Follow)
            .filter(
                Follow.follower_id == follower_id,
                Follow.following_id == target_id,
            )
            .first()
        )
        assert follow is not None

        stored_request = db.get(FollowRequest, request_id)
        assert stored_request is None
    finally:
        db.close()


def test_accept_request_requires_target_authorization() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()
    _, attacker_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    response = client.post(
        f"/api/v1/social/follow-requests/{request.id}/accept",
        headers=_auth_header(attacker_token),
    )

    assert response.status_code == 403


def test_reject_pending_request() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    response = client.post(
        f"/api/v1/social/follow-requests/{request.id}/reject",
        headers=_auth_header(target_token),
    )

    assert response.status_code == 200

    assert response.json() == {"status": "rejected"}

    db = _db()
    try:
        stored_request = db.get(FollowRequest, request.id)
        assert stored_request is not None
        assert stored_request.status == "rejected"
    finally:
        db.close()


def test_reject_request_requires_target_authorization() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()
    _, attacker_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    response = client.post(
        f"/api/v1/social/follow-requests/{request.id}/reject",
        headers=_auth_header(attacker_token),
    )

    assert response.status_code == 403


def test_cancel_pending_request_requires_requester() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()
    _, attacker_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    response = client.delete(
        f"/api/v1/social/follow-requests/{request.id}",
        headers=_auth_header(attacker_token),
    )

    assert response.status_code == 403


def test_cancel_pending_request_removes_request() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    response = client.delete(
        f"/api/v1/social/follow-requests/{request.id}",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 204

    db = _db()
    try:
        assert db.get(FollowRequest, request.id) is None
    finally:
        db.close()


def test_unfollow_removes_existing_follow() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(target_token, "alice")

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    response = client.delete(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 204

    db = _db()
    try:
        follow = (
            db.query(Follow)
            .filter(
                Follow.follower_id == follower_id,
                Follow.following_id == target_id,
            )
            .first()
        )
        assert follow is None
    finally:
        db.close()


def test_unfollow_nonexistent_relationship_returns_404() -> None:
    _, follower_token = _register()
    _, target_token = _register()

    _create_profile(target_token, "alice")

    response = client.delete(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 404


def test_unfollow_does_not_remove_pending_request() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    follow_response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert follow_response.status_code == 201

    response = client.delete(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 404

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None
    assert request.status == "pending"


def test_rejected_request_can_be_requested_again() -> None:
    follower_id, follower_token = _register()
    target_id, target_token = _register()

    _create_profile(
        target_token,
        "alice",
        visibility="private",
    )

    first = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert first.status_code == 201

    request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert request is not None

    reject = client.post(
        f"/api/v1/social/follow-requests/{request.id}/reject",
        headers=_auth_header(target_token),
    )
    assert reject.status_code == 200

    second = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert second.status_code == 201
    assert second.json() == {"status": "pending"}

    new_request = _get_request(
        requester_id=follower_id,
        target_id=target_id,
    )
    assert new_request is not None
    assert new_request.status == "pending"


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/social/follow-requests/not-a-uuid/accept"),
        ("post", "/api/v1/social/follow-requests/not-a-uuid/reject"),
        ("delete", "/api/v1/social/follow-requests/not-a-uuid"),
    ],
)
def test_invalid_request_uuid_returns_422(
    method: str,
    path: str,
) -> None:
    _, token = _register()

    response = getattr(client, method)(
        path,
        headers=_auth_header(token),
    )

    assert response.status_code == 422


def test_invalid_session_returns_401() -> None:
    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header("invalid-session-token"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication failed."


def test_social_responses_do_not_expose_session_data() -> None:
    _, follower_token = _register()
    _, target_token = _register()

    _create_profile(target_token, "alice")

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 201

    body = response.json()

    assert set(body) == {"status"}
    assert "session_token" not in body
    assert "password" not in body
    assert "password_hash" not in body


def test_follow_username_is_normalized() -> None:
    _, follower_token = _register()
    _, target_token = _register()

    _create_profile(target_token, "alice")

    response = client.post(
        "/api/v1/social/follow/  Alice  ",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 201
    assert response.json() == {"status": "following"}
