from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.identity import User
from app.models.profile import Profile
from app.models.username_registry import UsernameRegistry
from app.models.social import Follow, FollowRequest


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_social() -> None:
    db = SessionLocal()
    try:
        db.query(FollowRequest).delete()
        db.query(Follow).delete()
        db.query(UsernameRegistry).delete()
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

def test_relationship_counts_and_lists_are_correct() -> None:
    _, alice_token = _register()
    bob_id, bob_token = _register()
    _, charlie_token = _register()

    _create_profile(alice_token, "alice")
    _create_profile(bob_token, "bob")
    _create_profile(charlie_token, "charlie")

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(bob_token),
    )
    assert response.status_code == 201

    response = client.post(
        "/api/v1/social/follow/charlie",
        headers=_auth_header(alice_token),
    )
    assert response.status_code == 201

    response = client.get(
        "/api/v1/social/profiles/alice/relationships",
        headers=_auth_header(alice_token),
    )
    assert response.status_code == 200
    assert response.json() == {
        "follower_count": 1,
        "following_count": 1,
    }

    response = client.get(
        "/api/v1/social/profiles/alice/followers",
        headers=_auth_header(alice_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["username"] for item in body["items"]] == ["bob"]
    assert body["next_cursor"] is None

    # Relationship list items must not expose private profile fields.
    item = body["items"][0]
    assert "biography" not in item
    assert "location" not in item

    response = client.get(
        "/api/v1/social/profiles/alice/following",
        headers=_auth_header(alice_token),
    )
    assert response.status_code == 200
    assert [item["username"] for item in response.json()["items"]] == [
        "charlie"
    ]


def test_follower_pagination_returns_every_profile_once() -> None:
    _, alice_token = _register()
    _create_profile(alice_token, "alice")

    follower_tokens = []
    for username in ("bob", "carol", "dave"):
        _, token = _register()
        _create_profile(token, username)
        follower_tokens.append(token)

        response = client.post(
            "/api/v1/social/follow/alice",
            headers=_auth_header(token),
        )
        assert response.status_code == 201

    first = client.get(
        "/api/v1/social/profiles/alice/followers",
        params={"limit": 2},
        headers=_auth_header(alice_token),
    )
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second = client.get(
        "/api/v1/social/profiles/alice/followers",
        params={
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
        headers=_auth_header(alice_token),
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["items"]) == 1
    assert second_body["next_cursor"] is None

    usernames = [
        item["username"]
        for item in first_body["items"] + second_body["items"]
    ]
    assert len(usernames) == 3
    assert set(usernames) == {"bob", "carol", "dave"}


def test_private_relationships_require_owner_or_accepted_follower() -> None:
    owner_id, owner_token = _register()
    viewer_id, viewer_token = _register()
    _, stranger_token = _register()

    _create_profile(owner_token, "privatealice", visibility="private")

    # A private-profile follow attempt creates a pending request, not a follow.
    response = client.post(
        "/api/v1/social/follow/privatealice",
        headers=_auth_header(viewer_token),
    )
    assert response.status_code == 201
    assert response.json() == {"status": "pending"}

    denied = client.get(
        "/api/v1/social/profiles/privatealice/relationships",
        headers=_auth_header(stranger_token),
    )
    assert denied.status_code == 403

    # The owner can inspect counts; a pending request contributes zero.
    owner_counts = client.get(
        "/api/v1/social/profiles/privatealice/relationships",
        headers=_auth_header(owner_token),
    )
    assert owner_counts.status_code == 200
    assert owner_counts.json() == {
        "follower_count": 0,
        "following_count": 0,
    }

    db = _db()
    try:
        request = (
            db.query(FollowRequest)
            .filter(
                FollowRequest.requester_id == UUID(viewer_id),
                FollowRequest.target_id == UUID(owner_id),
                FollowRequest.status == "pending",
            )
            .one()
        )
        request_id = request.id
    finally:
        db.close()

    accepted = client.post(
        f"/api/v1/social/follow-requests/{request_id}/accept",
        headers=_auth_header(owner_token),
    )
    assert accepted.status_code == 200

    allowed = client.get(
        "/api/v1/social/profiles/privatealice/followers",
        headers=_auth_header(viewer_token),
    )
    assert allowed.status_code == 200
    assert allowed.json()["next_cursor"] is None
    assert allowed.json()["items"] == []


def test_inactive_related_accounts_are_excluded() -> None:
    follower_id, follower_token = _register()
    _, alice_token = _register()

    _create_profile(follower_token, "inactivebob")
    _create_profile(alice_token, "alice")

    response = client.post(
        "/api/v1/social/follow/alice",
        headers=_auth_header(follower_token),
    )
    assert response.status_code == 201

    db = _db()
    try:
        follower = db.get(User, UUID(follower_id))
        assert follower is not None
        follower.status = "deactivated"
        db.commit()
    finally:
        db.close()

    counts = client.get(
        "/api/v1/social/profiles/alice/relationships",
        headers=_auth_header(alice_token),
    )
    assert counts.status_code == 200
    assert counts.json()["follower_count"] == 0

    followers = client.get(
        "/api/v1/social/profiles/alice/followers",
        headers=_auth_header(alice_token),
    )
    assert followers.status_code == 200
    assert followers.json()["items"] == []


def test_relationship_endpoints_require_authentication() -> None:
    for suffix in ("relationships", "followers", "following"):
        response = client.get(
            f"/api/v1/social/profiles/alice/{suffix}",
        )
        assert response.status_code == 401


def test_relationship_list_rejects_invalid_cursor() -> None:
    _, token = _register()
    _create_profile(token, "alice")

    response = client.get(
        "/api/v1/social/profiles/alice/followers",
        params={"cursor": "not-a-valid-cursor"},
        headers=_auth_header(token),
    )
    assert response.status_code == 422
